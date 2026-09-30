@echo off
setlocal EnableExtensions
chcp 65001 >nul
title RH Facil - Gerar Executavel Offline

cd /d "%~dp0"

echo ============================================================
echo          RH FACIL v0.3.7 - COMPILACAO WINDOWS x64
echo ============================================================
echo.
echo Este processo cria uma versao AUTONOMA do RH Facil.
echo O notebook onde o programa sera usado NAO precisara de Python.
echo.
echo Pasta de saida:
echo   dist\RH Facil\
echo.

where py >nul 2>&1
if %errorlevel%==0 (
    set "PYTHON_CMD=py -3"
) else (
    where python >nul 2>&1
    if %errorlevel% neq 0 (
        echo [ERRO] Python nao foi encontrado neste computador.
        echo.
        echo Instale Python 3.11 ou 3.12 de 64 bits neste PC de compilacao
        echo e marque a opcao "Add Python to PATH".
        echo Depois execute este arquivo novamente.
        echo.
        pause
        exit /b 1
    )
    set "PYTHON_CMD=python"
)

echo [1/7] Verificando Python...
%PYTHON_CMD% -c "import sys,struct; print('Python:',sys.version); print('Arquitetura:',struct.calcsize('P')*8,'bits'); raise SystemExit(0 if struct.calcsize('P')*8==64 else 1)"
if %errorlevel% neq 0 (
    echo.
    echo [ERRO] Use Python de 64 bits para gerar o executavel.
    pause
    exit /b 1
)

echo.
echo [2/7] Criando ambiente de compilacao...
if not exist ".venv_build\Scripts\python.exe" (
    %PYTHON_CMD% -m venv .venv_build
    if %errorlevel% neq 0 goto :failure
)

set "VPY=.venv_build\Scripts\python.exe"

echo.
echo [3/7] Atualizando pip...
"%VPY%" -m pip install --upgrade pip setuptools wheel
if %errorlevel% neq 0 goto :failure

echo.
echo [4/7] Instalando dependencias de compilacao...
"%VPY%" -m pip install -r requirements-build.txt
if %errorlevel% neq 0 goto :failure

echo.
echo [5/7] Limpando compilacoes antigas...
if exist build rmdir /s /q build
if exist "dist\RH Facil" rmdir /s /q "dist\RH Facil"

echo.
echo [6/7] Gerando RH Facil.exe...
"%VPY%" -m PyInstaller --noconfirm --clean RH_Facil.spec
if %errorlevel% neq 0 goto :failure

if not exist "dist\RH Facil\RH Facil.exe" (
    echo [ERRO] O PyInstaller terminou, mas o executavel nao foi encontrado.
    goto :failure
)

echo.
echo [7/7] Criando pacote de entrega...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ErrorActionPreference='Stop';" ^
  "$src=Join-Path (Get-Location) 'dist\RH Facil';" ^
  "$zip=Join-Path (Get-Location) 'RH_Facil_v0.3.7_Portatil_Windows_x64.zip';" ^
  "if(Test-Path $zip){Remove-Item $zip -Force};" ^
  "Compress-Archive -Path $src -DestinationPath $zip -CompressionLevel Optimal"

if %errorlevel% neq 0 goto :failure

echo.
echo ============================================================
echo                COMPILACAO CONCLUIDA
echo ============================================================
echo.
echo TESTE neste computador:
echo   dist\RH Facil\RH Facil.exe
echo.
echo ARQUIVO PARA COPIAR AO NOTEBOOK DELA:
echo   RH_Facil_v0.3.7_Portatil_Windows_x64.zip
echo.
echo IMPORTANTE:
echo - No notebook dela, extraia o ZIP inteiro.
echo - Nao copie apenas o EXE.
echo - Abra "RH Facil.exe" dentro da pasta extraida.
echo - Nao precisa instalar Python.
echo - A primeira abertura NAO baixa Python nem componentes.
echo - A v0.3.7 inclui o componente de atualizacao automatica.
echo.
pause
exit /b 0

:failure
echo.
echo ============================================================
echo                  FALHA NA COMPILACAO
echo ============================================================
echo.
echo Veja as mensagens acima.
echo Se precisar, envie uma foto da tela ou o arquivo build_log.txt.
echo.
pause
exit /b 1
