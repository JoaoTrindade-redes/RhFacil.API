@echo off
cd /d "%~dp0"
echo Isto apaga apenas arquivos de COMPILACAO.
echo Nao apaga o codigo-fonte nem o banco incluido no kit.
echo.
pause
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist .venv_build rmdir /s /q .venv_build
if exist "RH_Facil_v0.3.7_Portatil_Windows_x64.zip" del /q "RH_Facil_v0.3.7_Portatil_Windows_x64.zip"
echo Limpeza concluida.
pause
