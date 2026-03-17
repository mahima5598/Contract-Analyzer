import pdfplumber
import pandas as pd
import io

class PDFExtractor:
    def __init__(self):
        # Optimized for legal document tables
        self.table_settings = {
            "vertical_strategy": "lines", 
            "horizontal_strategy": "lines",
            "snap_tolerance": 3,
        }

    def extract(self, pdf_path: str) -> str:
        """Extracts text and tables (as Markdown) from the PDF."""
        full_content = []
        
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                # 1. Get raw text
                page_text = page.extract() or ""
                
                # 2. Get tables
                tables = page.extract_tables(table_settings=self.table_settings)
                
                if tables:
                    formatted_tables = []
                    for table in tables:
                        try:
                            df = pd.DataFrame(table[1:], columns=table[0])
                            df = df.dropna(how='all').fillna("")
                            formatted_tables.append(df.to_markdown(index=False))
                        except Exception:
                            continue # Skip malformed tables
                    
                    combined = f"{page_text}\n\n### Table Data:\n" + "\n\n".join(formatted_tables)
                    full_content.append(combined)
                else:
                    full_content.append(page_text)
                    
        return "\n\n---\n\n".join(full_content)