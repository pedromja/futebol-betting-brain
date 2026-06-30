# Configura XAI_API_KEY no Render (IA live autónoma)
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
$xai = $local["XAI_API_KEY"]
if (-not $xai) {
    Write-Host "  Falta XAI_API_KEY no .env" -ForegroundColor Red
    Write-Host "  Obtem em https://console.x.ai/team/default/api-keys"
    exit 1
}

$renderKey = $env:RENDER_API_KEY
if (-not $renderKey) { $renderKey = $local["RENDER_API_KEY"] }
if ($renderKey) {
    & (Join-Path $PSScriptRoot "render_sync_env.ps1") -ServiceName "futebol-betting-brain"
    exit $LASTEXITCODE
}

Write-Host ""
Write-Host "  XAI_API_KEY no Render (manual)" -ForegroundColor Green
Write-Host "  1. https://dashboard.render.com -> futebol-betting-brain -> Environment"
Write-Host "  2. Add Environment Variable"
Write-Host "       Key:   XAI_API_KEY"
Write-Host "  3. Cola o valor (ja na area de transferencia) e Save Changes"
Write-Host ""
Write-Host "  Nota: a chave xAI precisa de creditos/licenca em https://console.x.ai"
Write-Host ""

try {
    Set-Clipboard -Value $xai
    Write-Host "  XAI_API_KEY copiada para a area de transferencia." -ForegroundColor Cyan
} catch {
    Write-Host "  Copia manualmente do .env local." -ForegroundColor Yellow
}

try {
    Start-Process "https://dashboard.render.com" | Out-Null
} catch {}