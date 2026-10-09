# Instalador de study-agent para Windows (PowerShell 5.1+).
#   irm https://raw.githubusercontent.com/byrogr/azure-study-agent/main/install.ps1 | iex
#
# Variables opcionales:
#   $env:STUDY_AGENT_VERSION      version a instalar, p. ej. v0.2.0 (por defecto, la ultima)
#   $env:STUDY_AGENT_INSTALL_DIR  carpeta destino (por defecto %LOCALAPPDATA%\Programs\study-agent)
#   $env:STUDY_AGENT_BASE_URL     origen de los binarios (por defecto, GitHub Releases)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

$Repo = 'byrogr/azure-study-agent'
$Version = if ($env:STUDY_AGENT_VERSION) { $env:STUDY_AGENT_VERSION } else { 'latest' }
$InstallDir = if ($env:STUDY_AGENT_INSTALL_DIR) { $env:STUDY_AGENT_INSTALL_DIR } else { Join-Path $env:LOCALAPPDATA 'Programs\study-agent' }

if (-not [Environment]::Is64BitOperatingSystem) { throw 'study-agent requiere Windows de 64 bits.' }
$Asset = 'study-agent-windows-x64.exe'   # en Windows ARM funciona mediante emulacion x64

if ($env:STUDY_AGENT_BASE_URL) { $Base = $env:STUDY_AGENT_BASE_URL }
elseif ($Version -eq 'latest') { $Base = "https://github.com/$Repo/releases/latest/download" }
else { $Base = "https://github.com/$Repo/releases/download/$Version" }

New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
$Exe = Join-Path $InstallDir 'study-agent.exe'
$Tmp = "$Exe.download"

Write-Host "Descargando $Asset ($Version)..."
Invoke-WebRequest -UseBasicParsing -Uri "$Base/$Asset" -OutFile $Tmp
$Expected = $null
try {
    Invoke-WebRequest -UseBasicParsing -Uri "$Base/$Asset.sha256" -OutFile "$Tmp.sha256"
    $Expected = ((Get-Content -Raw "$Tmp.sha256").Trim() -split '\s+')[0]
} catch { }  # release sin checksum
Remove-Item -ErrorAction SilentlyContinue "$Tmp.sha256"
if ($Expected -and ($Expected -ne (Get-FileHash -Algorithm SHA256 $Tmp).Hash)) {
    Remove-Item $Tmp
    throw 'checksum SHA-256 incorrecto'
}
Move-Item -Force $Tmp $Exe

$UserPath = [Environment]::GetEnvironmentVariable('Path', 'User')
if (($UserPath -split ';') -notcontains $InstallDir) {
    [Environment]::SetEnvironmentVariable('Path', "$InstallDir;$UserPath", 'User')
    $env:Path = "$InstallDir;$env:Path"
    Write-Host "Agregado $InstallDir a tu PATH de usuario (abre una terminal nueva para usarlo)."
}

Write-Host "Instalado: $Exe ($(& $Exe --version))"
if (-not (Get-Command claude -ErrorAction SilentlyContinue)) {
    Write-Host ''
    Write-Host 'Falta Claude Code, que study-agent usa con tu suscripcion. Instalalo e inicia sesion:'
    Write-Host '    irm https://claude.ai/install.ps1 | iex; claude'
}
Write-Host ''
Write-Host 'Siguiente paso: study-agent init'
