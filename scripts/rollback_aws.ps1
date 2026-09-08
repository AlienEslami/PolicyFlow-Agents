[CmdletBinding()]
param(
    [string]$Region = "ca-central-1",
    [string]$Cluster = "policyflow-agents-prod",
    [string]$Service = "policyflow-agents-prod",
    [string]$TaskFamily = "policyflow-agents-prod",
    [string]$TaskDefinitionArn
)

$ErrorActionPreference = "Stop"
if (-not $TaskDefinitionArn) {
    $definitions = aws ecs list-task-definitions `
        --region $Region `
        --family-prefix $TaskFamily `
        --status ACTIVE `
        --sort DESC `
        --query "taskDefinitionArns[0:2]" `
        --output json | ConvertFrom-Json
    if ($definitions.Count -lt 2) {
        throw "No previous active task-definition revision is available."
    }
    $TaskDefinitionArn = [string]$definitions[1]
}

aws ecs update-service `
    --region $Region `
    --cluster $Cluster `
    --service $Service `
    --task-definition $TaskDefinitionArn `
    --force-new-deployment | Out-Null
if ($LASTEXITCODE -ne 0) { throw "Rollback update failed." }
aws ecs wait services-stable --region $Region --cluster $Cluster --services $Service
if ($LASTEXITCODE -ne 0) { throw "Rolled-back service did not become stable." }
Write-Output "Rolled back $Service to $TaskDefinitionArn"

