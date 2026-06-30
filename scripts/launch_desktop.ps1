# Abre SindGreenMentor em janela desktop (modo dev, sem compilar)
$ErrorActionPreference = "Stop"
$Root = Split-Path $PSScriptRoot -Parent
$Py = "C:\Users\pedro\AppData\Local\Programs\Python\Python312\python.exe"

Set-Location $Root
& $Py -m pip install pywebview -q
& $Py desktop\launcher.py