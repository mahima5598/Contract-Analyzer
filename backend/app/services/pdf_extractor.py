"""
Multi-strategy PDF extraction pipeline.

Strategy:
1. pdfplumber  → primary text + table extraction (best for digital PDFs)
2. camelot-py  → fallback for complex tables
3. pymupdf     → image extraction
4. pytesseract → OCR for scanned/image-based pages

Design decision: We try digital extraction first (fast, accurate),
and fall back to OCR only for pages with little/no extractable text.
"""
import os
import uuid
import pdfplumber
import fitz  # pymupdf
from pdf2image import convert_from_path
import pytesseract
import camelot
import pandas as pd
from typing import Dict, List, Any


class PDFExtractor:
    def __init__(self, upload_dir: str = "uploads", extract_dir: str = "extracted"):
        self.upload_dir = upload_dir
        self.extract_dir = extract_dir
        os.makedirs(upload_dir, exist_ok=True)
        os.makedirs(extract_dir, exist_ok=True)

    def extract(self, filepath: str) -> Dict[str, Any]:
        """Full extraction pipeline: text + tables + OCR fallback."""
        document_id = str(uuid.uuid4())
        result = {
            "document_id": document_id,
            "filename": os.path.basename(filepath),
            "pages": [],
            "tables": [],
            "images_text": [],
        }

        # 1. Text extraction with pdfplumber
        with pdfplumber.open(filepath) as pdf:
            result["page_count"] = len(pdf.pages)
            for i, page in enumerate(pdf.pages):
                text = page.extract_text() or ""
                tables = page.extract_tables() or []

                # If text is too short, likely a scanned page → OCR
                if len(text.strip()) < 50:
                    text = self._ocr_page(filepath, i)

                result["pages"].append({
                    "page_number": i + 1,
                    "text": text,
                    "has_tables": len(tables) > 0,
                })

                for table in tables:
                    df = pd.DataFrame(table[1:], columns=table[0])
                    result["tables"].append({
                        "page_number": i + 1,
                        "dataframe": df.to_dict(),
                        "markdown": df.to_markdown(index=False),
                    })

        # 2. Extract images and OCR them
        result["images_text"] = self._extract_images(filepath)

        return result

    def _ocr_page(self, filepath: str, page_index: int) -> str:
        """OCR a single page using pytesseract."""
        images = convert_from_path(filepath, first_page=page_index + 1,
                                    last_page=page_index + 1)
        if images:
            return pytesseract.image_to_string(images[0])
        return ""

    def _extract_images(self, filepath: str) -> List[Dict]:
        """Extract embedded images and run OCR on them."""
        results = []
        doc = fitz.open(filepath)
        for page_num in range(len(doc)):
            page = doc[page_num]
            images = page.get_images(full=True)
            for img_idx, img in enumerate(images):
                xref = img[0]
                pix = fitz.Pixmap(doc, xref)
                if pix.n >= 5:  # CMYK → RGB
                    pix = fitz.Pixmap(fitz.csRGB, pix)
                img_path = os.path.join(
                    self.extract_dir, f"img_p{page_num}_{img_idx}.png"
                )
                pix.save(img_path)
                ocr_text = pytesseract.image_to_string(img_path)
                if ocr_text.strip():
                    results.append({
                        "page_number": page_num + 1,
                        "image_path": img_path,
                        "extracted_text": ocr_text,
                    })
        return results

    def get_full_text(self, extraction_result: Dict) -> str:
        """Combine all extracted content into a single text document."""
        parts = []
        for page in extraction_result["pages"]:
            parts.append(f"--- Page {page['page_number']} ---\n{page['text']}")

        for table in extraction_result["tables"]:
            parts.append(
                f"--- Table on Page {table['page_number']} ---\n{table['markdown']}"
            )

        for img in extraction_result["images_text"]:
            parts.append(
                f"--- Image on Page {img['page_number']} ---\n{img['extracted_text']}"
            )

        return "\n\n".join(parts)