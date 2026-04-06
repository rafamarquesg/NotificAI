# Auto Claude - Automatizador do Claude Code CLI

## 📋 Visão Geral

Script para automação do Claude Code CLI que executa automaticamente o comando **"continue o projeto"** no **horário limite da sessão**.

## 🚀 Como Funciona

O script monitora continuamente o horário limite da sessão do Claude Code e, quando o deadline se aproxima (5 minutos antes) ou é atingido, executa automaticamente:

```
claude
```

Com a mensagem: `"continue o projeto"`

## 📦 Instalação

### Pré-requisitos
- Python 3.8+
- Claude Code CLI (`@anthropic-ai/claude-code`)
- Node.js (para instalar o Claude Code CLI via npm)

### Instalação do Claude Code CLI

Se ainda não tiver o Claude Code CLI instalado:

```bash
npm install -g @anthropic-ai/claude-code
```

## 💻 Uso

### No Windows

**Opção 1: Usando o script batch (recomendado)**

```cmd
run_auto_claude.bat
```

Isso iniciará o monitor em uma nova janela.

**Opção 2: Usando Python diretamente**

```cmd
python auto_claude.py
```

### No Linux/Mac

```bash
python auto_claude.py
```

### Comandos Disponíveis

| Comando | Descrição |
|---------|-----------|
| `python auto_claude.py` | Inicia monitoramento do deadline |
| `python auto_claude.py --once` | Executa uma única vez e sai |
| `python auto_claude.py --stop` | Para o monitor |
| `python auto_claude.py --deadline "2024-04-06 07:00:00"` | Define deadline manual |

### No Windows (batch)

| Comando | Descrição |
|---------|-----------|
| `run_auto_claude.bat` | Inicia monitor em nova janela |
| `run_auto_claude.bat --once` | Executa uma vez |
| `run_auto_claude.bat --stop` | Para o monitor |
| `run_auto_claude.bat --deadline "2024-04-06 07:00:00"` | Deadline manual |

## 🔧 Configuração do Horário Limite

O script verifica as seguintes variáveis de ambiente para obter o horário limite:

- `CLAUDE_SESSION_DEADLINE`
- `SESSION_DEADLINE`
- `CLAUDE_TIMEOUT`
- `SESSION_TIMEOUT`

### Definindo Deadline Manualmente

Se o Claude Code não definir automaticamente essas variáveis, você pode definir manualmente:

**No Windows (CMD):**
```cmd
set CLAUDE_SESSION_DEADLINE=2024-04-06T07:00:00
python auto_claude.py
```

**No Windows (PowerShell):**
```powershell
$env:CLAUDE_SESSION_DEADLINE="2024-04-06T07:00:00"
python auto_claude.py
```

**No Linux/Mac:**
```bash
export CLAUDE_SESSION_DEADLINE="2024-04-06T07:00:00"
python auto_claude.py
```

Ou use o parâmetro `--deadline`:
```bash
python auto_claude.py --deadline "2024-04-06 07:00:00"
```

## 📊 Logs

O script gera dois arquivos de log:

1. **Console**: Logs em tempo real no terminal
2. **Arquivo**: `auto_claude.log` - Histórico completo das execuções

Para visualizar o log:
```bash
type auto_claude.log    # Windows
cat auto_claude.log     # Linux/Mac
```

## 🔍 Como Funciona o Monitoramento

1. O script verifica a cada 60 segundos se há um deadline definido
2. Quando um deadline é detectado:
   - Se faltam ≤ 5 minutos: executa imediatamente
   - Se o deadline foi atingido: executa imediatamente
   - Caso contrário: continua aguardando
3. Após executar, aguarda o próximo ciclo de verificação

## 🛑 Parando o Monitor

**Método 1: Usando o comando stop**
```bash
python auto_claude.py --stop
```

**Método 2: Pressionando Ctrl+C** (se estiver rodando no terminal)

**Método 3: No Windows, fechando a janela do monitor**

## 📝 Exemplos de Uso

### Exemplo 1: Monitoramento Contínuo

```bash
# Define o deadline (se necessário)
set CLAUDE_SESSION_DEADLINE=2024-04-06T07:00:00

# Inicia o monitor
python auto_claude.py
```

### Exemplo 2: Execução Única para Teste

```bash
python auto_claude.py --once
```

### Exemplo 3: Com Deadline Manual

```bash
python auto_claude.py --deadline "2024-04-06 07:00:00"
```

## ⚠️ Solução de Problemas

### "Claude Code CLI não encontrado"

Instale o Claude Code CLI:
```bash
npm install -g @anthropic-ai/claude-code
```

### "Python não encontrado"

Instale o Python 3.8+ e adicione ao PATH.

### Deadline não é detectado

Verifique se as variáveis de ambiente estão definidas:

**Windows:**
```cmd
echo %CLAUDE_SESSION_DEADLINE%
```

**Linux/Mac:**
```bash
echo $CLAUDE_SESSION_DEADLINE
```

### Monitor não para com --stop

No Windows, use o Gerenciador de Tarefas para finalizar o processo `python.exe`.

## 📄 Arquivos Criados

- `auto_claude.py` - Script principal Python
- `run_auto_claude.bat` - Script batch para Windows
- `auto_claude.log` - Arquivo de log (criado após primeira execução)
- `auto_claude.pid` - Arquivo de PID (apenas durante execução)

## 🔒 Considerações de Segurança

- O script executa comandos no Claude Code CLI com a mensagem fixa "continue o projeto"
- Mantenha o script em um diretório seguro
- Revise os logs regularmente para garantir o funcionamento correto

## 📞 Suporte

Para problemas ou dúvidas, verifique:
1. O arquivo de log `auto_claude.log`
2. A documentação do Claude Code CLI
3. As variáveis de ambiente do sistema