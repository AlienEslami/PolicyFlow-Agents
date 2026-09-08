[CmdletBinding()]
param(
    [string]$InputPath = "data/synthetic/ingestion_sample.json",
    [string]$Region = "ca-central-1",
    [string]$ProjectName = "policyflow-agents",
    [string]$EnvironmentName = "prod",
    [int]$WaitSeconds = 45
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$serviceStack = "$ProjectName-$EnvironmentName-service"
$resolvedInput = (Resolve-Path (Join-Path $projectRoot $InputPath)).Path
if (-not $resolvedInput.EndsWith(".json", [StringComparison]::OrdinalIgnoreCase)) {
    throw "Ingestion accepts JSON files only."
}
if ((Get-Item -LiteralPath $resolvedInput).Length -gt 1MB) {
    throw "Ingestion sample exceeds the one-megabyte pipeline limit."
}
Get-Content -Raw -LiteralPath $resolvedInput | ConvertFrom-Json | Out-Null

$bucket = aws cloudformation describe-stacks `
    --region $Region `
    --stack-name $serviceStack `
    --query "Stacks[0].Outputs[?OutputKey=='IngestionBucketName'].OutputValue" `
    --output text
if ($LASTEXITCODE -ne 0 -or -not $bucket) {
    throw "Could not resolve the deployed ingestion bucket."
}

$baseName = [IO.Path]::GetFileNameWithoutExtension($resolvedInput)
$submission = [Guid]::NewGuid().ToString("N")
$incomingKey = "incoming/$baseName-$submission.json"
$processedKey = "processed/$baseName-$submission.manifest.json"
aws s3 cp $resolvedInput "s3://$bucket/$incomingKey" `
    --region $Region `
    --only-show-errors `
    --sse AES256
if ($LASTEXITCODE -ne 0) { throw "Synthetic ingestion upload failed." }

$deadline = [DateTime]::UtcNow.AddSeconds($WaitSeconds)
do {
    aws s3api head-object `
        --region $Region `
        --bucket $bucket `
        --key $processedKey *> $null
    if ($LASTEXITCODE -eq 0) { break }
    Start-Sleep -Seconds 2
} while ([DateTime]::UtcNow -lt $deadline)
if ($LASTEXITCODE -ne 0) {
    throw "The processed manifest was not produced within $WaitSeconds seconds."
}

$artifacts = Join-Path $projectRoot "artifacts"
New-Item -ItemType Directory -Force -Path $artifacts | Out-Null
$output = Join-Path $artifacts "ingestion-manifest.json"
aws s3api get-object `
    --region $Region `
    --bucket $bucket `
    --key $processedKey `
    $output | Out-Null
if ($LASTEXITCODE -ne 0) { throw "Could not download the processed manifest." }

Write-Output "Synthetic ingestion completed."
Write-Output "Source: s3://$bucket/$incomingKey"
Write-Output "Manifest: s3://$bucket/$processedKey"
Write-Output "Local evidence: $output"
