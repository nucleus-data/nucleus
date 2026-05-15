# Nucleus Chocolatey uninstall script — DRAFT for v0.2.0.
#
# Docs: https://docs.chocolatey.org/en-us/create/functions/uninstall-binfile
#
# Removes the nucleus shim from PATH and deletes the venv that
# chocolateyInstall.ps1 created. Does NOT touch the python311 dep —
# Chocolatey handles that separately based on dependency reference counts.

$ErrorActionPreference = 'Stop'
$toolsDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$venvDir  = Join-Path $toolsDir 'venv'
$venvNucleus = Join-Path $venvDir 'Scripts\nucleus.exe'

# 1. Remove the PATH shim. Idempotent: Uninstall-BinFile is a no-op if the shim
#    doesn't exist, but be defensive.
if (Test-Path $venvNucleus) {
    Uninstall-BinFile -Name 'nucleus' -Path $venvNucleus
}

# 2. Remove the venv directory. Removes pyiceberg, polars, duckdb, pyarrow, etc.
#    A reinstall starts from a clean slate.
if (Test-Path $venvDir) {
    Write-Host "NUCLEUS-UNINSTALL: removing venv at $venvDir"
    Remove-Item -Recurse -Force $venvDir
}

Write-Host "NUCLEUS-UNINSTALL: complete. The python311 Chocolatey dep is untouched; " +
           "remove it separately with `choco uninstall python311` if no other package needs it."
