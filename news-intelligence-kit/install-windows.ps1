# News Intelligence Kit — Windows bootstrap (WSL2 + Docker)
param([switch]$Repair)

$ErrorActionPreference = "Stop"

if ($env:WSL_DISTRO_NAME) {
    Write-Host "Already inside WSL. Run: cd ~/news-intelligence-kit && ./install.sh"
    exit 0
}

$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "Re-launching as Administrator..."
    Start-Process powershell -Verb RunAs -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`""
    exit
}

Write-Host "Checking WSL..."
$wslConfig = "$env:USERPROFILE\.wslconfig"
if (-not (Test-Path $wslConfig)) {
    @"
[wsl2]
memory=12GB
processors=4
swap=8GB
"@ | Set-Content -Path $wslConfig -Encoding UTF8
    Write-Host "Wrote default .wslconfig (12GB RAM) — reboot WSL if needed: wsl --shutdown"
}

$wsl = Get-Command wsl -ErrorAction SilentlyContinue
if (-not $wsl) {
    Write-Host "Installing WSL + Ubuntu..."
    wsl --install -d Ubuntu
    Write-Host "REBOOT REQUIRED. After reboot, run INSTALL-WINDOWS.bat again."
    exit 301
}

$distro = (wsl -l -v 2>$null | Select-String Ubuntu)
if (-not $distro) {
    wsl --install -d Ubuntu
    Write-Host "REBOOT REQUIRED. After reboot, run INSTALL-WINDOWS.bat again."
    exit 301
}

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host "Installing Docker Desktop via winget..."
    winget install -e --id Docker.DockerDesktop --accept-package-agreements --accept-source-agreements
    Write-Host "Start Docker Desktop, then run this script again."
    exit 0
}

$kitWin = Split-Path -Parent $MyInvocation.MyCommand.Path
$kitWsl = "~/news-intelligence-kit"
if ($kitWin -match "^[A-Za-z]:\\") {
    $drive = $kitWin.Substring(0,1).ToLower()
    $rest = $kitWin.Substring(2) -replace '\\','/'
    $winPath = "/mnt/$drive$rest"
    wsl -d Ubuntu -- bash -lc "mkdir -p ~ && rsync -a '$winPath/' '$kitWsl/' 2>/dev/null || cp -a '$winPath' ~/"
} else {
    wsl -d Ubuntu -- bash -lc "mkdir -p ~"
}

if ($Repair) {
    wsl -d Ubuntu -- bash -lc "cd $kitWsl && ./scripts/repair.sh"
} else {
    wsl -d Ubuntu -- bash -lc "cd $kitWsl && chmod +x install.sh scripts/*.sh && ./install.sh --from-windows-bootstrap"
}

Start-Process "http://localhost:8080/setup/"
Write-Host "Done. Setup UI should open in browser."
