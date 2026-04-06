@echo off
REM Auto Claude - Script batch para Windows
REM Executa o auto_claude.py monitorando o horário limite da sessão

echo ==========================================
echo Auto Claude - Automatizador do Claude Code
echo ==========================================
echo.

REM Verifica se Python está instalado
python --version >nul 2>&1
if errorlevel 1 (
    echo ERRO: Python não encontrado no PATH
    echo Instale Python 3.8+ e adicione ao PATH
    pause
    exit /b 1
)

echo Python encontrado
echo.

REM Verifica argumentos
if "%1"=="--once" (
    echo Executando uma vez...
    python auto_claude.py --once
    goto :EOF
)

if "%1"=="--stop" (
    echo Parando monitor...
    python auto_claude.py --stop
    goto :EOF
)

if "%1"=="--help" (
    echo Uso:
    echo   run_auto_claude.bat              - Inicia monitoramento do deadline
    echo   run_auto_claude.bat --once       - Executa uma vez
    echo   run_auto_claude.bat --stop       - Para o monitor
    echo   run_auto_claude.bat --deadline "2024-04-06 07:00:00" - Define deadline manual
    echo.
    goto :EOF
)

REM Inicia o monitor (padrão)
if "%1"=="" (
    echo Iniciando monitor de deadline da sessão...
    echo O script ficará rodando em segundo plano.
    echo Para parar, execute: run_auto_claude.bat --stop
    echo.
    start "Auto Claude Monitor" cmd /k "python auto_claude.py"
    echo Monitor iniciado em nova janela.
    echo.
    echo Para verificar o log:
    echo   type auto_claude.log
    echo.
    goto :EOF
)

REM Se tiver argumento --deadline
if "%1"=="--deadline" (
    echo Iniciando com deadline manual: %2
    start "Auto Claude Monitor" cmd /k "python auto_claude.py --deadline \"%2\""
    goto :EOF
)

echo Uso: run_auto_claude.bat [--once^|--stop^|--deadline "YYYY-MM-DD HH:MM:SS"]