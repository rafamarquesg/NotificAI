"""Exportação dos resultados — formatos descritos na metodologia.

Gera:
  - resumo_executivo.csv          (uma linha por documento)
  - deteccoes_consolidadas.csv    (uma linha por documento, termos no formato
                                   "termo (pág.X-linhaY-DD/MM/AAAA)")
  - analise_completa.json         (estrutura completa)
  - relatorio_estatistico.txt     (estatísticas agregadas)
"""

from __future__ import annotations

import csv
import json
from collections import Counter
from datetime import datetime
from pathlib import Path

from config import ProcessingStatus
from pipeline import CaseReport


def _write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8-sig")
        return
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def executive_row(report: CaseReport) -> dict:
    p = report.patient
    m = report.metadata
    a = report.analysis
    e = report.extraction
    return {
        "arquivo": Path(report.source).name,
        "paciente_id": p.patient_id if p else "",
        "rghc": (p.rghc if p else "") or "",
        "codigo_paciente": (p.codigo_paciente if p else "") or "",
        "cpf": (p.cpf if p else "") or "",
        "data_nascimento": (p.data_nascimento if p else "") or "",
        "nome_paciente": (p.nome_paciente if p else "") or "",
        "data_documento": (m.document_date if m else "") or "",
        "tipo_documento": m.document_type.value if m else "",
        "autor": (m.author if m else "") or "",
        "servico": (m.service if m else "") or "",
        "metodo_extracao": e.method if e else "",
        "paginas": e.page_count if e else 0,
        "qualidade_extracao": e.quality.value if e else "",
        "n_deteccoes": len(a.detections) if a else 0,
        "categorias_unicas": len(a.category_counts) if a else 0,
        "score_base": a.base_score if a else 0.0,
        "bonus_contextual": a.contextual_bonus if a else 0.0,
        "score_total": a.total_score if a else 0.0,
        "severidade": report.severity.label if report.severity else "ERRO",
        "limiar_ajustado": report.severity.adjusted_thresholds if report.severity else False,
        **({f"padrao_{k}": v for k, v in a.patterns.as_dict().items()} if a else {}),
        "tempo_ms": report.elapsed_ms,
        "status": report.status.value,
    }


def consolidated_row(report: CaseReport) -> dict:
    p, m, a = report.patient, report.metadata, report.analysis
    if a is None:
        return {}
    seen_terms: dict[str, dict] = {}
    contexts: list[str] = []
    sentences: list[str] = []
    first_page = float("inf")
    for d in a.detections:
        first_page = min(first_page, d.page_number)
        key = d.term.lower()
        if key not in seen_terms or d.adjusted_weight > seen_terms[key]["weight"]:
            seen_terms[key] = {
                "label": f"{d.term} (pág.{d.page_number}-linha{d.line_number}-{d.document_date or ''})",
                "weight": d.adjusted_weight,
            }
        if d.context and d.context not in contexts:
            contexts.append(d.context)
        if d.full_sentence and d.full_sentence not in sentences:
            sentences.append(d.full_sentence)
    termos = ", ".join(v["label"] for v in seen_terms.values())
    return {
        "arquivo": Path(report.source).name,
        "paciente_id": p.patient_id if p else "",
        "rghc": (p.rghc if p else "") or "",
        "cpf": (p.cpf if p else "") or "",
        "nome_paciente": (p.nome_paciente if p else "") or "",
        "data_documento": (m.document_date if m else "") or "",
        "tipo_documento": m.document_type.value if m else "",
        "pagina_primeira_deteccao": int(first_page) if first_page != float("inf") else 0,
        "total_deteccoes": len(a.detections),
        "categorias_encontradas": ", ".join(a.category_counts.keys()),
        "termos_detectados": termos,
        "contextos_completos": " | ".join(contexts[:10]),
        "frases_completas": " | ".join(sentences[:10]),
        "score_base": a.base_score,
        "bonus_contextual": a.contextual_bonus,
        "score_total": a.total_score,
        "severidade": report.severity.label if report.severity else "ERRO",
    }


def _report_to_json(report: CaseReport) -> dict:
    p, m, a, e, s = (report.patient, report.metadata, report.analysis,
                     report.extraction, report.severity)
    return {
        "source": Path(report.source).name,
        "status": report.status.value,
        "elapsed_ms": report.elapsed_ms,
        "patient": ({"patient_id": p.patient_id, "rghc": p.rghc,
                     "codigo_paciente": p.codigo_paciente, "cpf": p.cpf,
                     "data_nascimento": p.data_nascimento,
                     "nome_paciente": p.nome_paciente,
                     "document_hash": p.document_hash} if p else None),
        "document": ({"date": m.document_date, "type": m.document_type.value,
                      "author": m.author, "service": m.service,
                      "creation_date": m.creation_date} if m else None),
        "extraction": ({"method": e.method, "pages": e.page_count,
                        "chars": e.char_count, "words": e.word_count,
                        "quality": e.quality.value} if e else None),
        "analysis": ({"base_score": a.base_score,
                      "contextual_bonus": a.contextual_bonus,
                      "total_score": a.total_score,
                      "category_scores": a.category_scores,
                      "category_counts": a.category_counts,
                      "patterns": a.patterns.as_dict(),
                      "n_detections": len(a.detections),
                      "detections": [
                          {"term": d.term, "category": d.category,
                           "page": d.page_number, "line": d.line_number,
                           "base_weight": d.base_weight,
                           "intensity": d.intensity,
                           "adjusted_weight": d.adjusted_weight,
                           "confidence": d.confidence,
                           "context": d.context,
                           "sentence": d.full_sentence}
                          for d in a.detections]} if a else None),
        "severity": ({"label": s.label, "score": s.score,
                      "adjusted_thresholds": s.adjusted_thresholds} if s else None),
        "error_message": report.error_message,
    }


def export_all(reports: list[CaseReport], out_dir: Path) -> dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    success = [r for r in reports if r.status == ProcessingStatus.SUCCESS]

    exec_path = out_dir / "resumo_executivo.csv"
    cons_path = out_dir / "deteccoes_consolidadas.csv"
    json_path = out_dir / "analise_completa.json"
    stats_path = out_dir / "relatorio_estatistico.txt"

    _write_csv(exec_path, [executive_row(r) for r in reports])
    _write_csv(cons_path, [consolidated_row(r) for r in success if r.analysis and r.analysis.detections])

    json_payload = {
        "export_timestamp": datetime.now().isoformat(),
        "n_total": len(reports), "n_success": len(success),
        "n_failed": len(reports) - len(success),
        "reports": [_report_to_json(r) for r in reports],
    }
    json_path.write_text(json.dumps(json_payload, ensure_ascii=False, indent=2),
                         encoding="utf-8")
    stats_path.write_text(_statistical_report(reports), encoding="utf-8")

    return {"executive": exec_path, "consolidated": cons_path,
            "json": json_path, "stats": stats_path}


def _statistical_report(reports: list[CaseReport]) -> str:
    success = [r for r in reports if r.status == ProcessingStatus.SUCCESS]
    if not success:
        return "Nenhum documento processado com sucesso."
    scores = [r.analysis.total_score for r in success if r.analysis]
    sev = Counter(r.severity.label for r in success if r.severity)
    doc_types = Counter(r.metadata.document_type.value for r in success if r.metadata)
    pattern_counts = Counter()
    for r in success:
        if r.analysis:
            for k, v in r.analysis.patterns.as_dict().items():
                if v:
                    pattern_counts[k] += 1
    lines = [
        "RELATÓRIO ESTATÍSTICO — NotificAI",
        "=" * 50,
        f"Data: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}",
        f"Total processado: {len(reports)} | Sucesso: {len(success)} "
        f"| Falhas: {len(reports) - len(success)}",
        "",
        "SCORES:",
        f"  média: {sum(scores)/len(scores):.2f} | máx: {max(scores):.2f} "
        f"| mín: {min(scores):.2f}",
        "",
        "DISTRIBUIÇÃO POR SEVERIDADE:",
        *(f"  {k}: {v} ({v/len(success)*100:.1f}%)" for k, v in sev.most_common()),
        "",
        "DISTRIBUIÇÃO POR TIPO DE DOCUMENTO:",
        *(f"  {k}: {v}" for k, v in doc_types.most_common()),
        "",
        "PADRÕES DE VIOLÊNCIA:",
        *(f"  {k}: {v}" for k, v in pattern_counts.most_common()),
    ]
    return "\n".join(lines)
