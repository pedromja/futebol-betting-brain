# Abre o Render para deploy via Blueprint (render.yaml)
$ErrorActionPreference = "Stop"

$Repo = "pedromja/futebol-betting-brain"
$BlueprintUrl = "https://dashboard.render.com/blueprints/new"
$RepoUrl = "https://github.com/$Repo"

Write-Host ""
Write-Host "  Render - SindGreenMentor" -ForegroundColor Green
Write-Host "  Repo: $RepoUrl"
Write-Host ""
Write-Host "  Passos:" -ForegroundColor Cyan
Write-Host "  1. Login com GitHub em render.com (se ainda nao tiveres conta)"
Write-Host "  2. New -> Blueprint -> Connect $Repo"
Write-Host "  3. Deploy Blueprint (cria servico sindgreen-mentor)"
Write-Host "  4. Environment -> API_FOOTBALL_KEY = (tua chave)"
Write-Host "  5. Abre o link no telemovel -> Adicionar ao ecra principal"
Write-Host ""
Write-Host "  A abrir o painel Render..." -ForegroundColor Yellow
Start-Process $BlueprintUrl
Write-Host "  Se o browser nao abrir: $BlueprintUrl"
Write-Host ""