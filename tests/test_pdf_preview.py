"""Company Brain PDF parsing retains content and rejection boundaries."""
from io import BytesIO
import pytest
from fastapi import HTTPException
from pypdf import PdfWriter
from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject
from backend.routers.brain import extract_document


def document(encrypted=False):
    writer = PdfWriter()
    page = writer.add_blank_page(width=300, height=300)
    font = DictionaryObject({NameObject("/Type"): NameObject("/Font"), NameObject("/Subtype"): NameObject("/Type1"), NameObject("/BaseFont"): NameObject("/Helvetica")})
    page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})})
    stream = DecodedStreamObject()
    stream.set_data(b"BT /F1 12 Tf 20 100 Td (Reviewed company evidence) Tj ET")
    page[NameObject("/Contents")] = stream
    if encrypted:
        writer.encrypt("test-only")
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def test_pdf_preview_retains_text():
    result = extract_document("evidence.pdf", document())
    assert result["content"] == "Reviewed company evidence"


@pytest.mark.parametrize("raw", [b"not a PDF", document(encrypted=True)])
def test_pdf_preview_rejects_invalid_and_encrypted_files(raw):
    with pytest.raises(HTTPException) as error:
        extract_document("evidence.pdf", raw)
    assert error.value.status_code == 422
