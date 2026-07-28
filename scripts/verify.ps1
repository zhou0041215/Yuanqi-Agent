param(
    [switch]$WithDockerSandbox,
    [switch]$RebuildDockerSandbox
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$previousDockerFlag = $env:YUANQI_RUN_DOCKER_TESTS

function Invoke-Checked {
    param(
        [Parameter(Mandatory = $true)][scriptblock]$Command,
        [Parameter(Mandatory = $true)][string]$Label
    )

    Write-Host "`n==> $Label"
    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw "$Label failed with exit code $LASTEXITCODE"
    }
}

try {
    Push-Location $projectRoot
    Invoke-Checked { docker compose config --quiet } "Validate Docker Compose"
    if ($WithDockerSandbox) {
        $localSandboxImage = docker image inspect yuanqi-agent-sandbox:local --format "{{.Id}}" 2>$null
        if ($RebuildDockerSandbox -or [string]::IsNullOrWhiteSpace($localSandboxImage)) {
            Invoke-Checked {
                docker build -f agent/sandbox/Dockerfile -t yuanqi-agent-sandbox:local agent/sandbox
            } "Build physical sandbox"
        } else {
            Write-Host "`n==> Reuse local physical sandbox image $localSandboxImage"
        }
        $env:YUANQI_RUN_DOCKER_TESTS = "1"
    } else {
        Remove-Item Env:YUANQI_RUN_DOCKER_TESTS -ErrorAction SilentlyContinue
    }
    Pop-Location

    Push-Location (Join-Path $projectRoot "backend")
    Invoke-Checked { mvn test } "Java tests"
    Pop-Location

    Push-Location (Join-Path $projectRoot "agent")
    Invoke-Checked { .\.venv\Scripts\python -m ruff check src tests } "Python lint"
    Invoke-Checked { .\.venv\Scripts\python -m pytest } "Python tests"
    Pop-Location

    Push-Location (Join-Path $projectRoot "frontend")
    Invoke-Checked { npm test } "Frontend tests"
    Invoke-Checked { npm run build } "Frontend production build"
    Pop-Location

    Write-Host "`nAll YuanQi verification gates passed."
} finally {
    while ((Get-Location).Path -ne $projectRoot -and (Get-Location).Path.StartsWith($projectRoot)) {
        Pop-Location
    }
    if ($null -eq $previousDockerFlag) {
        Remove-Item Env:YUANQI_RUN_DOCKER_TESTS -ErrorAction SilentlyContinue
    } else {
        $env:YUANQI_RUN_DOCKER_TESTS = $previousDockerFlag
    }
}
