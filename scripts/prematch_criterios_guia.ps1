# Guia interativo dos critérios pré-jogo
$Root = Split-Path $PSScriptRoot -Parent
$Py = "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe"
if (-not (Test-Path $Py)) { $Py = "python" }
& $Py "$Root\scripts\prematch_criterios_guia.py" @args