<#
.SYNOPSIS
Installs the local web application without VieNeu's optional demo UI.
#>

param(
    [string]$Python = "python"
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot

& $Python -m pip install -r (Join-Path $projectRoot "requirements.txt")
# VieNeu 3.8.3 declares a dependency used only by its demo application. This
# project calls the offline SDK directly, so avoid installing that unused UI.
& $Python -m pip install --no-deps "vieneu==3.8.3"
