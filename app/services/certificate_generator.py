from io import BytesIO
from typing import TYPE_CHECKING

from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas

from app.schemas import CertificateInfo, FieldDefinition

if TYPE_CHECKING:
    from reportlab.pdfgen.canvas import Canvas


def generate_certificate_pdf(
    name: str,
    info: CertificateInfo,
    certificate_id: str,
    fields: list[FieldDefinition] | None = None,
    data: dict[str, object] | None = None,
) -> bytes:
    """
    Generate a certificate PDF and return it as bytes.

    Args:
        name: Recipient name (must not be empty or whitespace-only)
        info: Certificate information
        certificate_id: Unique certificate identifier

    Returns:
        PDF bytes

    Raises:
        ValueError: If name is empty or whitespace-only
    """
    if not name or not name.strip():
        raise ValueError("Recipient name cannot be empty")

    name = name.strip()

    buffer = BytesIO()
    page_width, page_height = landscape(A4)
    c = canvas.Canvas(buffer, pagesize=landscape(A4))

    margin = 0.5 * inch
    content_width = page_width - 2 * margin

    c.setLineWidth(3)
    c.rect(margin, margin, content_width, page_height - 2 * margin)

    c.setFont("Helvetica-Bold", 36)
    c.drawCentredString(page_width / 2, page_height - 2 * inch, info.title)

    c.setFont("Helvetica", 18)
    c.drawCentredString(
        page_width / 2,
        page_height - 2.6 * inch,
        "This certificate is proudly presented to",
    )

    _draw_name_with_font_scaling(
        c, name, page_width / 2, page_height - 3.5 * inch, content_width
    )

    c.setFont("Helvetica", 18)
    c.drawCentredString(
        page_width / 2, page_height - 4.2 * inch, "for successfully completing"
    )

    c.setFont("Helvetica-Bold", 24)
    c.drawCentredString(page_width / 2, page_height - 4.8 * inch, info.event_name)

    field_y = page_height - 5.35 * inch
    for field in fields or []:
        value = (data or {}).get(field.key)
        if value not in (None, ""):
            field_y = _draw_wrapped_field(
                c, field.label, str(value), page_width / 2, field_y, content_width
            )
            field_y -= 14

    formatted_date = info.issue_date.strftime("%B %d, %Y")

    c.setFont("Helvetica", 16)
    left_x = page_width / 2 - 2 * inch
    right_x = page_width / 2 + 2 * inch
    bottom_y = 1.5 * inch

    c.drawCentredString(left_x, bottom_y, f"Issued by: {info.issued_by}")
    c.drawCentredString(right_x, bottom_y, f"Date: {formatted_date}")

    c.setFont("Helvetica-Oblique", 10)
    c.drawCentredString(
        page_width / 2, 0.75 * inch, f"Certificate ID: {certificate_id}"
    )

    c.save()
    buffer.seek(0)
    return buffer.getvalue()


def _draw_name_with_font_scaling(
    c: "Canvas",
    name: str,
    x: float,
    y: float,
    max_width: float,
) -> None:
    """
    Draw the recipient name with automatic font size scaling to fit within max_width.

    Starts at 48pt and reduces to minimum 18pt.
    """
    font_size = 48
    min_font_size = 18

    c.setFont("Helvetica-Bold", font_size)
    text_width = c.stringWidth(name, "Helvetica-Bold", font_size)

    while text_width > max_width and font_size > min_font_size:
        font_size -= 2
        c.setFont("Helvetica-Bold", font_size)
        text_width = c.stringWidth(name, "Helvetica-Bold", font_size)

    c.drawCentredString(x, y, name)


def _draw_wrapped_field(
    c: "Canvas",
    label: str,
    value: str,
    x: float,
    y: float,
    max_width: float,
) -> float:
    font_size = 13
    text = f"{label}: {value}"
    while font_size > 8 and c.stringWidth(text, "Helvetica", font_size) > max_width:
        font_size -= 1
    c.setFont("Helvetica", font_size)
    lines: list[str] = []
    current = ""
    for word in text.split():
        candidate = f"{current} {word}".strip()
        if current and c.stringWidth(candidate, "Helvetica", font_size) > max_width:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    for index, line in enumerate(lines[:3]):
        c.drawCentredString(x, y - index * (font_size + 2), line)
    return y - max(0, len(lines[:3]) - 1) * (font_size + 2)
