# Liga a SindGreenMentor na rede local (PC + telemóvel)
$ErrorActionPreference = "Stop"
$Root = Split-Path $PSScriptRoot -Parent
$Py = "C:\Users\pedro\AppData\Local\Programs\Python\Python312\python.exe"
$Port = 8765

Set-Location $Root

# Regra de firewall (só cria se não existir)
$ruleName = "SindGreenMentor PWA $Port"
if (-not (Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue)) {
    New-NetFirewallRule -DisplayName $ruleName -Direction Inbound -Action Allow -Protocol TCP -LocalPort $Port | Out-Null
}

$ip = (Get-NetIPAddress -AddressFamily IPv4 |
    Where-Object { $_.IPAddress -notlike "127.*" -and $_.PrefixOrigin -eq "Dhcp" } |
    Select-Object -First 1).IPAddress
$profile = Get-NetConnectionProfile -ErrorAction SilentlyContinue | Select-Object -First 1

Write-Host ""
Write-Host "  SindGreenMentor — servidor a ligar..." -ForegroundColor Green
Write-Host "  Tabs: Pre-jogo + Ao Vivo (odds in-play, auto-refresh 45s)" -ForegroundColor Cyan
Write-Host "  PC:        http://127.0.0.1:$Port/"
if ($ip) {
    Write-Host "  Telemóvel: http://${ip}:$Port/" -ForegroundColor Yellow
}
if ($profile.Name -match "POCO|iPhone|Galaxy|Hotspot|Android") {
    Write-Host ""
    Write-Host "  AVISO: PC ligado ao hotspot do telemovel." -ForegroundColor Red
    Write-Host "  Muitos telemoveis NAO conseguem abrir o PC nesta rede."
    Write-Host "  Usa em vez: .\scripts\start_pwa_tunnel.ps1" -ForegroundColor Yellow
}
Write-Host "  (deixa esta janela aberta; Ctrl+C para parar)"
Write-Host ""

& $Py -m uvicorn web.api.server:app --host 0.0.0.0 --port $Port