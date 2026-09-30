@echo off
cd /d "%~dp0"
if not exist "dist\RH Facil\RH Facil.exe" (
    echo O executavel ainda nao foi gerado.
    echo Execute primeiro: 1_GERAR_EXECUTAVEL.bat
    pause
    exit /b 1
)
start "" "dist\RH Facil\RH Facil.exe"
