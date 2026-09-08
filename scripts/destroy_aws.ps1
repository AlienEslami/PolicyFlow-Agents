[CmdletBinding(SupportsShouldProcess = $true, ConfirmImpact = "High")]
param(
    [ValidateSet("ca-central-1")]
    [string]$Region = "ca-central-1"
)

$ErrorActionPreference = "Stop"
$expectedAccountId = "071239861872"
$serviceStack = "policyflow-agents-prod-service"
$bootstrapStack = "policyflow-agents-prod-ecr"
$expectedBucket = "policyflow-agents-prod-ingestion-071239861872-ca-central-1"
$expectedOidcProvider = "arn:aws:iam::071239861872:oidc-provider/token.actions.githubusercontent.com"
$serviceTemplate = Join-Path (Split-Path -Parent $PSScriptRoot) "infra/aws/service.yaml"

$env:AWS_DEFAULT_REGION = $Region
$env:AWS_REGION = $Region

if (-not (Get-Command aws -ErrorAction SilentlyContinue)) {
    throw "AWS CLI v2 is required."
}

function Invoke-AwsText {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments,
        [switch]$AllowFailure
    )

    $output = & aws @Arguments 2>&1
    $exitCode = $LASTEXITCODE
    if ($exitCode -ne 0 -and -not $AllowFailure) {
        throw "AWS CLI failed: aws $($Arguments -join ' ')`n$($output -join [Environment]::NewLine)"
    }
    return [pscustomobject]@{
        ExitCode = $exitCode
        Output = ($output -join [Environment]::NewLine)
    }
}

function Get-Stack {
    param([Parameter(Mandatory = $true)][string]$StackName)

    $result = Invoke-AwsText -AllowFailure -Arguments @(
        "cloudformation", "describe-stacks",
        "--region", $Region,
        "--stack-name", $StackName,
        "--output", "json"
    )
    if ($result.ExitCode -ne 0) {
        return $null
    }
    return ($result.Output | ConvertFrom-Json).Stacks[0]
}

function Show-DeleteFailure {
    param([Parameter(Mandatory = $true)][string]$StackName)

    $stack = Get-Stack -StackName $StackName
    if ($null -ne $stack) {
        Write-Error "$StackName ended in $($stack.StackStatus): $($stack.StackStatusReason)" -ErrorAction Continue
    }

    $events = Invoke-AwsText -AllowFailure -Arguments @(
        "cloudformation", "describe-stack-events",
        "--region", $Region,
        "--stack-name", $StackName,
        "--query", "StackEvents[?ResourceStatus=='DELETE_FAILED'].[Timestamp,LogicalResourceId,PhysicalResourceId,ResourceStatusReason]",
        "--output", "table"
    )
    if ($events.Output) {
        Write-Host $events.Output
    }
}

function Wait-ForStackDeletion {
    param([Parameter(Mandatory = $true)][string]$StackName)

    $wait = Invoke-AwsText -AllowFailure -Arguments @(
        "cloudformation", "wait", "stack-delete-complete",
        "--region", $Region,
        "--stack-name", $StackName
    )
    if ($wait.ExitCode -ne 0) {
        Show-DeleteFailure -StackName $StackName
        throw "$StackName deletion did not complete. No later deletion step was attempted. Diagnose the failed resource before retrying."
    }
}

function Enable-OidcRetention {
    param([Parameter(Mandatory = $true)]$Stack)

    $providerResource = Invoke-AwsText -AllowFailure -Arguments @(
        "cloudformation", "describe-stack-resource",
        "--region", $Region,
        "--stack-name", $serviceStack,
        "--logical-resource-id", "GitHubOidcProvider",
        "--output", "json"
    )
    if ($providerResource.ExitCode -ne 0) {
        Write-Host "The service stack does not own GitHubOidcProvider; no provider lifecycle will be changed."
        return
    }

    $physicalId = [string](($providerResource.Output | ConvertFrom-Json).StackResourceDetail.PhysicalResourceId)
    if ($physicalId -ne $expectedOidcProvider) {
        throw "Refusing to continue: unexpected stack-managed OIDC provider '$physicalId'."
    }

    $parameterArguments = @()
    foreach ($parameter in $Stack.Parameters) {
        $parameterArguments += "ParameterKey=$($parameter.ParameterKey),UsePreviousValue=true"
    }

    $updateArguments = @(
        "cloudformation", "update-stack",
        "--region", $Region,
        "--stack-name", $serviceStack,
        "--template-body", "file://$($serviceTemplate -replace '\\', '/')",
        "--capabilities", "CAPABILITY_IAM",
        "--parameters"
    ) + $parameterArguments

    $update = Invoke-AwsText -AllowFailure -Arguments $updateArguments
    if ($update.ExitCode -ne 0) {
        if ($update.Output -match "No updates are to be performed") {
            Write-Host "The deployed template already retains the GitHub OIDC provider."
            return
        }
        throw "Could not install the OIDC retention policy before deletion:`n$($update.Output)"
    }

    Invoke-AwsText -Arguments @(
        "cloudformation", "wait", "stack-update-complete",
        "--region", $Region,
        "--stack-name", $serviceStack
    ) | Out-Null
    Write-Host "CloudFormation retention is active for $expectedOidcProvider."
}

function Clear-ExactVersionedBucket {
    param([Parameter(Mandatory = $true)][string]$BucketName)

    if ($BucketName -ne $expectedBucket) {
        throw "Refusing to empty unexpected bucket '$BucketName'. Expected '$expectedBucket'."
    }

    $bucketLookup = Invoke-AwsText -Arguments @(
        "s3api", "list-buckets",
        "--query", "Buckets[?Name=='$BucketName'].Name",
        "--output", "text"
    )
    if (-not $bucketLookup.Output.Trim()) {
        Write-Host "The exact ingestion bucket is already absent; continuing a prior teardown safely."
        return
    }

    $deletedCount = 0
    while ($true) {
        # Re-read and delete the first 1,000 entries until none remain. This avoids
        # pagination races and permanently removes both versions and delete markers.
        $inventoryResult = Invoke-AwsText -Arguments @(
            "s3api", "list-object-versions",
            "--region", $Region,
            "--bucket", $BucketName,
            "--max-items", "1000",
            "--output", "json"
        )
        $inventory = $inventoryResult.Output | ConvertFrom-Json
        $objects = @()
        foreach ($version in @($inventory.Versions)) {
            if ($null -ne $version) {
                $objects += [ordered]@{ Key = [string]$version.Key; VersionId = [string]$version.VersionId }
            }
        }
        foreach ($marker in @($inventory.DeleteMarkers)) {
            if ($null -ne $marker) {
                $objects += [ordered]@{ Key = [string]$marker.Key; VersionId = [string]$marker.VersionId }
            }
        }

        if ($objects.Count -eq 0) {
            break
        }

        $deleteDocument = [ordered]@{ Objects = $objects; Quiet = $true } | ConvertTo-Json -Depth 4 -Compress
        $temporaryFile = Join-Path ([IO.Path]::GetTempPath()) ("policyflow-s3-delete-{0}.json" -f [Guid]::NewGuid().ToString("N"))
        try {
            [IO.File]::WriteAllText($temporaryFile, $deleteDocument, [Text.UTF8Encoding]::new($false))
            $deleteResult = Invoke-AwsText -Arguments @(
                "s3api", "delete-objects",
                "--region", $Region,
                "--bucket", $BucketName,
                "--delete", "file://$($temporaryFile -replace '\\', '/')",
                "--output", "json"
            )
            $deleteResponse = $deleteResult.Output | ConvertFrom-Json
            if (@($deleteResponse.Errors).Count -gt 0) {
                throw "S3 returned per-object deletion errors: $($deleteResponse.Errors | ConvertTo-Json -Depth 4 -Compress)"
            }
            $deletedCount += $objects.Count
        }
        finally {
            if (Test-Path -LiteralPath $temporaryFile) {
                Remove-Item -LiteralPath $temporaryFile -Force
            }
        }
    }

    $verification = (Invoke-AwsText -Arguments @(
        "s3api", "list-object-versions",
        "--region", $Region,
        "--bucket", $BucketName,
        "--query", "length(Versions || ``[]) + length(DeleteMarkers || ``[])",
        "--output", "text"
    )).Output.Trim()
    if ($verification -ne "0") {
        throw "Bucket verification found $verification remaining versions or delete markers."
    }
    Write-Host "Permanently deleted $deletedCount object versions/delete markers from $BucketName."
}

$identityResult = Invoke-AwsText -Arguments @("sts", "get-caller-identity", "--region", $Region, "--output", "json")
$identity = $identityResult.Output | ConvertFrom-Json
if ([string]$identity.Account -ne $expectedAccountId) {
    throw "Refusing to continue in AWS account $($identity.Account). Expected $expectedAccountId."
}

$service = Get-Stack -StackName $serviceStack
$bootstrap = Get-Stack -StackName $bootstrapStack
if ($null -eq $service -and $null -eq $bootstrap) {
    Write-Output "Both exact PolicyFlow stacks are already absent. No deletion was attempted."
    return
}
if ($null -ne $service -and [string]$service.StackStatus -notin @("UPDATE_COMPLETE", "DELETE_FAILED")) {
    throw "Refusing to start from service stack status $($service.StackStatus). Diagnose it first."
}
if ($null -ne $bootstrap -and [string]$bootstrap.StackStatus -notin @("CREATE_COMPLETE", "DELETE_FAILED")) {
    throw "Refusing to start from bootstrap stack status $($bootstrap.StackStatus). Diagnose it first."
}

if ($null -ne $service) {
    $bucketOutput = @($service.Outputs | Where-Object OutputKey -eq "IngestionBucketName")
    if ($bucketOutput.Count -ne 1 -or [string]$bucketOutput[0].OutputValue -ne $expectedBucket) {
        throw "The service stack did not resolve to the exact expected ingestion bucket."
    }
}

$target = "AWS account $expectedAccountId; $serviceStack then $bootstrapStack; region $Region"
if ($PSCmdlet.ShouldProcess(
    $target,
    "Permanently empty the exact versioned ingestion bucket and delete the PolicyFlow production stacks while retaining the GitHub OIDC provider"
)) {
    if ($null -ne $service) {
        if ([string]$service.StackStatus -eq "DELETE_FAILED") {
            Show-DeleteFailure -StackName $serviceStack
        }
        else {
            Enable-OidcRetention -Stack $service
        }
        Clear-ExactVersionedBucket -BucketName $expectedBucket

        Invoke-AwsText -Arguments @(
            "cloudformation", "delete-stack",
            "--region", $Region,
            "--stack-name", $serviceStack,
            "--deletion-mode", "STANDARD"
        ) | Out-Null
        Wait-ForStackDeletion -StackName $serviceStack
    }

    if ($null -ne $bootstrap) {
        if ([string]$bootstrap.StackStatus -eq "DELETE_FAILED") {
            Show-DeleteFailure -StackName $bootstrapStack
        }
        Invoke-AwsText -Arguments @(
            "cloudformation", "delete-stack",
            "--region", $Region,
            "--stack-name", $bootstrapStack,
            "--deletion-mode", "STANDARD"
        ) | Out-Null
        Wait-ForStackDeletion -StackName $bootstrapStack
    }

    if ($null -ne (Get-Stack -StackName $serviceStack) -or $null -ne (Get-Stack -StackName $bootstrapStack)) {
        throw "Post-delete verification still found a PolicyFlow CloudFormation stack."
    }
    Write-Output "Deleted both PolicyFlow production stacks in $Region. The GitHub OIDC provider was retained."
    Write-Output "Run the documented post-delete resource audit before treating decommissioning as complete."
}
