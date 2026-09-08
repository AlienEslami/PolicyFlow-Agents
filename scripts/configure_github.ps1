[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Owner,

    [Parameter(Mandatory = $true)]
    [string]$Repository,

    [Parameter(Mandatory = $true)]
    [string]$AwsDeployRoleArn,

    [Parameter(Mandatory = $true)]
    [string]$HttpsUrl
)

$ErrorActionPreference = "Stop"
if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    throw "GitHub CLI is required."
}
gh auth status
if ($LASTEXITCODE -ne 0) { throw "Authenticate GitHub CLI before running this script." }

$target = "$Owner/$Repository"
$tempBody = Join-Path ([System.IO.Path]::GetTempPath()) ("policyflow-gh-{0}.json" -f [Guid]::NewGuid())
try {
    [System.IO.File]::WriteAllText($tempBody, '{"wait_timer":0}')
    gh api --method PUT "repos/$target/environments/aws-production" --input $tempBody
    if ($LASTEXITCODE -ne 0) { throw "Could not create the GitHub deployment environment." }
}
finally {
    if (Test-Path -LiteralPath $tempBody) {
        Remove-Item -LiteralPath $tempBody -Force
    }
}
gh variable set AWS_DEPLOY_ROLE_ARN --repo $target --body $AwsDeployRoleArn
gh variable set POLICYFLOW_HTTPS_URL --repo $target --body $HttpsUrl

$ownerId = gh api "users/$Owner" --jq .id
$repositoryId = gh api "repos/$target" --jq .id
$subject = "repo:{0}@{1}/{2}@{3}:environment:aws-production" -f $Owner, $ownerId, $Repository, $repositoryId
Write-Output $subject
