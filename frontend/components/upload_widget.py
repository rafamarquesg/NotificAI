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
            st.warning(f"Aviso: {result.error}")


# ---------------------------------------------------------------------------
# Upload de arquivos
# ---------------------------------------------------------------------------

def render_upload_section(conn: sqlite3.Connection) -> None:
    """
    Renderiza a seção de upload de arquivos.

    Os arquivos enviados são processados imediatamente e os resultados
    exibidos em cards abaixo do formulário.
    """
    st.subheader("Enviar Documentos")

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
