"""
================================================
  PDF Parser — Extract text from uploaded PDFs
================================================
"""

import logging
from pathlib import Path
from typing import List, Dict, Any
from PyPDF2 import PdfReader

logger = logging.getLogger(__name__)


def parse_pdf(file_path: str) -> List[Dict[str, Any]]:
    """
    Extract text from a PDF file, page by page.

    Returns:
        List of dicts: [{ "text": str, "metadata": { "page": int, "source": str } }]
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {file_path}")

    logger.info(f"Parsing PDF: {path.name}")
    reader = PdfReader(str(path))
    pages = []

    for i, page in enumerate(reader.pages):
        text = page.extract_text()
        if text and text.strip():
            pages.append({
                "text": text.strip(),
                "metadata": {
                    "page": i + 1,
                    "total_pages": len(reader.pages),
                    "source": path.name,
                    "source_type": "pdf",
                },
            })

    logger.info(f"Extracted text from {len(pages)}/{len(reader.pages)} pages in {path.name}")
    return pages
