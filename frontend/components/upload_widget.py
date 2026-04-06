"""
Widget de upload de documentos e monitoramento de pasta.

Permite ao usuário:
  - Enviar arquivos PDF/TXT diretamente pelo navegador.
  - Configurar um caminho de pasta para monitoramento automático.
"""

import sqlite3
import streamlit as st
from pathlib import Path
from typing import Optional

from core.processor import process_file, ProcessingResult
from core.ocr import get_ocr_status


# ---------------------------------------------------------------------------
# Mapeamento de status → rótulo colorido
# ---------------------------------------------------------------------------

_STATUS_BADGE = {
    "sucesso":        "🟢 Processado",
    "duplicado":      "🔵 Duplicado",
    "erro_extracao":  "🔴 Erro na extração",
    "erro":           "🔴 Erro",
}

_SEVERITY_BADGE = {
    "CRÍTICO":       "🔴 CRÍTICO",
    "ALTO":          "🟠 ALTO",
    "MODERADO":      "🟡 MODERADO",
    "BAIXO":         "🟢 BAIXO",
    "MÍNIMO":        "🟢 MÍNIMO",
    "SEM INDICAÇÃO": "⚪ SEM INDICAÇÃO",
}


def _result_card(result: ProcessingResult) -> None:
    """Exibe um resumo compacto do resultado de processamento."""
    status_label  = _STATUS_BADGE.get(result.status, result.status)
    severity_label = _SEVERITY_BADGE.get(result.severity_level, result.severity_level)

    with st.container():
        cols = st.columns([3, 2, 2, 1])
        cols[0].markdown(f"**{result.filename}**")
        cols[1].markdown(result.notification_type)
        cols[2].markdown(severity_label)
        cols[3].markdown(status_label)

        if result.error and result.status not in ("duplicado",):
            _render_error_card(result.error)


# ---------------------------------------------------------------------------
# Upload de arquivos
# ---------------------------------------------------------------------------

def _render_error_card(error: str) -> None:
    """Renderiza card de erro contextualizado com instruções de resolução."""
    if error.startswith("pdf_escaneado|"):
        ocr_msg = error.split("|", 1)[1]
        st.markdown(
            f"""<div style="background:rgba(245,158,11,0.07);border-left:3px solid #F59E0B;
            border-radius:0 8px 8px 0;padding:10px 14px;font-size:0.82rem;margin-top:4px;">
            <div style="color:#FBBF24;font-weight:600;margin-bottom:4px;">
                📄 PDF escaneado — texto não extraível diretamente
            </div>
            <div style="color:#4B5563;font-size:0.76rem;line-height:1.7;">
                Para processar este arquivo, instale o OCR:
                <ol style="margin:4px 0 0 16px;padding:0;">
                    <li>Baixar <a href="https://github.com/UB-Mannheim/tesseract/wiki"
                        target="_blank" style="color:#60A5FA;">Tesseract OCR (Windows)</a>
                        — marcar <strong>Portuguese</strong></li>
                    <li><code style="background:#141C2E;padding:1px 5px;border-radius:3px;
                        color:#60A5FA;">pip install pytesseract</code></li>
                    <li>Reiniciar o NotificAI e reenviar o arquivo</li>
                </ol>
            </div>
            </div>""",
            unsafe_allow_html=True,
        )
    elif error.startswith("ocr_erro"):
        st.markdown(
            f"""<div style="background:rgba(239,68,68,0.07);border-left:3px solid #EF4444;
            border-radius:0 8px 8px 0;padding:10px 14px;font-size:0.82rem;margin-top:4px;">
            <div style="color:#F87171;font-weight:600;">⚠️ OCR falhou neste arquivo</div>
            <div style="color:#4B5563;font-size:0.76rem;margin-top:3px;">{error}</div>
            </div>""",
            unsafe_allow_html=True,
        )
    elif error == "texto_insuficiente":
        ocr = get_ocr_status()
        if ocr.available:
            st.markdown(
                """<div style="background:rgba(107,114,128,0.08);border-left:3px solid #6B7280;
                border-radius:0 8px 8px 0;padding:10px 14px;font-size:0.82rem;margin-top:4px;">
                <div style="color:#9CA3AF;font-weight:600;">📄 Texto insuficiente para análise</div>
                <div style="color:#4B5563;font-size:0.76rem;margin-top:2px;">
                    O documento pode estar em branco ou conter apenas imagens não reconhecíveis.
                </div></div>""",
                unsafe_allow_html=True,
            )
        else:
            _render_error_card(f"pdf_escaneado|{ocr.message}")
    else:
        st.warning(f"⚠️ {error}")


def _render_ocr_status_banner() -> None:
    """Exibe status do OCR em tempo real com instrução de instalação se necessário."""
    ocr = get_ocr_status()
    if ocr.available:
        st.markdown(
            f"""<div style="background:rgba(16,185,129,0.08);border:1px solid rgba(16,185,129,0.2);
            border-radius:8px;padding:8px 12px;font-size:0.78rem;color:#34D399;margin-bottom:10px;">
            🔍 <strong>OCR ativo</strong> — Tesseract {ocr.version} · PDFs escaneados serão processados automaticamente.
            </div>""",
            unsafe_allow_html=True,
        )
    else:
        # Detectar motivo e mostrar instrução correta
        if "pytesseract" in ocr.message:
            step1 = "✅ Tesseract instalado"
            step2 = "❌ Falta: `pip install pytesseract`"
            cmd   = "pip install pytesseract"
        elif "Tesseract OCR não encontrado" in ocr.message:
            step1 = "❌ Falta: instalar o Tesseract OCR (binário)"
            step2 = "✅ pytesseract instalado"
            cmd   = None
        else:
            step1 = ocr.message
            step2 = ""
            cmd   = None

        st.markdown(
            f"""<div style="background:rgba(245,158,11,0.07);border:1px solid rgba(245,158,11,0.2);
            border-radius:8px;padding:10px 14px;font-size:0.78rem;margin-bottom:10px;">
            <div style="color:#FBBF24;font-weight:600;margin-bottom:6px;">
                ⚠️ OCR inativo — PDFs escaneados não serão lidos
            </div>
            <div style="color:#4B5563;line-height:1.7;">
                {step1}<br>{step2}
            </div>
            {"<div style='margin-top:6px;'><strong style=color:#F1F5F9;>Para ativar:</strong></div>" if cmd or True else ""}
            <ol style="color:#94A3B8;margin:4px 0 0 16px;padding:0;font-size:0.76rem;line-height:1.8;">
                <li>Instalar o <a href="https://github.com/UB-Mannheim/tesseract/wiki"
                    target="_blank" style="color:#60A5FA;">Tesseract OCR para Windows</a>
                    — marcar <strong>Portuguese</strong> no instalador</li>
                <li>Executar no terminal: <code style="background:#141C2E;padding:1px 6px;
                    border-radius:4px;color:#60A5FA;">pip install pytesseract</code></li>
                <li>Reiniciar o NotificAI</li>
            </ol>
            </div>""",
            unsafe_allow_html=True,
        )


def render_upload_section(conn: sqlite3.Connection) -> None:
    """
    Renderiza a seção de upload de arquivos.

    Os arquivos enviados são processados imediatamente e os resultados
    exibidos em cards abaixo do formulário.
    """
    st.subheader("Enviar Documentos")
    _render_ocr_status_banner()

    uploaded = st.file_uploader(
        "Selecione um ou mais arquivos PDF ou TXT",
        type=["pdf", "txt"],
        accept_multiple_files=True,
        help="Máximo 200 MB por arquivo. O arquivo é analisado e descartado da memória após o processamento.",
    )

    if not uploaded:
        return

    if st.button("Processar arquivos", type="primary"):
        results = []
        progress = st.progress(0, text="Processando…")
        for i, f in enumerate(uploaded):
            try:
                result = process_file(conn, f.read(), f.name)
                results.append(result)
            except Exception as exc:
                st.error(f"Falha ao processar **{f.name}**: {exc}")
            progress.progress((i + 1) / len(uploaded), text=f"Processando {f.name}…")
        progress.empty()

        if results:
            st.success(f"{len(results)} arquivo(s) processado(s).")
            st.markdown("---")
            # Header
            hcols = st.columns([3, 2, 2, 1])
            hcols[0].markdown("**Arquivo**")
            hcols[1].markdown("**Tipo de notificação**")
            hcols[2].markdown("**Severidade**")
            hcols[3].markdown("**Status**")
            st.markdown("---")
            for r in results:
                _result_card(r)

        # Sinaliza para o painel recarregar métricas
        st.session_state["docs_updated"] = True


# ---------------------------------------------------------------------------
# Configuração de pasta monitorada
# ---------------------------------------------------------------------------

def render_folder_monitor_section(conn: sqlite3.Connection) -> None:
    """
    Renderiza o formulário de configuração de monitoramento de pasta.

    Inicia/para um FolderWatcher que processa novos PDFs automaticamente.
    """
    st.subheader("Monitoramento de Pasta")

    try:
        from core.watcher import FolderWatcher, HAS_WATCHDOG
    except ImportError:
        HAS_WATCHDOG = False

    if not HAS_WATCHDOG:
        st.warning(
            "Biblioteca **watchdog** não instalada. "
            "Instale com `pip install watchdog` para ativar o monitoramento automático."
        )
        return

    watcher: Optional[FolderWatcher] = st.session_state.get("folder_watcher")
    is_running = watcher is not None and watcher.is_alive()

    with st.form("folder_monitor_form"):
        folder_path = st.text_input(
            "Caminho da pasta",
            value=st.session_state.get("monitor_folder_path", ""),
            placeholder="/mnt/prontuarios",
            help="Caminho absoluto da pasta contendo os PDFs. Novos arquivos serão processados automaticamente.",
        )
        scan_existing = st.checkbox(
            "Processar PDFs já existentes na pasta ao iniciar",
            value=True,
        )
        col_start, col_stop = st.columns(2)
        start_btn = col_start.form_submit_button("▶ Iniciar monitoramento", type="primary", disabled=is_running)
        stop_btn  = col_stop.form_submit_button("■ Parar monitoramento",  disabled=not is_running)

    if start_btn and folder_path:
        p = Path(folder_path)
        if not p.exists():
            st.error(f"Pasta não encontrada: {folder_path}")
        else:
            def _on_new_doc(result: ProcessingResult):
                st.session_state["docs_updated"] = True

            new_watcher = FolderWatcher(
                folder_path=str(p),
                conn=conn,
                on_new_doc=_on_new_doc,
            )
            new_watcher.start()

            if scan_existing:
                with st.spinner("Processando PDFs existentes…"):
                    new_watcher.scan_existing()

            st.session_state["folder_watcher"] = new_watcher
            st.session_state["monitor_folder_path"] = folder_path
            st.success(f"Monitorando: `{folder_path}`")
            st.rerun()

    if stop_btn and is_running:
        watcher.stop()
        watcher.join(timeout=5)
        st.session_state["folder_watcher"] = None
        st.info("Monitoramento encerrado.")
        st.rerun()

    # Status atual
    if is_running:
        processed = len(watcher.processed)
        errors    = len(watcher.errors)
        st.info(
            f"**Em execução** · Pasta: `{st.session_state.get('monitor_folder_path', '')}` "
            f"· {processed} processado(s) · {errors} erro(s)"
        )
        if watcher.errors:
            with st.expander("Ver erros"):
                for e in watcher.errors:
                    st.error(f"`{e['file']}` — {e['error']}")
