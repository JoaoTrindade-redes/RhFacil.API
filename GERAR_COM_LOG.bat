@echo off
cd /d "%~dp0"
echo Iniciando compilacao com log...
call "1_GERAR_EXECUTAVEL.bat" > build_log.txt 2>&1
echo.
echo Log salvo em:
echo %~dp0build_log.txt
echo.
notepad build_log.txt
