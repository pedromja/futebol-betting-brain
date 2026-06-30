# PWA com HTTPS (Cloudflare) — mesma app que http://IP:8765 mas com cadeado
$ErrorActionPreference = "Stop"
$Root = Split-Path $PSScriptRoot -Parent
$Py = "C:\Users\pedro\AppData\Local\Programs\Python\Python312\python.exe"
$Port = 8765
$Cloudflared = Join-Path $PSScriptRoot "cloudflared.exe"

Set-Location $Root

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

if (-not (Test-Path $Cloudflared)) {
    Write-Host "A transferir cloudflared..." -ForegroundColor Yellow
    $url = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe"
    Invoke-WebRequest -Uri $url -OutFile $Cloudflared
}

$listening = netstat -ano | findstr "LISTENING" | findstr ":$Port "
if (-not $listening) {
    Write-Host "A ligar servidor web local (porta $Port)..." -ForegroundColor Green
    Start-Process -FilePath $Py -ArgumentList (Join-Path $Root "scripts\run_pwa_server.py") -WindowStyle Minimized
    Start-Sleep -Seconds 4
}

$ip = (Get-NetIPAddress -AddressFamily IPv4 |
    Where-Object { $_.IPAddress -notlike "127.*" -and $_.PrefixOrigin -eq "Dhcp" } |
    Select-Object -First 1).IPAddress

Write-Host ""
Write-Host "  SindGreenMentor — modo SEGURO (HTTPS)" -ForegroundColor Green
Write-Host "  Local (sem cadeado): http://${ip}:$Port/" -ForegroundColor DarkGray
Write-Host ""
Write-Host "  Copia o URL https://....trycloudflare.com que aparece abaixo" -ForegroundColor Yellow
Write-Host "  Esse e o link SEGURO para o telemovel (Wi-Fi ou 4G)" -ForegroundColor Yellow
Write-Host "  Deixa esta janela aberta. Ctrl+C para parar." -ForegroundColor DarkGray
Write-Host ""

& $Cloudflared tunnel --url "http://127.0.0.1:$Port"