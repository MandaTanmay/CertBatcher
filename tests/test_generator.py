from datetime import date
from io import BytesIO

import pytest
from pypdf import PdfReader

from app.schemas import CertificateInfo
from app.services.certificate_generator import generate_certificate_pdf

INFO = CertificateInfo(
    title="Certificate of Completion",
    event_name="Python Bootcamp 2026",
    issued_by="ABC Academy",
    issue_date=date(2026, 10, 1),
)


def test_pdf_starts_with_pdf_header():
    pdf_bytes = generate_certificate_pdf("John Doe", INFO, "cert-123")
    assert pdf_bytes.startswith(b"%PDF")


def test_pdf_can_be_opened_by_pypdf():
    pdf_bytes = generate_certificate_pdf("John Doe", INFO, "cert-123")
    reader = PdfReader(BytesIO(pdf_bytes))
    assert len(reader.pages) == 1


def test_pdf_contains_recipient_name():
    pdf_bytes = generate_certificate_pdf("John Doe", INFO, "cert-123")
    reader = PdfReader(BytesIO(pdf_bytes))
    text = reader.pages[0].extract_text()
    assert "John Doe" in text


def test_pdf_contains_event_name():
    pdf_bytes = generate_certificate_pdf("John Doe", INFO, "cert-123")
    reader = PdfReader(BytesIO(pdf_bytes))
    text = reader.pages[0].extract_text()
    assert "Python Bootcamp 2026" in text


def test_pdf_contains_issuer():
    pdf_bytes = generate_certificate_pdf("John Doe", INFO, "cert-123")
    reader = PdfReader(BytesIO(pdf_bytes))
    text = reader.pages[0].extract_text()
    assert "ABC Academy" in text


def test_pdf_contains_certificate_id():
    pdf_bytes = generate_certificate_pdf("John Doe", INFO, "cert-123")
    reader = PdfReader(BytesIO(pdf_bytes))
    text = reader.pages[0].extract_text()
    assert "cert-123" in text


def test_pdf_contains_formatted_date():
    pdf_bytes = generate_certificate_pdf("John Doe", INFO, "cert-123")
    reader = PdfReader(BytesIO(pdf_bytes))
    text = reader.pages[0].extract_text()
    assert "October 01, 2026" in text


def test_empty_name_raises_value_error():
    with pytest.raises(ValueError, match="Recipient name cannot be empty"):
        generate_certificate_pdf("", INFO, "cert-123")


def test_whitespace_only_name_raises_value_error():
    with pytest.raises(ValueError, match="Recipient name cannot be empty"):
        generate_certificate_pdf("   ", INFO, "cert-123")


def test_long_name_generates_successfully():
    long_name = "A" * 80
    pdf_bytes = generate_certificate_pdf(long_name, INFO, "cert-123")
    assert pdf_bytes.startswith(b"%PDF")


def test_different_names_produce_different_pdfs():
    pdf1 = generate_certificate_pdf("Alice", INFO, "cert-1")
    pdf2 = generate_certificate_pdf("Bob", INFO, "cert-2")
    assert pdf1 != pdf2

    reader1 = PdfReader(BytesIO(pdf1))
    reader2 = PdfReader(BytesIO(pdf2))
    text1 = reader1.pages[0].extract_text()
    text2 = reader2.pages[0].extract_text()

    assert "Alice" in text1
    assert "Bob" in text2
    assert "Alice" not in text2
    assert "Bob" not in text1
