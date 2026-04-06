"""
Ficha de Notificação SINAN — formulário editável pré-preenchido.

Baseado na Ficha de Notificação Individual de Violência Interpessoal/
Autoprovocada (SINAN NET v2019), campos obrigatórios de notificação.

O técnico pode revisar e completar os campos antes de baixar o CSV.
"""

import io
import csv
import sqlite3
from datetime import datetime, date, timezone
from typing import Any, Dict, Optional

import streamlit as st

from core.database import get_analysis_detail, get_patient

# ---------------------------------------------------------------------------
# Mapeamentos SINAN
# ---------------------------------------------------------------------------

_TIPO_VIOLENCIA = {
    "Violência Física":             "1",
    "Violência Sexual":             "2",
    "Violência Psicológica/Moral":  "3",
    "Violência Autoprovocada":      "4",
    "Negligência/Abandono":         "5",
    "Trabalho Infantil":            "6",
    "Tráfico de Pessoas":           "7",
    "Outros/Não Classificado":      "9",
}

_CID10 = {
    "Violência Física":             "T74.1",
    "Violência Sexual":             "T74.2",
    "Violência Psicológica/Moral":  "T74.3",
    "Violência Autoprovocada":      "X84",
    "Negligência/Abandono":         "T74.0",
    "Trabalho Infantil":            "T74.4",
    "Tráfico de Pessoas":           "T74.8",
    "Outros/Não Classificado":      "T74.9",
}

_SEXO_OPTIONS = ["Ignorado", "Masculino", "Feminino"]
_RACA_OPTIONS = ["Ignorado", "Branca", "Preta", "Amarela", "Parda", "Indígena"]
_ESCOLARIDADE = [
    "Ignorado", "Analfabeto", "1ª a 4ª série incompleta", "4ª série completa",
    "5ª a 8ª série incompleta", "Ensino fundamental completo",
    "Ensino médio incompleto", "Ensino médio completo",
    "Superior incompleto", "Superior completo",
]
_VINCULO = [
    "Ignorado", "Cônjuge/companheiro", "Ex-cônjuge/ex-companheiro",
    "Namorado/ex-namorado", "Pai/padrasto", "Mãe/madrasta",
    "Filho/enteado", "Irmão", "Amigo/conhecido", "Desconhecido",
    "Própria pessoa", "Cuidador", "Patrão/chefe", "Outro",
]
_LOCAL_OCORRENCIA = [
    "Ignorado", "Residência", "Via pública", "Escola", "Local de trabalho",
    "Bar/boate", "Unidade de saúde", "Outros",
]
_EVOLUCAO = ["Ignorado", "Alta", "Encaminhamento", "Internação", "Óbito"]
_TIPO_NOT = "4"  # Notificação individual — violência

# Campos exportados no CSV
_CSV_FIELDS = [
    "DT_NOTIF", "TP_NOT", "ID_AGRAVO", "CS_SEXO", "DT_NASC", "CS_RACA",
    "CS_ESCOL_N", "NU_IDADE_N", "SG_UF_NOT", "ID_MUNICIP",
    "TIPO_VIOL", "DT_OCOR", "LOCAL_OCOR", "VINCULO_AGRES",
    "NOME_PAC_HASH", "CID10", "CS_EVOLUCAO", "DT_ENCERRA",
    "OBSERVACOES", "ID_ANALISE",
]


def render_sinan_form(
    conn: sqlite3.Connection,
    analysis_id: str,
    session_id: str,
    show_patient: bool = True,
) -> None:
    """
    Renderiza o formulário SINAN editável e o botão de download.

    Args:
        conn:         Conexão SQLite.
        analysis_id:  ID da análise a notificar.
        session_id:   ID da sessão (auditoria).
        show_patient: Se True, preenche campos do paciente quando disponíveis.
    """
    detail = get_analysis_detail(conn, analysis_id)
    if not detail:
        st.warning("Análise não encontrada.")
        return

    ntype       = detail.get("notification_type", "Outros/Não Classificado")
    doc_date    = detail.get("document_date") or ""
    patient_hash = detail.get("patient_hash") or ""
    score       = detail.get("score", 0.0)
    confidence  = detail.get("confidence", 0.0)
    severity    = detail.get("severity_level", "—")

    # Dados do paciente (somente Painel Seguro)
    patient = None
    if show_patient and patient_hash:
        patient = get_patient(conn, patient_hash)

    st.markdown(
        """
        <div style="
            background:linear-gradient(135deg,#1a252f,#2c3e50);
            border-radius:10px;
            padding:14px 18px;
            margin-bottom:14px;
        ">
            <div style="color:#ecf0f1;font-size:1rem;font-weight:700;">
                📋 Ficha de Notificação — SINAN
            </div>
            <div style="color:#7f8c8d;font-size:0.8rem;margin-top:2px;">
                Violência Interpessoal/Autoprovocada — SINAN NET v2019
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    today_str = date.today().strftime("%d/%m/%Y")

    # Pré-preencher data de ocorrência
    try:
        dt_ocor_default = datetime.strptime(doc_date[:10], "%Y-%m-%d").date() if doc_date else date.today()
    except Exception:
        dt_ocor_default = date.today()

    # -----------------------------------------------------------------------
    # Seção 1 — Notificação
    # -----------------------------------------------------------------------
    with st.expander("1. Dados da Notificação", expanded=True):
        c1, c2, c3 = st.columns(3)
        dt_notif  = c1.date_input("Data de Notificação", value=date.today(), key=f"sf_dtnotif_{analysis_id}")
        uf        = c2.text_input("UF da Unidade", max_chars=2, value="SP", key=f"sf_uf_{analysis_id}")
        municipio = c3.text_input("Município", value="São Paulo", key=f"sf_mun_{analysis_id}")

        st.markdown(
            f"**Tipo de Notificação:** {_TIPO_NOT} — Individual &nbsp;|&nbsp; "
            f"**CID-10 sugerido:** `{_CID10.get(ntype, 'T74.9')}` &nbsp;|&nbsp; "
            f"**Tipo de Violência:** `{_TIPO_VIOLENCIA.get(ntype, '9')}`",
            unsafe_allow_html=True,
        )

    # -----------------------------------------------------------------------
    # Seção 2 — Paciente
    # -----------------------------------------------------------------------
    with st.expander("2. Dados do Paciente", expanded=True):
        if patient:
            st.info("Campos pré-preenchidos com base nos dados extraídos do prontuário.")

        c1, c2 = st.columns(2)
        nome_display = (patient or {}).get("nome_paciente") or ""
        rghc_display = (patient or {}).get("rghc") or ""

        nome_label = c1.text_input(
            "Nome (hash para exportação)",
            value=nome_display[:40] if nome_display else f"HASH:{patient_hash[:12]}",
            key=f"sf_nome_{analysis_id}",
            help="Não é exportado no CSV — apenas o hash anonimizado.",
        )
        rghc = c2.text_input(
            "RGHC / Prontuário",
            value=rghc_display,
            key=f"sf_rghc_{analysis_id}",
        )

        c3, c4, c5 = st.columns(3)
        try:
            dob_default = datetime.strptime(
                (patient or {}).get("data_nascimento", "")[:10], "%Y-%m-%d"
            ).date() if (patient or {}).get("data_nascimento") else None
        except Exception:
            dob_default = None

        dt_nasc  = c3.date_input("Data de Nascimento", value=dob_default, key=f"sf_nasc_{analysis_id}")
        sexo     = c4.selectbox("Sexo", _SEXO_OPTIONS, key=f"sf_sexo_{analysis_id}")
        raca     = c5.selectbox("Raça/Cor", _RACA_OPTIONS, key=f"sf_raca_{analysis_id}")
        escol    = st.selectbox("Escolaridade", _ESCOLARIDADE, key=f"sf_escol_{analysis_id}")

    # -----------------------------------------------------------------------
    # Seção 3 — Ocorrência
    # -----------------------------------------------------------------------
    with st.expander("3. Dados da Ocorrência", expanded=True):
        c1, c2 = st.columns(2)
        dt_ocor  = c1.date_input("Data da Ocorrência", value=dt_ocor_default, key=f"sf_dtocor_{analysis_id}")
        local    = c2.selectbox("Local de Ocorrência", _LOCAL_OCORRENCIA, key=f"sf_local_{analysis_id}")
        vinculo  = st.selectbox("Vínculo com o Agressor", _VINCULO, key=f"sf_vinculo_{analysis_id}")
        evolucao = st.selectbox("Evolução do Caso", _EVOLUCAO, key=f"sf_evolucao_{analysis_id}")

    # -----------------------------------------------------------------------
    # Seção 4 — Observações
    # -----------------------------------------------------------------------
    with st.expander("4. Observações e Confirmação", expanded=True):
        obs = st.text_area(
            "Observações do técnico",
            key=f"sf_obs_{analysis_id}",
            placeholder="Informações complementares, contexto clínico, solicitações especiais…",
            height=90,
        )
        st.markdown(
            f"**Confiança da IA:** {confidence:.0%} &nbsp;|&nbsp; "
            f"**Score:** {score:.1f} &nbsp;|&nbsp; "
            f"**Severidade:** {severity}",
        )
        tech_nome = st.text_input(
            "Técnico responsável",
            key=f"sf_tech_{analysis_id}",
            placeholder="Nome do técnico NUVE responsável",
        )

    # -----------------------------------------------------------------------
    # Gerar e baixar
    # -----------------------------------------------------------------------
    st.markdown("")
    col_csv, col_txt = st.columns(2)

    if col_csv.button(
        "📥 Gerar Ficha SINAN (CSV)",
        key=f"sf_btn_csv_{analysis_id}",
        type="primary",
        use_container_width=True,
    ):
        csv_bytes = _build_csv(
            analysis_id=analysis_id,
            ntype=ntype,
            dt_notif=dt_notif,
            dt_ocor=dt_ocor,
            dt_nasc=dt_nasc,
            sexo=sexo,
            raca=raca,
            escolaridade=escol,
            uf=uf,
            municipio=municipio,
            local=local,
            vinculo=vinculo,
            evolucao=evolucao,
            patient_hash=patient_hash,
            observacoes=f"{obs or ''} | Técnico: {tech_nome or '—'} | Score IA: {score:.1f}",
        )
        fname = f"sinan_{analysis_id[:8]}_{date.today().isoformat()}.csv"
        st.download_button(
            "⬇️ Baixar CSV SINAN",
            data=csv_bytes,
            file_name=fname,
            mime="text/csv",
            key=f"sf_dl_csv_{analysis_id}",
        )

    if col_txt.button(
        "📄 Gerar Resumo TXT",
        key=f"sf_btn_txt_{analysis_id}",
        use_container_width=True,
    ):
        txt = _build_summary_txt(
            analysis_id=analysis_id,
            ntype=ntype,
            dt_notif=dt_notif,
            dt_ocor=dt_ocor,
            rghc=rghc,
            sexo=sexo,
            raca=raca,
            local=local,
            vinculo=vinculo,
            evolucao=evolucao,
            score=score,
            confidence=confidence,
            severity=severity,
            obs=obs or "",
            tech_nome=tech_nome or "—",
        )
        fname = f"notificai_resumo_{analysis_id[:8]}_{date.today().isoformat()}.txt"
        st.download_button(
            "⬇️ Baixar Resumo TXT",
            data=txt.encode("utf-8"),
            file_name=fname,
            mime="text/plain",
            key=f"sf_dl_txt_{analysis_id}",
        )


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------

def _build_csv(
    analysis_id: str,
    ntype: str,
    dt_notif: date,
    dt_ocor: Optional[date],
    dt_nasc: Optional[date],
    sexo: str,
    raca: str,
    escolaridade: str,
    uf: str,
    municipio: str,
    local: str,
    vinculo: str,
    evolucao: str,
    patient_hash: str,
    observacoes: str,
) -> bytes:
    def _d(d: Optional[date]) -> str:
        return d.strftime("%d/%m/%Y") if d else ""

    row = {
        "DT_NOTIF":      _d(dt_notif),
        "TP_NOT":        _TIPO_NOT,
        "ID_AGRAVO":     _CID10.get(ntype, "T74.9"),
        "CS_SEXO":       sexo[0].upper() if sexo != "Ignorado" else "I",
        "DT_NASC":       _d(dt_nasc),
        "CS_RACA":       str(_RACA_OPTIONS.index(raca)) if raca in _RACA_OPTIONS else "9",
        "CS_ESCOL_N":    str(_ESCOLARIDADE.index(escolaridade)) if escolaridade in _ESCOLARIDADE else "9",
        "NU_IDADE_N":    "",
        "SG_UF_NOT":     uf.upper(),
        "ID_MUNICIP":    municipio,
        "TIPO_VIOL":     _TIPO_VIOLENCIA.get(ntype, "9"),
        "DT_OCOR":       _d(dt_ocor),
        "LOCAL_OCOR":    str(_LOCAL_OCORRENCIA.index(local)) if local in _LOCAL_OCORRENCIA else "9",
        "VINCULO_AGRES": str(_VINCULO.index(vinculo)) if vinculo in _VINCULO else "99",
        "NOME_PAC_HASH": patient_hash[:16],
        "CID10":         _CID10.get(ntype, "T74.9"),
        "CS_EVOLUCAO":   str(_EVOLUCAO.index(evolucao)) if evolucao in _EVOLUCAO else "9",
        "DT_ENCERRA":    date.today().strftime("%d/%m/%Y"),
        "OBSERVACOES":   observacoes[:500],
        "ID_ANALISE":    analysis_id,
    }

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=_CSV_FIELDS, extrasaction="ignore")
    writer.writeheader()
    writer.writerow(row)
    return buf.getvalue().encode("utf-8-sig")  # BOM para Excel


def _build_summary_txt(
    analysis_id: str,
    ntype: str,
    dt_notif: date,
    dt_ocor: Optional[date],
    rghc: str,
    sexo: str,
    raca: str,
    local: str,
    vinculo: str,
    evolucao: str,
    score: float,
    confidence: float,
    severity: str,
    obs: str,
    tech_nome: str,
) -> str:
    def _d(d):
        return d.strftime("%d/%m/%Y") if d else "—"

    return f"""
=================================================================
NOTIFICAÇÃO DE VIOLÊNCIA — NotificAI / NUVE HC-FMUSP
=================================================================
ID da Análise   : {analysis_id}
Data de Emissão : {date.today().strftime("%d/%m/%Y")} — {datetime.now().strftime("%H:%M")}
Técnico         : {tech_nome}

--- CLASSIFICAÇÃO IA ----------------------------------------
Tipo de Violência : {ntype}
CID-10 Sugerido   : {_CID10.get(ntype, "T74.9")}
Tipo SINAN        : {_TIPO_VIOLENCIA.get(ntype, "9")}
Severidade        : {severity}
Score             : {score:.2f}
Confiança         : {confidence:.0%}

--- DADOS DA OCORRÊNCIA ------------------------------------
Data de Notificação : {_d(dt_notif)}
Data da Ocorrência  : {_d(dt_ocor)}
Local               : {local}
Vínculo c/ Agressor : {vinculo}
Evolução            : {evolucao}

--- PACIENTE ------------------------------------------------
RGHC/Prontuário : {rghc or "—"}
Sexo            : {sexo}
Raça/Cor        : {raca}

--- OBSERVAÇÕES ---------------------------------------------
{obs or "Nenhuma observação registrada."}

=================================================================
Gerado automaticamente pelo NotificAI v2.0 — NUVE HC-FMUSP
Este documento deve ser revisado pelo técnico antes do envio.
=================================================================
""".strip()
