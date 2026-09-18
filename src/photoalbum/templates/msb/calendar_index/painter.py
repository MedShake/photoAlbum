from __future__ import annotations

from PySide6.QtCore import (
    QRectF,
    Qt,
)
from PySide6.QtGui import (
    QColor,
    QFont,
    QPainter,
)

from photoalbum.rendering.fonts import (
    DEFAULT_SANS_FONT,
    resolve_font_family,
)
from photoalbum.templates.msb.calendar_index.composition import (
    CalendarIndexComposition,
)
from photoalbum.i18n import Translator


def paint_calendar_index(
    painter: QPainter,
    *,
    target_rect,
    composition: CalendarIndexComposition,
    translator: Translator,
    page_width_mm: float,
    page_height_mm: float,
    show_title: bool = True,
) -> None:
    sx = (
        target_rect.width()
        / page_width_mm
    )
    sy = (
        target_rect.height()
        / page_height_mm
    )

    def rect_mm(
        x,
        y,
        width,
        height,
    ) -> QRectF:
        return QRectF(
            target_rect.x() + x * sx,
            target_rect.y() + y * sy,
            width * sx,
            height * sy,
        )

    def font_pt(
        points: float,
        *,
        bold: bool = False,
    ) -> QFont:
        font = QFont(
            resolve_font_family(
                DEFAULT_SANS_FONT
            )
        )

        font.setBold(
            bold
        )

        # Point size converted to preview pixels.
        mm = points * 25.4 / 72.0

        font.setPixelSize(
            max(
                5,
                round(
                    mm * sx
                ),
            )
        )

        return font

    # The year is the page title. 72 pt gives it real visual presence,
    # while a physical title band keeps the 12-month grid safely on-page.
    title_band_mm = 28.0 if show_title else 0.0

    if show_title:
        painter.setFont(font_pt(72, bold=True))
        painter.setPen(QColor(0, 141, 195))
        painter.drawText(
            rect_mm(10, 5, page_width_mm - 20, title_band_mm),
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            str(composition.year),
        )

    margin = 10.0
    column_spacing = 8.0

    columns = 2
    rows = 6

    page_area_width = (
        page_width_mm
        - 2 * margin
        - column_spacing
    )

    calendar_top = margin + title_band_mm
    page_area_height = page_height_mm - calendar_top - margin

    month_width = (
        page_area_width
        / columns
    )

    month_height = page_area_height / rows

    weekday_labels = (
        translator.tr(
            "calendar_index.mon"
        ),
        translator.tr(
            "calendar_index.tue"
        ),
        translator.tr(
            "calendar_index.wed"
        ),
        translator.tr(
            "calendar_index.thu"
        ),
        translator.tr(
            "calendar_index.fri"
        ),
        translator.tr(
            "calendar_index.sat"
        ),
        translator.tr(
            "calendar_index.sun"
        ),
    )

    for index, month in enumerate(
        composition.months
    ):
        column = index % 2
        row = index // 2

        x = (
            margin
            + column
            * (
                month_width
                + column_spacing
            )
        )

        y = calendar_top + row * month_height

        # ----------------------------------------------------
        # Month title + optional index page number.
        # ----------------------------------------------------

        month_name = (
            translator.month_name(
                month.month
            )
        )

        if month_name:
            month_name = (
                month_name[0].upper()
                + month_name[1:]
            )

        if month.page_number is not None:
            label = (
                f"{month_name} — "
                + translator.tr(
                    "calendar_index.page",
                    page=month.page_number,
                )
            )
        else:
            label = month_name

        painter.setFont(
            font_pt(
                8,
                bold=True,
            )
        )

        painter.setPen(
            Qt.GlobalColor.black
        )

        painter.drawText(
            rect_mm(
                x,
                y,
                month_width,
                5,
            ),
            Qt.AlignmentFlag.AlignCenter,
            label,
        )

        # ----------------------------------------------------
        # Weekday header.
        # ----------------------------------------------------

        week_column_width = 8.0
        day_width = (
            month_width
            - week_column_width
        ) / 7

        header_y = y + 5

        painter.setFont(
            font_pt(
                6
            )
        )

        for day_index, label in enumerate(
            weekday_labels
        ):
            cell = rect_mm(
                x
                + week_column_width
                + day_index
                * day_width,
                header_y,
                day_width,
                4,
            )

            painter.drawRect(
                cell
            )

            painter.drawText(
                cell,
                Qt.AlignmentFlag.AlignCenter,
                label,
            )

        # ----------------------------------------------------
        # Weeks and days.
        # ----------------------------------------------------

        for week_index, week in enumerate(
            month.weeks
        ):
            week_y = (
                header_y
                + 4
                + week_index * 4
            )

            week_rect = rect_mm(
                x,
                week_y,
                week_column_width,
                4,
            )

            painter.drawRect(
                week_rect
            )

            painter.drawText(
                week_rect,
                Qt.AlignmentFlag.AlignCenter,
                str(
                    week.week_number
                ),
            )

            for day_index, day in enumerate(
                week.days
            ):
                cell = rect_mm(
                    x
                    + week_column_width
                    + day_index
                    * day_width,
                    week_y,
                    day_width,
                    4,
                )

                if day.has_photo:
                    painter.fillRect(
                        cell,
                        QColor(
                            *month.color
                        ),
                    )

                painter.setPen(
                    Qt.GlobalColor.black
                )

                painter.drawRect(
                    cell
                )

                if day.day is not None:
                    painter.drawText(
                        cell,
                        Qt.AlignmentFlag.AlignCenter,
                        str(day.day),
                    )
