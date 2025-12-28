from pathlib import Path
from docx import Document

BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = BASE_DIR / "output"


def _safe_company(company_name: str) -> str:
    return company_name.strip().replace(" ", "_")


def create_resume_docx(company_name: str, resume_text: str, version: int) -> Path:
    """
    Creates a versioned resume file:
      Anmol_Sansi_<Company>_v<version>.docx
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    safe_company = _safe_company(company_name)
    filename = f"Anmol_Sansi_{safe_company}_v{version}.docx"
    docx_path = OUTPUT_DIR / filename

    doc = Document()
    for line in resume_text.split("\n"):
        doc.add_paragraph(line)
    doc.save(docx_path)

    return docx_path
