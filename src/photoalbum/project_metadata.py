from __future__ import annotations

from dataclasses import dataclass
import json


PDF_EXPORT_CONTENT_VALUES = frozenset({"complete", "covers", "body"})
PDF_EXPORT_DPI_VALUES = frozenset({96, 150, 300, 600})


@dataclass(frozen=True)
class ProjectPdfMetadata:
    title: str = ""
    author: str = ""
    subject: str = ""
    keywords: str = ""


@dataclass(frozen=True)
class PdfExportSettings:
    """Project-level preferences for PDF generation."""

    metadata: ProjectPdfMetadata = ProjectPdfMetadata()
    dpi: int = 300
    content: str = "complete"


def pdf_export_settings_to_json(settings: PdfExportSettings) -> str:
    return json.dumps(
        {
            "metadata": {
                "title": settings.metadata.title,
                "author": settings.metadata.author,
                "subject": settings.metadata.subject,
                "keywords": settings.metadata.keywords,
            },
            "dpi": settings.dpi,
            "content": settings.content,
        },
        ensure_ascii=False,
        sort_keys=True,
    )


def pdf_export_settings_from_json(value: str) -> PdfExportSettings:
    data = json.loads(value)
    if not isinstance(data, dict):
        raise ValueError("PDF export settings must be a JSON object.")

    raw_metadata = data.get("metadata", {})
    if not isinstance(raw_metadata, dict):
        raw_metadata = {}

    metadata = ProjectPdfMetadata(
        title=str(raw_metadata.get("title", "")),
        author=str(raw_metadata.get("author", "")),
        subject=str(raw_metadata.get("subject", "")),
        keywords=str(raw_metadata.get("keywords", "")),
    )

    try:
        dpi = int(data.get("dpi", 300))
    except (TypeError, ValueError):
        dpi = 300
    if dpi not in PDF_EXPORT_DPI_VALUES:
        dpi = 300

    content = str(data.get("content", "complete"))
    if content not in PDF_EXPORT_CONTENT_VALUES:
        content = "complete"

    return PdfExportSettings(metadata=metadata, dpi=dpi, content=content)
