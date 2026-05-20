"""CLI — processa lote de PDFs e gera resumo_executivo.csv e deteccoes_consolidadas.csv.

Uso:
    python main.py <pasta_com_pdfs> [--out diretorio_saida]
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

from keyword_extraction import aggregate_keywords, to_csv_rows
from pipeline import TriagePipeline, case_summary_row, detection_rows
from sensitivity import composite_sensitivity, format_pct


def _write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def run(input_dir: Path, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    pdfs = sorted(input_dir.glob("*.pdf"))
    if not pdfs:
        print(f"Nenhum PDF em {input_dir}")
        return

    pipeline = TriagePipeline()
    summary_rows: list[dict] = []
    detection_rows_all: list[dict] = []
    analyses = []
    explicit_detected = 0
    contextual_high_risk = 0

    for pdf in pdfs:
        report = pipeline.process(pdf)
        summary_rows.append(case_summary_row(report))
        detection_rows_all.extend(detection_rows(report))
        analyses.append(report.analysis)
        explicit_has_term = any(not d.negated for d in report.analysis.detections)
        if explicit_has_term:
            explicit_detected += 1
        elif report.severity.label in ("ALTO", "CRITICO"):
            contextual_high_risk += 1

    _write_csv(output_dir / "resumo_executivo.csv", summary_rows)
    _write_csv(output_dir / "deteccoes_consolidadas.csv", detection_rows_all)

    keywords = aggregate_keywords(analyses, top_k=20)
    _write_csv(output_dir / "tabela2_palavras_chave.csv", to_csv_rows(keywords))

    total = len(pdfs)
    sens = composite_sensitivity(explicit_detected, total, contextual_high_risk)
    print(f"Processados: {total}")
    print(f"Detectados explicitamente: {explicit_detected}")
    print(f"Contextuais (alto risco): {contextual_high_risk}")
    e = sens["explicita"]
    x = sens["expandida"]
    print(f"Sensibilidade explícita: {format_pct(e.sensitivity)} "
          f"(IC95% {format_pct(e.ci_lower)}–{format_pct(e.ci_upper)})")
    print(f"Sensibilidade expandida: {format_pct(x.sensitivity)} "
          f"(IC95% {format_pct(x.ci_lower)}–{format_pct(x.ci_upper)})")


def main() -> None:
    parser = argparse.ArgumentParser(description="NotificAI — triagem lexical de violência em prontuários")
    parser.add_argument("input_dir", type=Path, help="Diretório com PDFs de prontuários")
    parser.add_argument("--out", type=Path, default=Path("./saida"), help="Diretório de saída")
    args = parser.parse_args()
    run(args.input_dir, args.out)


if __name__ == "__main__":
    main()
