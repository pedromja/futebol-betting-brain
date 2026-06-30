# Compila SindGreenMentor Pro Desktop (Windows)
$ErrorActionPreference = "Stop"
$Root = Split-Path $PSScriptRoot -Parent
$Py = "C:\Users\pedro\AppData\Local\Programs\Python\Python312\python.exe"

Set-Location $Root

Write-Host ""
Write-Host "  SindGreenMentor Pro - build desktop" -ForegroundColor Green
Write-Host ""

& $Py -m pip install -r requirements-desktop.txt -q

$IconJpg = Join-Path $Root "web\static\icons\icon-512.jpg"
$IconIco = Join-Path $Root "desktop\app.ico"
if ((Test-Path $IconJpg) -and -not (Test-Path $IconIco)) {
    & $Py -c "from PIL import Image; Image.open(r'$IconJpg').save(r'$IconIco', format='ICO', sizes=[(256,256),(128,128),(64,64),(32,32),(16,16)])"
}

$Dist = Join-Path $Root "dist\SindGreenMentor"
$ExeName = "SindGreenMentor"

# Fechar app se estiver aberta (bloqueia DLLs em dist)
Get-Process -Name $ExeName -ErrorAction SilentlyContinue | ForEach-Object {
    Write-Host "  A fechar $($ExeName).exe (PID $($_.Id))..." -ForegroundColor Yellow
    Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
}
Start-Sleep -Seconds 2

if (Test-Path $Dist) {
    try {
        Remove-Item $Dist -Recurse -Force
    } catch {
        Write-Host "  AVISO: nao foi possivel apagar dist (app ainda aberta?)." -ForegroundColor Yellow
        Write-Host "  A sincronizar apenas ficheiros web..." -ForegroundColor Yellow
        $StaticSrc = Join-Path $Root "web\static"
        $StaticDst = Join-Path $Dist "_internal\web\static"
        if (Test-Path $StaticDst) {
            Copy-Item "$StaticSrc\*" $StaticDst -Recurse -Force
            Write-Host "  UI actualizada em $StaticDst" -ForegroundColor Cyan
            Write-Host "  Reinicia SindGreenMentor.exe para ver alteracoes." -ForegroundColor Yellow
            exit 0
        }
        throw
    }
}

& $Py -m PyInstaller desktop\SindGreenMentor.spec --noconfirm

$EnvExample = Join-Path $Root ".env.example"
$EnvTarget = Join-Path $Dist ".env.example"
if (Test-Path $EnvExample) {
    Copy-Item $EnvExample $EnvTarget -Force
} else {
    "API_FOOTBALL_KEY=`nTHE_ODDS_API_KEY=`nFOOTBALL_DATA_API_KEY=`nOPENWEATHERMAP_API_KEY=" | Set-Content -Path $EnvTarget -Encoding UTF8
}

$Readme = Join-Path $Dist "LEIA-ME.txt"
$lines = @(
    "SindGreenMentor Pro - Desktop",
    "=============================",
    "",
    "1. Copia .env.example para .env na mesma pasta do .exe",
    "2. Preenche as API keys",
    "3. Executa SindGreenMentor.exe",
    "",
    "Os dados ficam em .\data\"
)
$lines | Set-Content -Path $Readme -Encoding UTF8

Write-Host ""
Write-Host "  Concluido: $Dist\SindGreenMentor.exe" -ForegroundColor Cyan
Write-Host "  Copia .env para a pasta dist antes de usar." -ForegroundColor Yellow
Write-Host ""