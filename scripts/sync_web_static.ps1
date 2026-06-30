# Copia UI web (fonte) para o bundle desktop — sem rebuild completo
$ErrorActionPreference = "Stop"
$Root = Split-Path $PSScriptRoot -Parent
$StaticSrc = Join-Path $Root "web\static"
$StaticDst = Join-Path $Root "dist\SindGreenMentor\_internal\web\static"
$BrandingSrc = Join-Path $Root "web\branding.json"
$BrandingDst = Join-Path $Root "dist\SindGreenMentor\_internal\web\branding.json"

if (-not (Test-Path $StaticSrc)) {
    Write-Error "Nao encontrado: $StaticSrc"
}

if (-not (Test-Path $StaticDst)) {
    Write-Host "AVISO: dist ainda nao compilado ($StaticDst). Corre build_desktop.ps1 primeiro." -ForegroundColor Yellow
    exit 1
}

Copy-Item "$StaticSrc\*" $StaticDst -Recurse -Force
if (Test-Path $BrandingSrc) {
    Copy-Item $BrandingSrc $BrandingDst -Force
}

Write-Host "UI sincronizada: web/static -> dist/_internal/web/static" -ForegroundColor Green
Write-Host "Reinicia SindGreenMentor.exe se estiver aberto." -ForegroundColor Yellow