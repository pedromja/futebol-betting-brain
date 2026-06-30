# Copia chaves do .env local para o servico Render (API_FOOTBALL_KEY, etc.)
param(
    [string]$ServiceName = "futebol-betting-brain"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path $PSScriptRoot -Parent
$EnvFile = Join-Path $Root ".env"

function Read-DotEnv([string]$Path) {
    $vars = @{}
    if (-not (Test-Path $Path)) { return $vars }
    Get-Content $Path | ForEach-Object {
        $line = $_.Trim()
        if (-not $line -or $line.StartsWith("#")) { return }
        $idx = $line.IndexOf("=")
        if ($idx -lt 1) { return }
        $key = $line.Substring(0, $idx).Trim()
        $val = $line.Substring($idx + 1).Trim().Trim('"').Trim("'")
        if ($key) { $vars[$key] = $val }
    }
    return $vars
}

$local = Read-DotEnv $EnvFile
$apiKey = $env:RENDER_API_KEY
if (-not $apiKey) { $apiKey = $local["RENDER_API_KEY"] }
if (-not $apiKey) {
    Write-Host ""
    Write-Host "  Falta RENDER_API_KEY." -ForegroundColor Red
    Write-Host "  1. https://dashboard.render.com/u/settings#api-keys"
    Write-Host "  2. Cria API Key e adiciona ao .env: RENDER_API_KEY=..."
    Write-Host "  3. Volta a correr este script"
    Write-Host ""
    exit 1
}

$headers = @{
    Authorization = "Bearer $apiKey"
    Accept        = "application/json"
    "Content-Type" = "application/json"
}

Write-Host ""
Write-Host "  Render sync - $ServiceName" -ForegroundColor Green

$services = Invoke-RestMethod -Uri "https://api.render.com/v1/services?name=$ServiceName" -Headers $headers -Method Get
$service = $services | Select-Object -First 1
if (-not $service -or -not $service.service) {
    Write-Host "  Servico '$ServiceName' nao encontrado no Render." -ForegroundColor Red
    exit 1
}

$serviceId = $service.service.id
$siteUrl = $service.service.serviceDetails.url
Write-Host "  ID: $serviceId"
if ($siteUrl) { Write-Host "  URL: $siteUrl" -ForegroundColor Cyan }

$fromEnv = @(
    "API_FOOTBALL_KEY",
    "OPENWEATHERMAP_API_KEY",
    "FOOTBALL_DATA_API_KEY",
    "XAI_API_KEY",
    "AUTH_ENABLED",
    "AUTH_USERNAME",
    "AUTH_PASSWORD",
    "AUTH_SECRET",
    "AUTH_ADMIN2_USERNAME",
    "AUTH_ADMIN2_PASSWORD"
)
$static = @{
    DATA_DIR        = "/var/data"
    PUBLIC_SITE_URL = "https://futebol-betting-brain.onrender.com"
}
if (-not $local["AUTH_ENABLED"]) { $static["AUTH_ENABLED"] = "1" }
$synced = 0
foreach ($key in $fromEnv) {
    $value = $local[$key]
    if (-not $value) { continue }
    $body = @{ value = $value } | ConvertTo-Json
    Invoke-RestMethod -Uri "https://api.render.com/v1/services/$serviceId/env-vars/$key" -Headers $headers -Method Put -Body $body | Out-Null
    Write-Host "  OK $key" -ForegroundColor Yellow
    $synced++
}
foreach ($entry in $static.GetEnumerator()) {
    $body = @{ value = $entry.Value } | ConvertTo-Json
    Invoke-RestMethod -Uri "https://api.render.com/v1/services/$serviceId/env-vars/$($entry.Key)" -Headers $headers -Method Put -Body $body | Out-Null
    Write-Host "  OK $($entry.Key) = $($entry.Value)" -ForegroundColor Yellow
    $synced++
}

if ($synced -eq 0) {
    Write-Host "  Nenhuma chave encontrada no .env para sincronizar." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "  Chaves enviadas. O Render reinicia o servico automaticamente." -ForegroundColor Green
if ($siteUrl) {
    Write-Host "  Testa: $siteUrl/health"
}
Write-Host ""