from pathlib import Path

from docx import Document as WordDocument
from django.core.exceptions import ValidationError

from .rag_service import index_document

def extract_docx_text(file_obj):
    """
    Extract readable text from a DOCX file.

    Extracts paragraphs and table cells.
    Returns the complete extracted text.
    """
    filename = getattr(file_obj, "name", "")

    if Path(filename).suffix.lower() != ".docx":
        raise ValidationError("Only .docx files are supported.")

    try:
        file_obj.seek(0)
        word_document = WordDocument(file_obj)

        text_parts = []

        for paragraph in word_document.paragraphs:
            text = paragraph.text.strip()
            if text:
                text_parts.append(text)

        for table in word_document.tables:
            for row in table.rows:
                cells = [
                    cell.text.strip().replace("\n", " ")
                    for cell in row.cells
                ]
                if any(cells):
                    text_parts.append(" | ".join(cells))

        full_text = "\n".join(text_parts).strip()

        if not full_text:
            raise ValidationError(
                "The DOCX file does not contain extractable text."
            )

        file_obj.seek(0)
        return full_text

    except ValidationError:
        raise
    except Exception as exc:
        raise ValidationError(
            "The file could not be read as a valid DOCX document."
        ) from exc



def process_document(document):
    """Extract text, save it, and index the document."""

    if not document.file:
        raise ValidationError("No file has been uploaded.")

    with document.file.open("rb") as file_obj:
        full_text = extract_docx_text(file_obj)

    document.full_text = full_text
    document.save(update_fields=["full_text", "updated_at"])

    # Make the document searchable through RAG.
    index_document(document)

    return full_text
