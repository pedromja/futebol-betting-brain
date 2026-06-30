# Liga a SindGreenMentor na rede local (PC + telemóvel)
$ErrorActionPreference = "Stop"
$Root = Split-Path $PSScriptRoot -Parent
$Py = "C:\Users\pedro\AppData\Local\Programs\Python\Python312\python.exe"
$Port = 8765
$WebDevPort = 18765

Set-Location $Root

function Get-ListenerCmd([int]$p) {
    $conn = Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $conn) { return $null }
    return (Get-CimInstance Win32_Process -Filter "ProcessId=$($conn.OwningProcess)" -ErrorAction SilentlyContinue).CommandLine
}

# Carrega .env (login, API keys, etc.)
$envFile = Join-Path $Root ".env"
if (Test-Path $envFile) {
    Get-Content $envFile | ForEach-Object {
        if ($_ -match '^\s*([^#=]+)=(.*)$') {
            $k = $matches[1].Trim()
            $v = $matches[2].Trim().Trim('"').Trim("'")
            if ($k) { Set-Item -Path "Env:$k" -Value $v }
        }
    }
}
if (-not $env:AUTH_ENABLED) { $env:AUTH_ENABLED = "1" }

# Regra de firewall (só cria se não existir)
$ruleName = "SindGreenMentor PWA $Port"
if (-not (Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue)) {
    New-NetFirewallRule -DisplayName $ruleName -Direction Inbound -Action Allow -Protocol TCP -LocalPort $Port | Out-Null
}

$ip = (Get-NetIPAddress -AddressFamily IPv4 |
    Where-Object { $_.IPAddress -notlike "127.*" -and $_.PrefixOrigin -eq "Dhcp" } |
    Select-Object -First 1).IPAddress
$profile = Get-NetConnectionProfile -ErrorAction SilentlyContinue | Select-Object -First 1

$listener8765 = Get-ListenerCmd $Port
if ($listener8765 -match "SindGreenMentor\.exe") {
    Write-Host ""
    Write-Host "  AVISO: SindGreenMentor.exe ocupa a porta $Port com UI EMPACOTADA (pode estar desactualizada)." -ForegroundColor Red
    Write-Host "  Para a versao WEB mais recente no telemovel:" -ForegroundColor Yellow
    Write-Host "    1) Fecha o .exe e volta a correr este script, OU" -ForegroundColor Yellow
    Write-Host "    2) Usa http://TEU-IP:${WebDevPort}/ (serve_auth_forever.py)" -ForegroundColor Yellow
    Write-Host ""
}

Write-Host ""
Write-Host "  SindGreenMentor — servidor WEB a ligar (web/static ao vivo)..." -ForegroundColor Green
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

& $Py (Join-Path $Root "scripts\run_pwa_server.py")