# Expoe a SindGreenMentor na internet temporariamente (telefone em qualquer rede)
$ErrorActionPreference = "Stop"
$Root = Split-Path $PSScriptRoot -Parent
$Py = "C:\Users\pedro\AppData\Local\Programs\Python\Python312\python.exe"
$Port = 8765
$Cloudflared = Join-Path $PSScriptRoot "cloudflared.exe"

Set-Location $Root

if (-not (Test-Path $Cloudflared)) {
    Write-Host "A transferir cloudflared..." -ForegroundColor Yellow
    $url = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe"
    Invoke-WebRequest -Uri $url -OutFile $Cloudflared
}

$listening = netstat -ano | findstr "LISTENING" | findstr ":$Port "
if (-not $listening) {
    Write-Host "A ligar servidor local..." -ForegroundColor Green
    Start-Process -FilePath $Py -ArgumentList "-m","uvicorn","web.api.server:app","--host","127.0.0.1","--port",$Port -WindowStyle Minimized
    Start-Sleep -Seconds 4
}

Write-Host ""
Write-Host "  A criar tunel publico..." -ForegroundColor Green
Write-Host "  Copia o URL https://....trycloudflare.com que aparecer abaixo"
Write-Host "  Cola no telemovel (4G, Wi-Fi ou hotspot)"
Write-Host "  Ctrl+C para parar"
Write-Host ""

& $Cloudflared tunnel --url "http://127.0.0.1:$Port"