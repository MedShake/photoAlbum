from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import QDateTime, QLocale


def _time_format_with_seconds(locale: QLocale) -> str:
    """Return the locale short time format with seconds."""
    pattern = locale.timeFormat(QLocale.FormatType.ShortFormat)
    if "s" in pattern:
        return pattern
    if "AP" in pattern:
        return pattern.replace(" AP", ":ss AP")
    if "ap" in pattern:
        return pattern.replace(" ap", ":ss ap")
    return pattern + ":ss"


def format_datetime(
    value: datetime,
    *,
    include_seconds: bool = False,
) -> str:
    """Format a date and time using the system locale."""
    locale = QLocale.system()
    qdatetime = QDateTime(value)

    date_format = QLocale.FormatType.ShortFormat

    text = locale.toString(
        qdatetime,
        date_format,
    )

    if include_seconds:
        # ShortFormat commonly omits seconds. Use the locale's
        # own date and time patterns while explicitly requesting
        # seconds for detailed views.
        date_pattern = locale.dateFormat(
            QLocale.FormatType.ShortFormat
        )
        time_pattern = _time_format_with_seconds(locale)

        text = locale.toString(
            qdatetime,
            f"{date_pattern} {time_pattern}",
        )

    return text


def datetime_edit_format() -> str:
    """Return the system-locale pattern for a date-time editor."""
    locale = QLocale.system()

    date_pattern = locale.dateFormat(
        QLocale.FormatType.ShortFormat
    )
    time_pattern = _time_format_with_seconds(locale)

    return f"{date_pattern} {time_pattern}"
