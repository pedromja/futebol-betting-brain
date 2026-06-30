@echo off
title Betting Brain - servidor local
cd /d "%~dp0.."
set AUTH_ENABLED=1
set AUTH_USERNAME=admin
set AUTH_PASSWORD=testadmin123
set AUTH_SECRET=live-test-secret-2026
set DATA_DIR=%cd%\data\auth_live_test
echo.
echo  Servidor: http://127.0.0.1:18765
echo  Admin:    admin / testadmin123
echo.
"C:\Users\pedro\AppData\Local\Programs\Python\Python312\python.exe" scripts\serve_auth_forever.py
pause