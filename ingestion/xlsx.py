"""
ingestion/xlsx.py
=================
Extrator para planilhas (.xlsx, .xls, .csv).
Concatena todas as células de texto em formato legível.
Útil para listas de pacientes, relatórios tabulados e exportações de sistemas.
"""

from pathlib import Path
from typing import Any, Dict, List, Tuple

from .base import AbstractExtractor, ExtractionResult


class XlsxExtractor(AbstractExtractor):
    supported_extensions = [".xlsx", ".xls", ".csv"]

    def extract(self, file_path: Path) -> ExtractionResult:
        if not file_path.exists():
            return self._build_error_result(file_path, "xlsx", f"Arquivo não encontrado: {file_path}")

        try:
            text, pages, meta = self._extract(file_path)
            return ExtractionResult(
                text=self._clean_text(text),
                source_path=str(file_path),
                format="xlsx",
                page_count=meta.get("sheet_count", 1),
                extraction_method="pandas",
                quality_score=1.0 if len(text) > 50 else 0.3,
                pages=pages,
                metadata=meta,
            )
        except Exception as exc:
            return self._build_error_result(file_path, "xlsx", str(exc))

    def _extract(self, path: Path) -> Tuple[str, List[Dict], Dict[str, Any]]:
        import pandas as pd

        ext = path.suffix.lower()
        sheets: Dict[str, Any] = {}

        if ext == ".csv":
            df = pd.read_csv(path, dtype=str, on_bad_lines="skip")
            sheets = {"Sheet1": df}
        else:
            xls = pd.ExcelFile(path)
            for sheet_name in xls.sheet_names:
                sheets[sheet_name] = xls.parse(sheet_name, dtype=str)

        pages: List[Dict] = []
        all_text_parts: List[str] = []

        for sheet_name, df in sheets.items():
            # Concatena header + linhas como texto
            df = df.fillna("")
            sheet_text = f"[Planilha: {sheet_name}]\n"
            sheet_text += df.to_string(index=False)
            all_text_parts.append(sheet_text)
            pages.append({"page": sheet_name, "text": sheet_text})

        full_text = "\n\n".join(all_text_parts)
        meta = {
            "sheet_count": len(sheets),
            "total_rows": sum(len(df) for df in sheets.values()),
        }
        return full_text, pages, meta
