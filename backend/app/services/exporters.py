import html
import io
import re
from datetime import UTC, datetime
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer


def export_report_markdown(
    *,
    title: str,
    query: str,
    summary: str,
    content: str,
    is_demo_mode: bool,
    validation_status: str,
    created_at: datetime | None = None,
) -> str:
    """Render a clean downloadable Markdown document with provenance header."""
    timestamp = (created_at or datetime.now(UTC)).strftime("%Y-%m-%d %H:%M UTC")
    notice = (
        "> **DEMO / SAMPLE DATA NOTICE:** Generated with mock providers for demonstration/testing.\n\n"
        if is_demo_mode
        else ""
    )
    header = (
        f"---\n"
        f'title: "{title.replace(chr(34), chr(39))}"\n'
        f'query: "{query.replace(chr(34), chr(39))}"\n'
        f"generated_at: {timestamp}\n"
        f"citation_status: {validation_status}\n"
        f"demo_mode: {str(is_demo_mode).lower()}\n"
        f"---\n\n"
    )
    return f"{header}{notice}{content.strip()}\n"


def _md_inline_to_reportlab(text: str) -> str:
    escaped = html.escape(text, quote=False)
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", escaped)
    escaped = re.sub(r"\*(.+?)\*", r"<i>\1</i>", escaped)
    escaped = re.sub(r"`(.+?)`", r'<font face="Courier">\1</font>', escaped)
    return escaped


def export_report_pdf(
    *,
    title: str,
    query: str,
    content: str,
    is_demo_mode: bool,
    validation_status: str,
    created_at: datetime | None = None,
) -> bytes:
    """Render a structured, readable PDF report using ReportLab."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=LETTER,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
        title=title,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ORATitle",
        parent=styles["Title"],
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#0F172A"),
        spaceAfter=10,
    )
    meta_style = ParagraphStyle(
        "ORAMeta",
        parent=styles["Normal"],
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#475569"),
        spaceAfter=12,
    )
    h2_style = ParagraphStyle(
        "ORAH2",
        parent=styles["Heading2"],
        fontSize=13,
        leading=16,
        textColor=colors.HexColor("#1E293B"),
        spaceBefore=12,
        spaceAfter=6,
    )
    h3_style = ParagraphStyle(
        "ORAH3",
        parent=styles["Heading3"],
        fontSize=11,
        leading=14,
        textColor=colors.HexColor("#334155"),
        spaceBefore=8,
        spaceAfter=4,
    )
    body_style = ParagraphStyle(
        "ORABody",
        parent=styles["Normal"],
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#1E293B"),
        spaceAfter=6,
    )
    quote_style = ParagraphStyle(
        "ORAQuote",
        parent=body_style,
        leftIndent=14,
        textColor=colors.HexColor("#475569"),
        fontSize=9.5,
    )

    story: list[Any] = []
    timestamp = (created_at or datetime.now(UTC)).strftime("%Y-%m-%d %H:%M UTC")
    story.append(Paragraph(_md_inline_to_reportlab(title), title_style))
    meta_text = (
        f"Research Query: {html.escape(query)}<br/>"
        f"Generated: {timestamp} | Citation Validation: {html.escape(validation_status)}"
    )
    if is_demo_mode:
        meta_text += " | <b>DEMO / SAMPLE DATA</b>"
    story.append(Paragraph(meta_text, meta_style))
    story.append(Spacer(1, 6))

    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line:
            story.append(Spacer(1, 4))
            continue
        if line.startswith("# "):
            continue  # Title already rendered
        if line.startswith("## "):
            story.append(Paragraph(_md_inline_to_reportlab(line[3:].strip()), h2_style))
        elif line.startswith("### "):
            story.append(Paragraph(_md_inline_to_reportlab(line[4:].strip()), h3_style))
        elif line.startswith("> "):
            story.append(Paragraph(_md_inline_to_reportlab(line[2:].strip()), quote_style))
        elif line.startswith(("- ", "* ")):
            story.append(
                Paragraph(f"• {_md_inline_to_reportlab(line[2:].strip())}", body_style)
            )
        elif line.startswith("|") and line.endswith("|"):
            if set(line.replace("|", "").replace("-", "").replace(":", "").strip()) == set():
                continue
            cells = [c.strip() for c in line.strip("|").split("|")]
            story.append(
                Paragraph(_md_inline_to_reportlab("  |  ".join(cells)), quote_style)
            )
        else:
            story.append(Paragraph(_md_inline_to_reportlab(line), body_style))

    doc.build(story)
    return buffer.getvalue()
