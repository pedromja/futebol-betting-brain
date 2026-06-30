# Guia rapido: API_FOOTBALL_KEY no Render
$ErrorActionPreference = "Stop"
$Root = Split-Path $PSScriptRoot -Parent
$EnvFile = Join-Path $Root ".env"

Write-Host ""
Write-Host "  API_FOOTBALL_KEY no Render" -ForegroundColor Green
Write-Host ""

if (Test-Path $EnvFile) {
    $hasKey = Select-String -Path $EnvFile -Pattern "^API_FOOTBALL_KEY=.+$" -Quiet
    if ($hasKey) {
        Write-Host "  OK: API_FOOTBALL_KEY encontrada no .env local" -ForegroundColor Cyan
    } else {
        Write-Host "  AVISO: API_FOOTBALL_KEY vazia no .env" -ForegroundColor Yellow
    }
} else {
    Write-Host "  AVISO: ficheiro .env nao encontrado" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "  Passos no browser:" -ForegroundColor Yellow
Write-Host "  1. Abre dashboard.render.com e faz login"
Write-Host "  2. Clica no servico: futebol-betting-brain"
Write-Host "  3. Menu esquerdo: Environment"
Write-Host "  4. Add Environment Variable"
Write-Host "       Key:   API_FOOTBALL_KEY"
Write-Host "       Value: (copia do teu .env local)"
Write-Host "  5. Save Changes e espera o redeploy (~2 min)"
Write-Host ""
Write-Host "  Teste: https://futebol-betting-brain.onrender.com/health"
Write-Host "         (deve mostrar api_football: true)"
Write-Host ""

$urls = @(
    "https://dashboard.render.com",
    "https://futebol-betting-brain.onrender.com/health"
)
foreach ($url in $urls) {
    try {
        Start-Process $url | Out-Null
    } catch {
        Write-Host "  Abre manualmente: $url"
    }
}

# Mostrar valor para copiar (so no PC do utilizador)
if (Test-Path $EnvFile) {
    $line = Get-Content $EnvFile | Where-Object { $_ -match "^API_FOOTBALL_KEY=" } | Select-Object -First 1
    if ($line -match "^API_FOOTBALL_KEY=(.+)$") {
        Write-Host "  Valor para colar no Render (copia isto):" -ForegroundColor Cyan
        Write-Host "  $($Matches[1])"
        Write-Host ""
        try {
            Set-Clipboard -Value $Matches[1]
            Write-Host "  (ja copiado para a area de transferencia)" -ForegroundColor Green
        } catch {}
    }
}