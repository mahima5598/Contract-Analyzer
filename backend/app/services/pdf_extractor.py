import logging
from typing import Dict, List, Any

import pdfplumber
import pandas as pd

logger = logging.getLogger(__name__)


class PDFExtractor:
    def __init__(self):
        self.table_settings = {
            "vertical_strategy": "lines",
            "horizontal_strategy": "lines",
            "snap_tolerance": 3,
        }

    def extract(self, pdf_path: str) -> Dict[str, Any]:
        """
        Extract text and tables from every page of a PDF.

        Returns:
            {
                "pages":       [{"page_number": int, "text": str}, ...],
                "tables":      [{"page_number": int, "markdown": str}, ...],
                "images_text": [],
                "page_count":  int,
            }
        """
        pages: List[Dict[str, Any]] = []
        tables: List[Dict[str, Any]] = []

        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                page_number = page.page_number

                page_text = page.extract_text() or ""
                pages.append({
                    "page_number": page_number,
                    "text": page_text,
                })

                raw_tables = page.extract_tables(
                    table_settings=self.table_settings
                )
                for idx, raw_table in enumerate(raw_tables or []):
                    try:
                        if not raw_table or len(raw_table) < 2:
                            continue
                        df = pd.DataFrame(raw_table[1:], columns=raw_table[0])
                        df = df.dropna(how="all").fillna("")
                        tables.append({
                            "page_number": page_number,
                            "markdown": df.to_markdown(index=False),
                        })
                    except Exception as exc:
                        logger.warning(
                            "Skipping malformed table %d on page %d: %s",
                            idx + 1, page_number, exc,
                        )

        return {
            "pages": pages,
            "tables": tables,
            "images_text": [],
            "page_count": len(pages),
        }
    # ── Helper: dict → single string (called by main.py) ─────────────────
    def get_full_text(self, extraction_result: Dict[str, Any]) -> str:
        """
        Collapse an extraction dict into one string.

        Page text comes first, followed by any table markdown — separated by
        page-break markers so the downstream chunker can split cleanly.
        """
        sections: List[str] = []

        for page in extraction_result.get("pages", []):
            text = page.get("text", "").strip()
            if text:
                sections.append(text)

        for table in extraction_result.get("tables", []):
            md = table.get("markdown", "").strip()
            if md:
                sections.append(f"### Table Data (page {table['page_number']}):\n{md}")

        return "\n\n---\n\n".join(sections)

    # ── Convenience: path → string (called by routes.py) ─────────────────
    def extract_text(self, pdf_path: str) -> str:
        """Extract a PDF and return its full text as a single string."""
        extraction = self.extract(pdf_path)
        return self.get_full_text(extraction)