# Nucleus Chocolatey install script — DRAFT for v0.2.0.
#
# Docs: https://docs.chocolatey.org/en-us/create/functions/install-chocolateyzippackage
#       https://docs.chocolatey.org/en-us/create/functions/install-binfile
#
# Strategy:
#   1. Locate the Python 3.11 installed by the python311 dependency.
#   2. Create an isolated virtualenv under $toolsDir\venv.
#   3. Download the published wheel from the GitHub release.
#   4. pip install the wheel into the venv.
#   5. Shim venv\Scripts\nucleus.exe onto $PATH via Install-BinFile.
#
# Why a venv (not a global pip install): clean uninstall, version isolation
# from any other Python tools the user has, idempotent reinstall.

$ErrorActionPreference = 'Stop'
$toolsDir   = Split-Path -Parent $MyInvocation.MyCommand.Definition
$packageId  = 'nucleus'
$pkgVersion = $env:ChocolateyPackageVersion  # injected by Chocolatey

# ----------------------------------------------------------------------------
# 1. Resolve Python 3.11 — installed by the python311 dependency in nuspec.
# ----------------------------------------------------------------------------
# The python311 Chocolatey package installs to one of:
#   $env:ChocolateyToolsLocation\python311\python.exe   (Choco-managed)
#   C:\Python311\python.exe                              (default location)
# We probe both, plus PATH lookup as fallback.
$candidates = @(
    "$env:ChocolateyToolsLocation\python311\python.exe",
    "$env:SystemDrive\Python311\python.exe",
    "$env:ProgramFiles\Python311\python.exe"
)

$pythonExe = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1

if (-not $pythonExe) {
    # Fall back to PATH lookup
    $pyOnPath = (Get-Command python -ErrorAction SilentlyContinue).Path
    if ($pyOnPath) {
        $verOut = & $pyOnPath --version 2>&1
        if ($verOut -match 'Python 3\.11') {
            $pythonExe = $pyOnPath
        }
    }
}

if (-not $pythonExe) {
    throw "NUCLEUS-INSTALL: Python 3.11 was not located even after installing the python311 dependency. " +
          "Searched: $($candidates -join '; '). Open an issue at https://github.com/nucleus-data/nucleus/issues " +
          "with `choco list python311` output."
}

Write-Host "NUCLEUS-INSTALL: using Python at $pythonExe"

# ----------------------------------------------------------------------------
# 2. Create the venv (idempotent — recreated on reinstall by chocolateyUninstall).
# ----------------------------------------------------------------------------
$venvDir = Join-Path $toolsDir 'venv'
if (Test-Path $venvDir) {
    Write-Host "NUCLEUS-INSTALL: removing existing venv at $venvDir (reinstall path)"
    Remove-Item -Recurse -Force $venvDir
}

& $pythonExe -m venv $venvDir
if ($LASTEXITCODE -ne 0) {
    throw "NUCLEUS-INSTALL: venv creation failed. Confirm Python 3.11 has the venv module."
}

$venvPython = Join-Path $venvDir 'Scripts\python.exe'
$venvNucleus = Join-Path $venvDir 'Scripts\nucleus.exe'

# ----------------------------------------------------------------------------
# 3. Download wheel from GitHub release. SHA256 is verified by Install-ChocolateyZipPackage's
#    sibling helper Get-ChocolateyWebFile.
# ----------------------------------------------------------------------------
# IMPORTANT: PyPI distribution name is `nucleus-data`, so the wheel filename uses
# the underscore-normalised `nucleus_data` per PEP 427.
$wheelName = "nucleus_data-${pkgVersion}-py3-none-any.whl"
$wheelUrl  = "https://github.com/nucleus-data/nucleus/releases/download/v${pkgVersion}/${wheelName}"
$wheelDest = Join-Path $toolsDir $wheelName

# REPLACE THIS PLACEHOLDER AT RELEASE TIME with the actual SHA256 of the published wheel.
# Compute on macOS/Linux: shasum -a 256 nucleus_data-0.2.0-py3-none-any.whl
# Compute on Windows:     (Get-FileHash nucleus_data-0.2.0-py3-none-any.whl -Algorithm SHA256).Hash
$wheelChecksum = '0000000000000000000000000000000000000000000000000000000000000000'

# Get-ChocolateyWebFile validates checksum if -Checksum / -ChecksumType supplied.
# Docs: https://docs.chocolatey.org/en-us/create/functions/get-chocolateywebfile
Get-ChocolateyWebFile `
    -PackageName  $packageId `
    -FileFullPath $wheelDest `
    -Url          $wheelUrl `
    -Checksum     $wheelChecksum `
    -ChecksumType 'sha256'

# ----------------------------------------------------------------------------
# 4. Install the wheel.
# ----------------------------------------------------------------------------
Write-Host "NUCLEUS-INSTALL: upgrading pip in venv"
& $venvPython -m pip install --no-warn-script-location --upgrade pip
if ($LASTEXITCODE -ne 0) { throw "NUCLEUS-INSTALL: pip upgrade failed" }

Write-Host "NUCLEUS-INSTALL: installing nucleus-data $pkgVersion into venv"
& $venvPython -m pip install --no-warn-script-location $wheelDest
if ($LASTEXITCODE -ne 0) { throw "NUCLEUS-INSTALL: pip install of wheel failed" }

# Drop the wheel after install — saves ~5 MB and prevents stale artefacts.
Remove-Item -Force $wheelDest

# ----------------------------------------------------------------------------
# 5. Shim nucleus.exe onto PATH.
# ----------------------------------------------------------------------------
# Docs: https://docs.chocolatey.org/en-us/create/functions/install-binfile
if (-not (Test-Path $venvNucleus)) {
    throw "NUCLEUS-INSTALL: nucleus.exe was not produced inside the venv. " +
          "Most likely cause: pip install succeeded but the [project.scripts] entry-point did not register."
}

Install-BinFile -Name 'nucleus' -Path $venvNucleus

# ----------------------------------------------------------------------------
# 6. Smoke test — fail loudly if the entry point doesn't run.
# ----------------------------------------------------------------------------
Write-Host "NUCLEUS-INSTALL: smoke testing nucleus --version"
$smoke = & $venvNucleus --version 2>&1
if ($LASTEXITCODE -ne 0) {
    throw "NUCLEUS-INSTALL: nucleus --version failed: $smoke"
}
Write-Host "NUCLEUS-INSTALL: smoke OK ($smoke)"
