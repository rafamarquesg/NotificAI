"""CLI: processa pasta de PDFs e gera relatórios.

Uso:
    python main.py <pasta_com_pdfs> [--out diretorio_saida]
                                    [--positivos N] [--no-anonymize]

`--positivos N` ativa o cálculo de sensibilidade Wilson score (composta:
explícita + expandida) assumindo que todos os PDFs da pasta são casos
positivos confirmados — reproduz a validação descrita no TCC.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from config import ProcessingConfig, SeverityLevel
from exporter import export_all
from keyword_extraction import aggregate_keywords, to_csv_rows
from pipeline import TriagePipeline
from sensitivity import composite_sensitivity, format_pct


def main() -> None:
    parser = argparse.ArgumentParser(description="NotificAI — triagem lexical de violência em prontuários")
    parser.add_argument("input_dir", type=Path, help="Diretório com PDFs")
    parser.add_argument("--out", type=Path, default=Path("./saida"))
    parser.add_argument("--positivos", type=int, default=None,
                        help="Se informado, reporta sensibilidade explícita+expandida (IC95% Wilson)")
    parser.add_argument("--no-anonymize", action="store_true",
                        help="Desativa anonimização (uso restrito; padrão: anonimizado)")
    args = parser.parse_args()

    pdfs = sorted(args.input_dir.glob("*.pdf"))
    if not pdfs:
        print(f"Nenhum PDF em {args.input_dir}")
        return

    config = ProcessingConfig(anonymize_identifiers=not args.no_anonymize)
    pipeline = TriagePipeline(config)

    print(f"Processando {len(pdfs)} PDF(s)...")
    reports = []
    for i, pdf in enumerate(pdfs, start=1):
        r = pipeline.process(pdf)
        if r.severity:
            print(f"  [{i}/{len(pdfs)}] {pdf.name}: {r.severity.label} (score={r.severity.score})")
        else:
            print(f"  [{i}/{len(pdfs)}] {pdf.name}: ERRO ({r.error_message})")
        reports.append(r)

    paths = export_all(reports, args.out)
    print(f"\nResumo executivo:        {paths['executive']}")
    print(f"Detecções consolidadas:  {paths['consolidated']}")
    print(f"Análise completa (JSON): {paths['json']}")
    print(f"Relatório estatístico:   {paths['stats']}")

    success = [r for r in reports if r.analysis]
    keywords = aggregate_keywords([r.analysis for r in success], top_k=20)
    kw_path = args.out / "tabela2_palavras_chave.csv"
    import csv as _csv
    with kw_path.open("w", encoding="utf-8-sig", newline="") as f:
        w = _csv.DictWriter(f, fieldnames=["termo", "frequencia_absoluta",
                                            "frequencia_relativa_pct", "categoria"])
        w.writeheader()
        w.writerows(to_csv_rows(keywords))
    print(f"Tabela 2 (palavras-chave): {kw_path}")

    n_positives = args.positivos if args.positivos is not None else None
    if n_positives:
        explicit = sum(1 for r in success
                       if r.analysis and any(not False for d in r.analysis.detections))
        contextual = sum(1 for r in success
                         if r.severity and r.severity.label in (SeverityLevel.HIGH.value,
                                                                 SeverityLevel.CRITICAL.value)
                         and not (r.analysis and r.analysis.detections))
        sens = composite_sensitivity(explicit, n_positives, contextual)
        print("\nSensibilidade (Wilson IC95%):")
        for name, res in sens.items():
            print(f"  {name}: {format_pct(res.sensitivity)} "
                  f"({format_pct(res.ci_lower)}–{format_pct(res.ci_upper)}) "
                  f"[{res.detected}/{res.total}]")


if __name__ == "__main__":
    main()
