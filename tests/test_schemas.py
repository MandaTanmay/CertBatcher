from datetime import date

import pytest
from pydantic import ValidationError

from app.schemas import (
    CertificateInfo,
    JobCreateRequest,
    RecipientIn,
    validate_recipient,
)


def test_recipient_valid():
    recipient = RecipientIn(name="John Doe", email="john@example.com")
    assert recipient.name == "John Doe"
    assert recipient.email == "john@example.com"


def test_recipient_valid_without_email():
    recipient = RecipientIn(name="John Doe")
    assert recipient.name == "John Doe"
    assert recipient.email is None


def test_recipient_name_trims_whitespace():
    recipient = RecipientIn(name="  John Doe  ")
    assert recipient.name == "John Doe"


def test_recipient_name_collapses_whitespace():
    recipient = RecipientIn(name="John   Doe")
    assert recipient.name == "John Doe"


def test_recipient_empty_name_fails():
    with pytest.raises(ValidationError) as exc_info:
        RecipientIn(name="", email="john@example.com")
    assert "Name cannot be blank" in str(exc_info.value)


def test_recipient_whitespace_only_name_fails():
    with pytest.raises(ValidationError) as exc_info:
        RecipientIn(name="   ", email="john@example.com")
    assert "Name cannot be blank" in str(exc_info.value)


def test_recipient_invalid_email_fails():
    with pytest.raises(ValidationError):
        RecipientIn(name="John Doe", email="invalid-email")


def test_recipient_name_too_long_fails():
    with pytest.raises(ValidationError) as exc_info:
        RecipientIn(name="a" * 81)
    assert "at most 80 characters" in str(exc_info.value)


def test_recipient_control_characters_fail():
    with pytest.raises(ValidationError) as exc_info:
        RecipientIn(name="John\x00Doe")
    assert "control characters" in str(exc_info.value)


def test_recipient_name_not_string_fails():
    with pytest.raises(ValidationError) as exc_info:
        RecipientIn(name=123)
    assert "Name must be a string" in str(exc_info.value)


def test_certificate_info_defaults():
    cert = CertificateInfo(
        event_name="Test Event",
        issued_by="Test Issuer",
        issue_date=date(2024, 1, 1),
    )
    assert cert.title == "Certificate of Completion"
    assert cert.event_name == "Test Event"
    assert cert.issued_by == "Test Issuer"
    assert cert.issue_date == date(2024, 1, 1)


def test_certificate_info_custom_title():
    cert = CertificateInfo(
        title="Custom Title",
        event_name="Test Event",
        issued_by="Test Issuer",
        issue_date=date(2024, 1, 1),
    )
    assert cert.title == "Custom Title"


def test_certificate_info_title_too_short_fails():
    with pytest.raises(ValidationError):
        CertificateInfo(
            title="",
            event_name="Test Event",
            issued_by="Test Issuer",
            issue_date=date(2024, 1, 1),
        )


def test_certificate_info_title_too_long_fails():
    with pytest.raises(ValidationError):
        CertificateInfo(
            title="a" * 121,
            event_name="Test Event",
            issued_by="Test Issuer",
            issue_date=date(2024, 1, 1),
        )


def test_job_create_request_accepts_recipient_dictionaries():
    request = JobCreateRequest(
        certificate={
            "title": "Certificate",
            "event_name": "Event",
            "issued_by": "Issuer",
            "issue_date": "2024-01-01",
        },
        recipients=[
            {"name": "John Doe", "email": "john@example.com"},
            {"name": "Jane Smith"},
            {"name": "Invalid", "email": "not-an-email"},
        ],
    )
    assert len(request.recipients) == 3
    assert request.recipients[0]["name"] == "John Doe"
    assert request.recipients[1]["name"] == "Jane Smith"
    assert request.recipients[2]["name"] == "Invalid"


def test_validate_recipient_valid():
    recipient, error = validate_recipient(
        {"name": "John Doe", "email": "john@example.com"}
    )
    assert recipient is not None
    assert error is None
    assert recipient.name == "John Doe"
    assert recipient.email == "john@example.com"


def test_validate_recipient_invalid_returns_error():
    recipient, error = validate_recipient({"name": "", "email": "john@example.com"})
    assert recipient is None
    assert error is not None
    assert "Name cannot be blank" in error


def test_validate_recipient_invalid_email_returns_error():
    recipient, error = validate_recipient({"name": "John Doe", "email": "invalid"})
    assert recipient is None
    assert error is not None
