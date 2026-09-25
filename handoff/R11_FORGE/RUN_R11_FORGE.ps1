$ErrorActionPreference = "Stop"

$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$Script = Join-Path $Here "BUILD_R11_VECTOR_REACTOR.py"

Write-Host ""
Write-Host "E.V. R11 VECTOR REACTOR FORGE" -ForegroundColor Cyan
Write-Host "================================" -ForegroundColor Cyan
Write-Host ""

# Try PATH first.
$Blender = Get-Command blender.exe -ErrorAction SilentlyContinue

if (-not $Blender) {
    $Candidates = @(
        "C:\Program Files\Blender Foundation\Blender 4.5\blender.exe",
        "C:\Program Files\Blender Foundation\Blender 4.4\blender.exe",
        "C:\Program Files\Blender Foundation\Blender 4.3\blender.exe",
        "C:\Program Files\Blender Foundation\Blender 4.2\blender.exe",
        "C:\Program Files\Blender Foundation\Blender 4.1\blender.exe",
        "C:\Program Files\Blender Foundation\Blender 4.0\blender.exe",
        "C:\Program Files\Blender Foundation\Blender 3.6\blender.exe"
    )

    foreach ($Candidate in $Candidates) {
        if (Test-Path $Candidate) {
            $Blender = $Candidate
            break
        }
    }
}

if (-not $Blender) {
    Write-Host "Blender was not found." -ForegroundColor Red
    Write-Host ""
    Write-Host "Install Blender first with:"
    Write-Host "winget install -e --id BlenderFoundation.Blender"
    Write-Host ""
    Read-Host "Press ENTER to close"
    exit 1
}

$BlenderPath = if ($Blender -is [System.Management.Automation.ApplicationInfo]) {
    $Blender.Source
} else {
    $Blender
}

Write-Host "Using Blender:" -ForegroundColor Green
Write-Host $BlenderPath
Write-Host ""
Write-Host "Building R11 source, GLBs and five approval renders..."
Write-Host ""

& $BlenderPath --background --python $Script

if ($LASTEXITCODE -ne 0) {
    throw "Blender R11 forge failed with exit code $LASTEXITCODE"
}

Write-Host ""
Write-Host "R11 FORGE COMPLETE" -ForegroundColor Green
Write-Host ""
Write-Host "Approval renders:"
Write-Host (Join-Path $Here "output\renders")
Write-Host ""
Write-Host "DO NOT integrate into D:\EV\gui yet."
Write-Host "Upload the 5 PNG renders to ChatGPT for approval."
Write-Host ""
Read-Host "Press ENTER to close"
