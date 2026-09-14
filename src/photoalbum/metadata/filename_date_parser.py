from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path


class FilenameDateParser:
    """
    Extract a capture date and optional time from a filename.

    The parser intentionally supports a limited set of explicit patterns.
    It should not guess ambiguous dates.
    """

    _PATTERNS = (
        # 2025-06-15_14-30-45
        (
            re.compile(
                r"(?P<year>\d{4})[-_.](?P<month>\d{2})[-_.](?P<day>\d{2})"
                r"(?:[T _-](?P<hour>\d{2})[-_.:]?(?P<minute>\d{2})"
                r"(?:[-_.:]?(?P<second>\d{2}))?)?"
            ),
            "separated",
        ),
        # 20250615_143045 or 20250615-143045
        (
            re.compile(
                r"(?P<year>\d{4})(?P<month>\d{2})(?P<day>\d{2})"
                r"(?:[T _-]?(?P<hour>\d{2})(?P<minute>\d{2})(?P<second>\d{2}))?"
            ),
            "compact",
        ),
    )

    def parse(self, filename: str | Path) -> datetime | None:
        name = Path(filename).stem

        for pattern, _pattern_name in self._PATTERNS:
            match = pattern.search(name)

            if match is None:
                continue

            parsed = self._build_datetime(match.groupdict())

            if parsed is not None:
                return parsed

        return None

    @staticmethod
    def _build_datetime(values: dict[str, str | None]) -> datetime | None:
        try:
            year = int(values["year"])
            month = int(values["month"])
            day = int(values["day"])

            hour = int(values["hour"]) if values.get("hour") else 0
            minute = int(values["minute"]) if values.get("minute") else 0
            second = int(values["second"]) if values.get("second") else 0

            return datetime(
                year,
                month,
                day,
                hour,
                minute,
                second,
            )

        except (TypeError, ValueError):
            return None

