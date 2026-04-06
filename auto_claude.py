#!/usr/bin/env python3
"""
Auto Claude - Script para automação do Claude Code CLI

Executa automaticamente o comando "claude" com a mensagem "continue o projeto"
no horário limite da sessão.

Uso:
    python auto_claude.py              # Executa monitorando deadline da sessão
    python auto_claude.py --once       # Executa apenas uma vez
    python auto_claude.py --stop       # Para o monitor
    python auto_claude.py --deadline "2024-04-06 07:00:00"  # Define deadline manual
"""

import subprocess
import sys
import time
import os
import argparse
import logging
import threading
from datetime import datetime, timedelta
from pathlib import Path

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('auto_claude.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# Configurações
CONTINUE_MESSAGE = "continue o projeto"
PID_FILE = Path("auto_claude.pid")
LOG_FILE = Path("auto_claude.log")
CHECK_INTERVAL_SECONDS = 60  # Verifica a cada 60 segundos
GRACE_PERIOD_MINUTES = 5     # Executa 5 minutos antes do deadline

# Variável global para controlar o loop
_stop_event = threading.Event()


def get_session_deadline() -> datetime | None:
    """
    Tenta obter o horário limite da sessão do Claude Code CLI.
    
    Verifica variáveis de ambiente que podem conter essa informação.
    
    Returns:
        datetime | None: Horário limite da sessão ou None se não disponível
    """
    env_vars = [
        'CLAUDE_SESSION_DEADLINE',
        'SESSION_DEADLINE',
        'CLAUDE_TIMEOUT',
        'SESSION_TIMEOUT',
    ]
    
    for var in env_vars:
        value = os.environ.get(var)
        if value:
            try:
                timestamp = float(value)
                return datetime.fromtimestamp(timestamp)
            except (ValueError, OSError):
                pass
            
            try:
                return datetime.fromisoformat(value)
            except ValueError:
                pass
    
    return None


def run_claude_command(message: str = CONTINUE_MESSAGE) -> int:
    """
    Executa o comando Claude Code CLI com a mensagem especificada.
    
    Args:
        message: Mensagem a ser enviada para o Claude
        
    Returns:
        int: Código de retorno do processo
    """
    logger.info(f"Executando Claude Code CLI com mensagem: '{message}'")
    
    try:
        # Tenta encontrar o comando claude
        claude_cmd = None
        
        # Verifica no PATH primeiro
        try:
            result = subprocess.run(
                ['claude', '--version'],
                capture_output=True,
                text=True,
                timeout=30,
                shell=(sys.platform == 'win32')
            )
            if result.returncode == 0:
                claude_cmd = 'claude'
                logger.info(f"Claude Code CLI encontrado: {result.stdout.strip()}")
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        
        # Se não encontrou, tenta caminhos comuns no Windows
        if claude_cmd is None and sys.platform == 'win32':
            common_paths = [
                os.path.expandvars(r'%APPDATA%\npm\claude.cmd'),
                os.path.expandvars(r'%USERPROFILE%\AppData\Roaming\npm\claude.cmd'),
                r'C:\Users\%USERNAME%\AppData\Roaming\npm\claude.cmd',
            ]
            for path in common_paths:
                if os.path.exists(path):
                    claude_cmd = path
                    logger.info(f"Claude Code CLI encontrado em: {path}")
                    break
        
        # Se ainda não encontrou, tenta instalar
        if claude_cmd is None:
            logger.warning("Claude Code CLI não encontrado no PATH")
            logger.info("Tentando instalar com npm...")
            try:
                subprocess.run(
                    ['npm', 'install', '-g', '@anthropic-ai/claude-code'],
                    check=True,
                    capture_output=True,
                    shell=(sys.platform == 'win32')
                )
                logger.info("Claude Code CLI instalado com sucesso")
                claude_cmd = 'claude'
            except subprocess.CalledProcessError as e:
                logger.error(f"Falha ao instalar Claude Code CLI: {e}")
                return 1
        
        cmd = [claude_cmd]
        
        process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=str(Path.cwd()),
            shell=(sys.platform == 'win32')
        )
        
        stdout, stderr = process.communicate(
            input=message,
            timeout=3600
        )
        
        if process.returncode == 0:
            logger.info("Claude Code CLI executado com sucesso")
        else:
            logger.warning(f"Claude Code CLI retornou código {process.returncode}")
            if stderr:
                logger.debug(f"stderr: {stderr[:500]}...")
        
        return process.returncode
        
    except subprocess.TimeoutExpired:
        logger.error("Timeout na execução do Claude Code CLI")
        return 1
    except FileNotFoundError:
        logger.error("Claude Code CLI não encontrado")
        return 1
    except Exception as e:
        logger.error(f"Erro na execução: {e}")
        return 1


def save_pid():
    """Salva o PID do processo atual."""
    PID_FILE.write_text(str(os.getpid()))


def remove_pid():
    """Remove o arquivo de PID."""
    if PID_FILE.exists():
        PID_FILE.unlink()


def is_running() -> bool:
    """Verifica se já existe uma instância rodando."""
    if not PID_FILE.exists():
        return False
    
    try:
        pid = int(PID_FILE.read_text().strip())
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, ValueError, OSError):
        remove_pid()
        return False


def wait_for_deadline(deadline: datetime):
    """
    Espera até o horário limite da sessão e executa o comando.
    
    Args:
        deadline: Horário limite da sessão
    """
    while not _stop_event.is_set():
        now = datetime.now()
        time_until_deadline = (deadline - now).total_seconds()
        
        if time_until_deadline <= 0:
            logger.info("Horário limite da sessão atingido!")
            run_claude_command()
            logger.info("Comando executado. Aguardando próximo deadline...")
            time.sleep(CHECK_INTERVAL_SECONDS)
            break
        
        if time_until_deadline <= GRACE_PERIOD_MINUTES * 60:
            logger.info(f"Executando {GRACE_PERIOD_MINUTES} minutos antes do deadline")
            run_claude_command()
            time.sleep(CHECK_INTERVAL_SECONDS)
            break
        
        hours, remainder = divmod(int(time_until_deadline), 3600)
        minutes, seconds = divmod(remainder, 60)
        logger.info(f"Próximo deadline em {hours}h {minutes}m {seconds}s - {deadline.strftime('%H:%M:%S')}")
        
        time.sleep(CHECK_INTERVAL_SECONDS)


def run_deadline_monitor():
    """
    Executa o monitor que aguarda o horário limite da sessão.
    """
    if is_running():
        logger.warning("Já existe uma instância do auto_claude rodando")
        logger.warning(f"PID: {PID_FILE.read_text().strip()}")
        sys.exit(1)
    
    save_pid()
    
    logger.info("Iniciando monitor de deadline da sessão")
    logger.info(f"Log file: {LOG_FILE}")
    logger.info("Pressione Ctrl+C para parar")
    
    try:
        while not _stop_event.is_set():
            deadline = get_session_deadline()
            
            if deadline:
                logger.info(f"Deadline da sessão detectado: {deadline.strftime('%Y-%m-%d %H:%M:%S')}")
                wait_for_deadline(deadline)
            else:
                logger.info("Nenhum deadline de sessão encontrado. Verificando novamente em 1 minuto...")
                time.sleep(60)
                
    except KeyboardInterrupt:
        logger.info("Monitor interrompido pelo usuário")
    except Exception as e:
        logger.error(f"Erro no monitor: {e}")
    finally:
        remove_pid()
        logger.info("Monitor encerrado")


def run_once():
    """Executa o Claude Code CLI uma única vez."""
    logger.info("Execução única do Claude Code CLI")
    return run_claude_command()


def stop_daemon():
    """Para o daemon se estiver rodando."""
    if not PID_FILE.exists():
        logger.info("Nenhum daemon está rodando")
        return
    
    try:
        pid = int(PID_FILE.read_text().strip())
        logger.info(f"Enviando sinal de parada para PID {pid}")
        
        if sys.platform == 'win32':
            subprocess.run(['taskkill', '/PID', str(pid), '/F'], capture_output=True)
        else:
            import signal
            os.kill(pid, signal.SIGTERM)
        
        for _ in range(10):
            time.sleep(0.5)
            if not is_running():
                logger.info("Daemon parado com sucesso")
                remove_pid()
                return
        
        logger.warning("Não foi possível parar o daemon")
        
    except (ProcessLookupError, ValueError, OSError) as e:
        logger.error(f"Erro ao parar daemon: {e}")
        remove_pid()


def signal_handler(sig, frame):
    """Manipulador de sinais para parada graciosa."""
    logger.info("Recebido sinal de parada")
    _stop_event.set()


def main():
    parser = argparse.ArgumentParser(
        description="Auto Claude - Automação do Claude Code CLI baseado no horário limite da sessão",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  python auto_claude.py              # Executa monitorando deadline da sessão
  python auto_claude.py --once       # Executa uma vez e sai
  python auto_claude.py --stop       # Para o monitor
  python auto_claude.py --deadline "2024-04-06 07:00:00"  # Define deadline manual
        """
    )
    
    parser.add_argument(
        '--once', '-o',
        action='store_true',
        help='Executar apenas uma vez'
    )
    
    parser.add_argument(
        '--stop', '-s',
        action='store_true',
        help='Parar o monitor se estiver rodando'
    )
    
    parser.add_argument(
        '--deadline',
        type=str,
        help='Horário limite da sessão no formato "YYYY-MM-DD HH:MM:SS"'
    )
    
    parser.add_argument(
        '--message', '-m',
        default=CONTINUE_MESSAGE,
        help=f'Mensagem a ser enviada (padrão: "{CONTINUE_MESSAGE}")'
    )
    
    args = parser.parse_args()
    
    import signal
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    if args.stop:
        stop_daemon()
        return
    
    if args.once:
        sys.exit(run_once())
    
    if args.deadline:
        try:
            manual_deadline = datetime.fromisoformat(args.deadline)
            os.environ['CLAUDE_SESSION_DEADLINE'] = manual_deadline.isoformat()
            logger.info(f"Deadline manual definido: {manual_deadline}")
        except ValueError as e:
            logger.error(f"Formato de deadline inválido: {e}")
            sys.exit(1)
    
    run_deadline_monitor()


if __name__ == '__main__':
    main()