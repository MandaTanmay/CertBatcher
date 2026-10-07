import re
from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, EmailStr, Field, TypeAdapter, field_validator

CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f-\x9f]")
FIELD_KEY = re.compile(r"^[a-z][a-z0-9_]{0,39}$")
MAX_CUSTOM_FIELDS = 20
FieldType = Literal["text", "email", "number", "date"]


class CertificateInfo(BaseModel):
    title: str = Field(
        default="Certificate of Completion", min_length=1, max_length=120
    )
    event_name: str = Field(min_length=1, max_length=200)
    issued_by: str = Field(min_length=1, max_length=200)
    issue_date: date


class FieldDefinition(BaseModel):
    key: str = Field(pattern=FIELD_KEY.pattern, min_length=1, max_length=40)
    label: str = Field(min_length=1, max_length=80)
    type: FieldType = "text"
    required: bool = False


class RecipientIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    email: EmailStr | None = None
    data: dict[str, Any] = Field(default_factory=dict)

    @field_validator("name", mode="before")
    @classmethod
    def validate_name(cls, v: Any) -> str:
        if not isinstance(v, str):
            raise ValueError("Name must be a string")

        name = v.strip()

        if not name:
            raise ValueError("Name cannot be blank")

        if CONTROL_CHARS.search(name):
            raise ValueError("Name cannot contain control characters")

        name = re.sub(r"\s+", " ", name)

        return name


class JobCreateRequest(BaseModel):
    certificate: CertificateInfo
    fields: list[FieldDefinition] = Field(
        default_factory=list, max_length=MAX_CUSTOM_FIELDS
    )
    recipients: list[dict[str, Any]]

    @field_validator("fields")
    @classmethod
    def validate_fields(cls, fields: list[FieldDefinition]) -> list[FieldDefinition]:
        keys = [field.key for field in fields]
        if len(keys) != len(set(keys)):
            raise ValueError("Custom field keys must be unique")
        if "name" in keys or "email" in keys:
            raise ValueError("Custom field keys cannot replace name or email")
        return fields


def validate_recipient(
    raw: dict[str, Any],
    fields: list[FieldDefinition] | None = None,
) -> tuple[RecipientIn | None, str | None]:
    try:
        fields = fields or []
        source_data = raw.get("data", {})
        if not isinstance(source_data, dict):
            raise ValueError("Recipient data must be an object")
        custom_data = {
            field.key: source_data.get(field.key, raw.get(field.key))
            for field in fields
        }
        for field in fields:
            value = custom_data[field.key]
            if value in (None, ""):
                if field.required:
                    raise ValueError(f"{field.label} is required")
                custom_data[field.key] = None
                continue
            if field.type == "text":
                if not isinstance(value, str):
                    raise ValueError(f"{field.label} must be text")
                custom_data[field.key] = value.strip()
            elif field.type == "email":
                custom_data[field.key] = str(
                    TypeAdapter(EmailStr).validate_python(value)
                )
            elif field.type == "number":
                try:
                    custom_data[field.key] = float(value)
                except (TypeError, ValueError):
                    raise ValueError(f"{field.label} must be a number") from None
            elif field.type == "date":
                try:
                    custom_data[field.key] = date.fromisoformat(str(value)).isoformat()
                except ValueError:
                    raise ValueError(f"{field.label} must be a valid date") from None
        recipient = RecipientIn.model_validate(
            {"name": raw.get("name"), "email": raw.get("email"), "data": custom_data}
        )
        return recipient, None
    except Exception as e:
        return None, str(e)


class JobCreatedResponse(BaseModel):
    id: str
    status: str
    total: int
    status_url: str


class Counts(BaseModel):
    total: int
    succeeded: int
    failed: int
    pending: int


class JobStatusResponse(BaseModel):
    id: str
    status: str
    total: int
    counts: Counts
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    error: str | None
    fields: list[FieldDefinition] = Field(default_factory=list)


class CertificateResult(BaseModel):
    id: str
    row_index: int
    recipient_name: str | None
    recipient_email: str | None
    status: str
    error_message: str | None
    file_path: str | None
    generated_at: datetime | None
    data: dict[str, Any] = Field(default_factory=dict)


class CertificateResultsResponse(BaseModel):
    job_id: str
    items: list[CertificateResult]


class FailureItem(BaseModel):
    row_index: int
    recipient_name: str | None
    error: str
