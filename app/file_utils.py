from pathlib import Path
from docx import Document

BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = BASE_DIR / "output"

def create_resume_docx(company_name: str, resume_text: str) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    safe_company = company_name.strip().replace(" ", "_")
    base_name = f"Anmol_Sansi_{safe_company}"

    docx_path = OUTPUT_DIR / f"{base_name}.docx"

    doc = Document()
    for line in resume_text.split("\n"):
        doc.add_paragraph(line)
    doc.save(docx_path)

    return docx_path
