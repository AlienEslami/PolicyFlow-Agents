[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string]$GitHubSubject,

    [string]$Region = "ca-central-1",
    [string]$ProjectName = "policyflow-agents",
    [string]$EnvironmentName = "prod",
    [ValidateSet("true", "false")]
    [string]$EnableBedrock = "false"
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$bootstrapStack = "$ProjectName-$EnvironmentName-ecr"
$serviceStack = "$ProjectName-$EnvironmentName-service"
$repositoryName = "$ProjectName-$EnvironmentName"

foreach ($command in @("aws", "docker", "git")) {
    if (-not (Get-Command $command -ErrorAction SilentlyContinue)) {
        throw "Required command is unavailable: $command"
    }
}

$identity = aws sts get-caller-identity --output json | ConvertFrom-Json
if ($LASTEXITCODE -ne 0) {
    throw "AWS authentication failed. Configure a short-lived AWS CLI session first."
}
$accountId = [string]$identity.Account

aws cloudformation deploy `
    --region $Region `
    --stack-name $bootstrapStack `
    --template-file (Join-Path $projectRoot "infra/aws/bootstrap.yaml") `
    --parameter-overrides "ProjectName=$ProjectName" "EnvironmentName=$EnvironmentName" `
    --tags "Project=$ProjectName" "Environment=$EnvironmentName"
if ($LASTEXITCODE -ne 0) { throw "ECR bootstrap stack deployment failed." }

$repositoryUri = aws cloudformation describe-stacks `
    --region $Region `
    --stack-name $bootstrapStack `
    --query "Stacks[0].Outputs[?OutputKey=='RepositoryUri'].OutputValue" `
    --output text
$repositoryArn = aws cloudformation describe-stacks `
    --region $Region `
    --stack-name $bootstrapStack `
    --query "Stacks[0].Outputs[?OutputKey=='RepositoryArn'].OutputValue" `
    --output text

$revision = git -C $projectRoot rev-parse --short=12 HEAD 2>$null
if (-not $revision) {
    $revision = [DateTime]::UtcNow.ToString("yyyyMMddHHmmss")
}
$imageUri = "$repositoryUri`:$revision"
$registry = "$accountId.dkr.ecr.$Region.amazonaws.com"
$ecrPassword = aws ecr get-login-password --region $Region
if ($LASTEXITCODE -ne 0) { throw "Could not obtain the short-lived ECR login password." }
$ecrPassword | docker login --username AWS --password-stdin $registry | Out-Null
$ecrPassword = $null
if ($LASTEXITCODE -ne 0) { throw "Docker could not authenticate to ECR." }

docker build --pull --label "org.opencontainers.image.revision=$revision" -t $imageUri $projectRoot
if ($LASTEXITCODE -ne 0) { throw "Docker build failed." }
docker push $imageUri
if ($LASTEXITCODE -ne 0) { throw "Docker push failed." }

$oidcArn = ""
$providers = aws iam list-open-id-connect-providers --output json | ConvertFrom-Json
foreach ($provider in $providers.OpenIDConnectProviderList) {
    $details = aws iam get-open-id-connect-provider `
        --open-id-connect-provider-arn $provider.Arn `
        --output json | ConvertFrom-Json
    if ($details.Url -eq "token.actions.githubusercontent.com") {
        $oidcArn = [string]$provider.Arn
        break
    }
}

$originSecret = ([Guid]::NewGuid().ToString("N") + [Guid]::NewGuid().ToString("N"))
aws cloudformation deploy `
    --region $Region `
    --stack-name $serviceStack `
    --template-file (Join-Path $projectRoot "infra/aws/service.yaml") `
    --capabilities CAPABILITY_IAM `
    --parameter-overrides `
        "ProjectName=$ProjectName" `
        "EnvironmentName=$EnvironmentName" `
        "ImageUri=$imageUri" `
        "EcrRepositoryName=$repositoryName" `
        "EcrRepositoryArn=$repositoryArn" `
        "OriginVerifySecret=$originSecret" `
        "GitHubOidcProviderArn=$oidcArn" `
        "GitHubSubject=$GitHubSubject" `
        "EnableBedrock=$EnableBedrock" `
    --tags "Project=$ProjectName" "Environment=$EnvironmentName"
$originSecret = $null
if ($LASTEXITCODE -ne 0) { throw "PolicyFlow service stack deployment failed." }

$outputs = aws cloudformation describe-stacks `
    --region $Region `
    --stack-name $serviceStack `
    --query "Stacks[0].Outputs" `
    --output json | ConvertFrom-Json
$outputMap = @{}
foreach ($output in $outputs) {
    $outputMap[[string]$output.OutputKey] = [string]$output.OutputValue
}

aws ecs wait services-stable `
    --region $Region `
    --cluster $outputMap.ClusterName `
    --services $outputMap.ServiceName
if ($LASTEXITCODE -ne 0) { throw "ECS service did not become stable." }

$artifacts = Join-Path $projectRoot "artifacts"
New-Item -ItemType Directory -Force -Path $artifacts | Out-Null
$safeOutputs = [ordered]@{
    deployed_at_utc = [DateTime]::UtcNow.ToString("o")
    aws_account_id = $accountId
    aws_region = $Region
    image_uri = $imageUri
    https_url = $outputMap.HttpsUrl
    cluster_name = $outputMap.ClusterName
    service_name = $outputMap.ServiceName
    task_definition_family = $outputMap.TaskDefinitionFamily
    log_group = $outputMap.LogGroupName
    dashboard_url = $outputMap.DashboardUrl
    github_deploy_role_arn = $outputMap.GitHubDeployRoleArn
}
$safeOutputs | ConvertTo-Json | Set-Content `
    -Encoding utf8 `
    -Path (Join-Path $artifacts "aws-stack-outputs.json")

$python = Join-Path $projectRoot ".venv/Scripts/python.exe"
if (-not (Test-Path $python)) { $python = "python" }
& $python (Join-Path $projectRoot "scripts/load_test.py") `
    --url "$($outputMap.HttpsUrl)/health/live" `
    --requests 60 `
    --concurrency 6 `
    --max-error-rate 0 `
    --max-p95-ms 2500 `
    --output (Join-Path $artifacts "aws-load-test.json")
if ($LASTEXITCODE -ne 0) { throw "The deployed HTTPS load test failed its gate." }

Write-Output "PolicyFlow is deployed at $($outputMap.HttpsUrl)"
Write-Output "GitHub deploy role: $($outputMap.GitHubDeployRoleArn)"
Write-Output "Non-secret evidence: $artifacts"

