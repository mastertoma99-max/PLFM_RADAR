param(
    [switch]$VerifyOnly,
    [string]$Python = 'python'
)
$ErrorActionPreference = 'Stop'
$env:PYTHONIOENCODING = 'utf-8'
# Qucs conversion is fully scripted. EAGLE schematics use the already imported
# KiCad baseline; KiCad 10.0 CLI has no direct EAGLE schematic import command.
if (-not $VerifyOnly) {
    & $Python (Join-Path $PSScriptRoot 'verification/convert_qucs.py')
    if ($LASTEXITCODE -ne 0) { throw 'Qucs conversion failed.' }
}
& $Python (Join-Path $PSScriptRoot 'verification/audit_schematics.py')
if ($LASTEXITCODE -ne 0) { throw 'EAGLE schematic comparison failed.' }
& $Python (Join-Path $PSScriptRoot 'verification/validate_all.py')
if ($LASTEXITCODE -ne 0) { throw 'KiCad verification failed.' }
Write-Host 'Completed. Reports: verification/final_validation.json'
