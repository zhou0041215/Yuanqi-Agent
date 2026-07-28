param(
    [switch]$ExpectGraphRag
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $projectRoot "agent\.venv\Scripts\python.exe"
$smoke = Join-Path $PSScriptRoot "smoke_medical_gateway.py"

if (-not (Test-Path -LiteralPath $python)) {
    throw "Agent virtual environment is missing: $python"
}
if (-not (Test-Path -LiteralPath $smoke)) {
    throw "Medical gateway smoke script is missing: $smoke"
}

Write-Host "==> Medical Java gateway, GraphRAG, sandbox, HITL, audit, and Flowable smoke"
& $python $smoke
if ($LASTEXITCODE -ne 0) {
    throw "Medical live smoke failed with exit code $LASTEXITCODE"
}

if ($ExpectGraphRag) {
    Write-Host "GraphRAG fusion was required and verified by smoke_medical_gateway.py."
}

Write-Host "Medical full-chain smoke passed."
