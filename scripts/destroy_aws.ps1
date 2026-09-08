[CmdletBinding(SupportsShouldProcess = $true, ConfirmImpact = "High")]
param(
    [string]$Region = "ca-central-1",
    [string]$ProjectName = "policyflow-agents",
    [string]$EnvironmentName = "prod"
)

$ErrorActionPreference = "Stop"
$serviceStack = "$ProjectName-$EnvironmentName-service"
$bootstrapStack = "$ProjectName-$EnvironmentName-ecr"

if ($PSCmdlet.ShouldProcess(
    "$serviceStack and $bootstrapStack in $Region",
    "Permanently delete the AWS deployment, ECR images, runtime secret, and logs"
)) {
    aws cloudformation delete-stack --region $Region --stack-name $serviceStack
    aws cloudformation wait stack-delete-complete --region $Region --stack-name $serviceStack
    if ($LASTEXITCODE -ne 0) { throw "Service stack deletion failed." }
    aws cloudformation delete-stack --region $Region --stack-name $bootstrapStack
    aws cloudformation wait stack-delete-complete --region $Region --stack-name $bootstrapStack
    if ($LASTEXITCODE -ne 0) { throw "ECR stack deletion failed." }
    Write-Output "Deleted the PolicyFlow AWS deployment in $Region."
}

