$ErrorActionPreference = "Stop"

$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$Build = Join-Path $Here "BUILD_R11B_DENSE_MACHINE.py"

$Blender = "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe"

if (-not (Test-Path $Blender)) {
    Write-Host "Expected Blender 5.2 not found at:" -ForegroundColor Red
    Write-Host $Blender
    Write-Host ""
    Write-Host "Locate Blender and run BUILD_R11B_DENSE_MACHINE.py with --background --python."
    Read-Host "Press ENTER"
    exit 1
}

Write-Host ""
Write-Host "E.V. R11B DENSE MACHINE FORGE" -ForegroundColor Cyan
Write-Host "==============================" -ForegroundColor Cyan
Write-Host ""

& $Blender --background --python $Build

if ($LASTEXITCODE -ne 0) {
    Write-Host "R11B Forge failed: $LASTEXITCODE" -ForegroundColor Red
    Read-Host "Press ENTER"
    exit $LASTEXITCODE
}

Write-Host ""
Write-Host "R11B renders are ready." -ForegroundColor Green
Write-Host (Join-Path $Here "output\renders")
Write-Host ""
Write-Host "DO NOT integrate into D:\EV\gui."
Write-Host "Upload the five R11B PNG renders to ChatGPT first."
Read-Host "Press ENTER"
