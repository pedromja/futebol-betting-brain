# Cria repo no GitHub (se nao existir) e envia o codigo
param(
    [Parameter(Mandatory = $true)]
    [string]$GitHubUser,

    [string]$RepoName = "futebol-betting-brain"
)

$ErrorActionPreference = "Stop"
$git = "C:\Program Files\Git\cmd\git.exe"
$gh = "C:\Program Files\GitHub CLI\gh.exe"
if (-not (Test-Path $git)) { $git = "git" }
if (-not (Test-Path $gh)) { $gh = "gh" }

$Root = Split-Path $PSScriptRoot -Parent
Set-Location $Root

Write-Host ""
Write-Host "  GitHub — SindGreenMentor" -ForegroundColor Green
Write-Host "  User: $GitHubUser / Repo: $RepoName"
Write-Host ""

# 1) Login GitHub (abre browser — so uma vez)
$authOk = $false
try {
    & $gh auth status 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) { $authOk = $true }
} catch {}

if (-not $authOk) {
    Write-Host "  Passo 1: Login no GitHub (vai abrir o browser)..." -ForegroundColor Yellow
    & $gh auth login -h github.com -p https -w
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  Login cancelado. Tenta outra vez." -ForegroundColor Red
        exit 1
    }
}

# 2) Garantir git local
if (-not (Test-Path ".git")) {
    & $git init
}
& $git branch -M main

# 3) Commit pendente
& $git add -A
if (Test-Path ".env") { & $git rm --cached -f .env 2>$null }
$porcelain = & $git status --porcelain
if ($porcelain) {
    & $git commit -m "Actualizacao SindGreenMentor $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
}

# 4) Criar repo remoto se nao existir + push
Write-Host "  Passo 2: Criar repo e enviar codigo..." -ForegroundColor Cyan
& $gh repo create "$GitHubUser/$RepoName" --public --source=. --remote=origin --push

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "  FEITO!" -ForegroundColor Green
    Write-Host "  https://github.com/$GitHubUser/$RepoName"
    Write-Host ""
    Write-Host "  Seguinte: Render.com -> New Web Service -> Docker -> este repo" -ForegroundColor Yellow
    Write-Host ""
} else {
    Write-Host "  Se o repo ja existir, tenta:" -ForegroundColor Yellow
    Write-Host "  git remote add origin https://github.com/$GitHubUser/$RepoName.git"
    Write-Host "  git push -u origin main"
}