param(
    [switch]$Clean
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

if ($Clean) {
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue (Join-Path $root 'build')
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue (Join-Path $root 'dist')
}

$venvPython = Join-Path $root '.venv\Scripts\python.exe'
$python = if (Test-Path $venvPython) { $venvPython } else { 'python' }
& $python -m PyInstaller --noconfirm --clean installer.spec
Write-Host "Bộ chạy nằm tại: $root\dist\PhatThanhAI"
