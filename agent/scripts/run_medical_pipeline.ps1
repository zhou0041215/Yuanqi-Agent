# Rebuild and verify the medical knowledge graph end-to-end.
#
# Prerequisites:
#   1. Neo4j (and optionally Qdrant) running via Docker Desktop:
#        docker compose up -d neo4j qdrant
#   2. The agent virtualenv installed:  py -3.12 -m venv .venv ; .\.venv\Scripts\python -m pip install -e ".[dev]"
#
# Usage (from the agent folder or anywhere):
#   .\scripts\run_medical_pipeline.ps1            # import -> standardize -> publish -> verify
#   .\scripts\run_medical_pipeline.ps1 -WithIndex # also rebuild the Qdrant vector index

[CmdletBinding()]
param(
  [switch]$WithIndex
)

$ErrorActionPreference = "Stop"

# scripts/ -> agent/
Set-Location (Join-Path $PSScriptRoot "..")
$py = ".\.venv\Scripts\python.exe"
if (-not (Test-Path $py)) { throw "Agent venv not found at $py. Create it first (see README)." }

Write-Host "==> [1/4] Importing full disease catalog (data/medical.json)..." -ForegroundColor Cyan
& $py scripts\import_disease_kb.py --file data/medical.json

Write-Host "==> [2/4] Standardizing catalog and departments..." -ForegroundColor Cyan
& $py scripts\standardize_medical_catalog.py

Write-Host "==> [3/4] Publishing the trusted, source-backed subset..." -ForegroundColor Cyan
& $py scripts\publish_trusted_medical_subset.py

if ($WithIndex) {
  Write-Host "==> [3b] Rebuilding Qdrant vector index..." -ForegroundColor Cyan
  & $py scripts\index_medical_knowledge.py
}

Write-Host "==> [4/4] Verifying knowledge-graph completeness..." -ForegroundColor Cyan
& $py scripts\verify_medical_kg.py

Write-Host "Done." -ForegroundColor Green
