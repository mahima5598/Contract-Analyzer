import fitz  # PyMuPDF
import pdfplumber
import pandas as pd
import camelot
import pymupdf4llm

from pathlib import Path
import os
import io
from PIL import Image
import pytesseract

import logging
logger = logging.getLogger(__name__)


def extract_text_pymupdf4llm(pdf_path: str):
    # to_markdown can read the whole file and split it into pages for you!
    md_pages = pymupdf4llm.to_markdown(pdf_path, page_chunks=True)
    
    pages = []
    for i, entry in enumerate(md_pages, start=1):
        pages.append({
            "page": i, 
            "text": entry["text"]
        })
    return pages
    
def extract_images(pdf_path: str, output_dir="extracted/images"):
    """
    Extracts embedded images and OCR text.
    Returns: [{page, image_id, path, ocr_text}]
    """
    os.makedirs(output_dir, exist_ok=True)
    doc = fitz.open(pdf_path)
    images_meta = []

    for page_num, page in enumerate(doc, start=1):
        for img_index, img in enumerate(page.get_images(full=True), start=1):
            xref = img[0]
            base_image = doc.extract_image(xref)
            image_bytes = base_image["image"]
            ext = base_image.get("ext", "png")

            filename = f"{output_dir}/p{page_num}_img{img_index}.{ext}"
            with open(filename, "wb") as f:
                f.write(image_bytes)

            # OCR
            try:
                pil = Image.open(io.BytesIO(image_bytes)).convert("RGB")
                ocr_text = pytesseract.image_to_string(pil)
            except Exception:
                ocr_text = ""

            images_meta.append({
                "page": page_num,
                "image_id": f"p{page_num}_img{img_index}",
                "path": filename,
                "ocr_text": ocr_text.strip()
            })

    return images_meta


def extract_tables(pdf_path: str, output_dir="extracted/tables"):
    import pdfplumber
    import pandas as pd
    import os

    os.makedirs(output_dir, exist_ok=True)
    tables_meta = []

    with pdfplumber.open(pdf_path) as pdf:
        for pnum, page in enumerate(pdf.pages, start=1):
            try:
                page_tables = page.extract_tables()
                for ti, tbl in enumerate(page_tables, start=1):
                    df = pd.DataFrame(tbl[1:], columns=tbl[0]) if len(tbl) > 1 else pd.DataFrame(tbl)

                    csv_path = f"{output_dir}/p{pnum}_t{ti}.csv"
                    df.to_csv(csv_path, index=False)

                    text_render = "\n".join(
                        [" | ".join(map(str, row)) for row in df.values.tolist()]
                    )

                    tables_meta.append({
                        "table_id": f"p{pnum}_t{ti}",
                        "page": pnum,
                        "csv": csv_path,
                        "text": text_render
                    })
            except Exception:
                continue

    return tables_meta


def extract_all(pdf_path: str):
    """
    Unified ingestion pipeline:
    - Clean text (PyMuPDF4LLM)
    - Images + OCR
    - Tables (Camelot + pdfplumber)
    """
    pages = extract_text_pymupdf4llm(pdf_path)
    images = extract_images(pdf_path)
    tables = extract_tables(pdf_path)

    return {
        "pages": pages,
        "images": images,
        "tables": tables
    }
