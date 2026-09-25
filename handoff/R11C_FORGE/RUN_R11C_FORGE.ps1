$ErrorActionPreference = "Stop"

$Blender = "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe"
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$Build = Join-Path $Here "BUILD_R11C_FLAGSHIP_REACTOR.py"

if (-not (Test-Path $Blender)) {
    Write-Host "Blender 5.2 not found at expected path:" -ForegroundColor Red
    Write-Host $Blender
    exit 1
}

& $Blender --background --python $Build

if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

Write-Host ""
Write-Host "R11C FORGE COMPLETE" -ForegroundColor Green
Write-Host (Join-Path $Here "output\renders")
Write-Host ""
Write-Host "Do NOT integrate yet. Upload the five renders to ChatGPT."
