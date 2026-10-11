"""Two bounded preview-navigation indexes with synchronized browsing.

Dates are a compact temporal outline (years, months, observed days). Physical
pages use a separate ruler. Scrolling a ruler browses both indexes without
moving the album; clicking commits the chosen destination. Scrolling the album
repositions both indexes. Visible entries are painted directly rather than
creating one widget per date or page.
"""
from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass

from PySide6.QtCore import QPoint, QRect, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget

from photoalbum.i18n import Translator


@dataclass(frozen=True)
class NavigationPage:
    """One physical page and its known dates (no image data)."""

    date_label: str
    year: int | None = None
    month: int | None = None
    day: int | None = None
    divider_level: str | None = None
    dates: tuple[tuple[int, int, int], ...] = ()
    short_label: str = ""
    page_label: str = ""
    page_number: int | None = None


@dataclass(frozen=True)
class _DateEntry:
    kind: str
    short_label: str
    full_label: str
    page_index: int
    period: tuple[int, ...]


class _RulerCallout(QWidget):
    """In-app page/date tooltip, drawn as one continuous pointed outline."""

    WIDTH = 194
    HEIGHT = 58
    TIP = 12
    TEXT_TOP = 31

    def __init__(self, parent: QWidget, *, side: str) -> None:
        super().__init__(parent)
        self._side = side
        self._first_line = ""
        self._second_line = ""
        self._arrow_y = self.HEIGHT / 2
        self.setFixedSize(self.WIDTH, self.HEIGHT)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.hide()

    def _body_edges(self) -> tuple[float, float]:
        if self._side == "left":
            return float(self.TIP + 1), float(self.WIDTH - 1)
        return 1.0, float(self.WIDTH - self.TIP - 1)

    def _text_geometry(self) -> tuple[int, int]:
        left, right = self._body_edges()
        return int(left + 9), int(right - left - 18)

    def _date_height(self) -> int:
        """Allow long dates and explicit ranges to occupy multiple lines."""
        _left, width = self._text_geometry()
        metrics = QFontMetrics(self.font())
        return metrics.boundingRect(
            QRect(0, 0, width, 2048),
            int(Qt.TextFlag.TextWordWrap),
            self._second_line,
        ).height()

    def display(self, page_text: str, date_text: str, anchor: QPoint) -> None:
        parent = self.parentWidget()
        if parent is None:
            return
        self._first_line = page_text
        self._second_line = date_text
        desired_height = max(self.HEIGHT, self.TEXT_TOP + self._date_height() + 10)
        if self.height() != desired_height:
            self.setFixedHeight(desired_height)
        if self._side == "left":
            x = anchor.x()  # Panel opens towards the album, to the right.
        else:
            x = anchor.x() - self.WIDTH  # Panel opens to the left.
        x = max(0, min(max(0, parent.width() - self.WIDTH), x))
        y = max(2, min(max(2, parent.height() - self.height() - 2),
                       anchor.y() - self.height() // 2))
        # Keep the point clear of the rounded corners, including near the
        # first/last ruler entry.
        self._arrow_y = max(16, min(self.height() - 16, anchor.y() - y))
        self.move(x, y)
        self.raise_()
        self.show()
        self.update()

    def _outline_path(self) -> QPainterPath:
        """One closed contour, without the former rectangle/triangle seam."""
        left, right = self._body_edges()
        top, bottom, radius = 1.5, self.height() - 1.5, 7.0
        point = 1.5 if self._side == "left" else self.WIDTH - 1.5
        mid, half = self._arrow_y, 7.0
        path = QPainterPath()
        path.moveTo(left + radius, top)
        path.lineTo(right - radius, top)
        path.quadTo(right, top, right, top + radius)
        if self._side == "right":
            path.lineTo(right, mid - half)
            path.lineTo(point, mid)
            path.lineTo(right, mid + half)
        path.lineTo(right, bottom - radius)
        path.quadTo(right, bottom, right - radius, bottom)
        path.lineTo(left + radius, bottom)
        path.quadTo(left, bottom, left, bottom - radius)
        if self._side == "left":
            path.lineTo(left, mid + half)
            path.lineTo(point, mid)
            path.lineTo(left, mid - half)
        path.lineTo(left, top + radius)
        path.quadTo(left, top, left + radius, top)
        path.closeSubpath()
        return path

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        base = self.palette().base().color()
        border = self.palette().highlight().color()
        text = self.palette().text().color()
        secondary = QColor(text)
        secondary.setAlpha(185)
        painter.setPen(QPen(border, 1))
        painter.setBrush(base)
        painter.drawPath(self._outline_path())

        text_left, text_width = self._text_geometry()
        font = QFont(self.font())
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(text)
        painter.drawText(text_left, 10, text_width, 18,
                         Qt.AlignmentFlag.AlignVCenter, self._first_line)
        font.setBold(False)
        painter.setFont(font)
        painter.setPen(secondary)
        painter.drawText(
            QRect(text_left, self.TEXT_TOP, text_width,
                  self.height() - self.TEXT_TOP - 6),
            int(Qt.AlignmentFlag.AlignLeft | Qt.TextFlag.TextWordWrap),
            self._second_line,
        )
        painter.end()


class PreviewNavigationRuler(QWidget):
    """A bounded physical-page (left) or date (right) navigation strip.

    The rulers occupy the full preview height. Both stop at the first and
    last entry; the active entry remains visible without looping around.
    """

    page_activated = Signal(int)  # Physical index, including covers.
    page_explored = Signal(int, int)  # Physical index; selected date row, or -1.
    WIDTH = 54
    PAGE_HEIGHT = 25
    YEAR_HEIGHT = 31
    MONTH_HEIGHT = 27
    DAY_HEIGHT = 7
    YEAR_FONT_SIZE = 16
    MONTH_FONT_SIZE = 12
    PAGE_FONT_SIZE = 12

    def __init__(
        self, translator: Translator, parent: QWidget | None = None, *,
        mode: str = "date",
    ) -> None:
        super().__init__(parent)
        if mode not in ("date", "page"):
            raise ValueError(mode)
        self._translator = translator
        self._mode = mode
        self._pages: tuple[NavigationPage, ...] = ()
        self._date_entries: tuple[_DateEntry, ...] = ()
        self._date_period_indices: dict[tuple[int, ...], int] = {}
        self._date_page_indices: tuple[int, ...] = ()
        self._row_tops: tuple[int, ...] = (0,)
        self._enabled_dividers: frozenset[str] = frozenset()
        self._numbered_pages = 0
        self._current_index = 0
        self._date_cursor = 0
        # The preview's position and the independently browsed position must
        # not be conflated: scrolling either ruler never scrolls the album.
        self._explore_index: int | None = None
        self._explore_date_cursor: int | None = None
        self._hover: int | None = None
        self._dragging: tuple[float, int, bool] | None = None
        self._requested_date: int | None = None
        self._callout = (_RulerCallout(parent, side="right" if mode == "date" else "left")
                         if parent is not None else None)
        self.setFixedWidth(self.WIDTH)
        self.setMouseTracking(True)
        self.setAccessibleName(self._translator.tr("preview.navigation.name"))

    def sizeHint(self) -> QSize:
        return QSize(self.WIDTH, 300)

    def set_pages(
        self,
        pages: list[NavigationPage] | tuple[NavigationPage, ...], *,
        enabled_dividers: tuple[str, ...] = (),
    ) -> None:
        self._pages = tuple(pages)
        self._enabled_dividers = frozenset(enabled_dividers)
        self._date_entries = self._make_dates() if self._mode == "date" else ()
        self._date_period_indices = {
            item.period: i for i, item in enumerate(self._date_entries)
        }
        self._date_page_indices = tuple(item.page_index for item in self._date_entries)
        self._numbered_pages = sum(page.page_number is not None for page in self._pages)
        # Prefix offsets give O(log N + visible rows) painting and hit-testing,
        # even for albums containing thousands of physical pages.
        tops = [0]
        for index in range(self._count()):
            tops.append(tops[-1] + self._item_height(index))
        self._row_tops = tuple(tops)
        self._current_index = 0
        self._date_cursor = self._date_cursor_for_page(0) if self._pages else 0
        self._explore_index = None
        self._explore_date_cursor = None
        self._hover = None
        self._dragging = None
        self._requested_date = None
        self._hide_callout()
        self.setEnabled(bool(self._date_entries) if self._mode == "date" else bool(self._pages))
        self.update()

    def _make_dates(self) -> tuple[_DateEntry, ...]:
        """Only existing years, months and observed days; no empty calendar days."""
        entries: list[_DateEntry] = []
        seen: set[tuple[int, ...]] = set()
        for page_index, page in enumerate(self._pages):
            candidates_dates = page.dates or ((page.year, page.month, page.day),)
            for year, month, day in candidates_dates:
                if year is None:
                    continue
                candidates = [("year", (year,), str(year), str(year))]
                if month is not None:
                    name = self._translator.month_name(month)
                    # Keep the year legible even when the annual heading is
                    # outside the visible part of the date navigation strip.
                    candidates.append(("month", (year, month),
                                       f"{name[:3].lower()} {year % 100:02d}",
                                       f"{name} {year}"))
                if month is not None and day is not None:
                    candidates.append(("day", (year, month, day), str(day),
                                       f"{day} {self._translator.month_name(month)} {year}"))
                for kind, period, short, full in candidates:
                    if period not in seen:
                        seen.add(period)
                        entries.append(_DateEntry(kind, short, full, page_index, period))
        return tuple(entries)

    def _date_cursor_for_page(self, page_index: int) -> int:
        if not self._date_entries or not self._pages:
            return 0
        page = self._pages[page_index]
        if page.year is not None:
            for key in ((page.year, page.month, page.day),
                        (page.year, page.month), (page.year,)):
                if None not in key and key in self._date_period_indices:
                    return self._date_period_indices[key]
        return max(0, bisect_right(self._date_page_indices, page_index) - 1)

    def set_current_index(self, index: int) -> None:
        if not self._pages:
            return
        new_index = max(0, min(len(self._pages) - 1, index))
        if new_index != self._current_index:
            self._current_index = new_index
            self._date_cursor = self._date_cursor_for_page(new_index)
            self.update()
        if (self._mode == "date" and self._requested_date is not None
                and self._date_entries[self._requested_date].page_index == new_index):
            self._date_cursor = self._requested_date
            self.update()

    def set_explored_index(self, page_index: int, *, date_entry: int = -1) -> None:
        """Browse a position without changing the album's displayed page.

        The initiating ruler may preserve an exact year/month/day row, whereas
        the companion ruler is positioned using its corresponding page/date.
        """
        if not self._pages:
            return
        page_index = max(0, min(len(self._pages) - 1, page_index))
        self._explore_index = page_index
        if self._mode == "date":
            if 0 <= date_entry < len(self._date_entries):
                self._explore_date_cursor = date_entry
            else:
                self._explore_date_cursor = self._date_cursor_for_page(page_index)
        self.update()

    def clear_exploration(self) -> None:
        if self._explore_index is None:
            return
        self._explore_index = None
        self._explore_date_cursor = None
        self._hover = None
        self._hide_callout()
        self.update()

    def _count(self) -> int:
        return len(self._date_entries) if self._mode == "date" else len(self._pages)

    def _cursor(self) -> int:
        if self._mode == "date":
            return (self._explore_date_cursor if self._explore_date_cursor is not None
                    else self._date_cursor)
        return (self._explore_index if self._explore_index is not None
                else self._current_index)

    def _preview_cursor(self) -> int:
        """Row of the actual preview, regardless of ruler-only exploration."""
        return self._date_cursor if self._mode == "date" else self._current_index

    def _item_height(self, index: int) -> int:
        if self._mode == "page":
            return self.PAGE_HEIGHT
        kind = self._date_entries[index].kind
        return {"year": self.YEAR_HEIGHT, "month": self.MONTH_HEIGHT,
                "day": self.DAY_HEIGHT}[kind]

    def _visible_rows(self) -> list[tuple[int, float, float]]:
        """Visible (index, centre, height) rows in a non-wrapping list.

        The selected row is centred when there is room on both sides. Near
        either boundary the viewport stays within the content, so no entries
        repeat and the first/last page can sit at the top/bottom respectively.
        Short date indexes start at the top of their strip; short page indexes
        retain their existing centred presentation.
        """
        count = self._count()
        if not count:
            return []
        viewport_height = self.height()
        total_height = self._row_tops[-1]
        if total_height <= viewport_height:
            scroll_top = (0.0 if self._mode == "date"
                          else -(viewport_height - total_height) / 2)
        else:
            current = self._cursor()
            selected_y = (self._row_tops[current] + self._row_tops[current + 1]) / 2
            scroll_top = max(0.0, min(total_height - viewport_height,
                                      selected_y - viewport_height / 2))

        first = max(0, bisect_right(self._row_tops, scroll_top) - 1)
        rows: list[tuple[int, float, float]] = []
        for index in range(first, count):
            top = self._row_tops[index] - scroll_top
            if top >= viewport_height:
                break
            height = self._item_height(index)
            if top + height > 0:
                rows.append((index, top + height / 2, height))
        return rows

    def _hit_at(self, y: float) -> tuple[int, float] | None:
        for index, center, height in self._visible_rows():
            if center - height / 2 <= y < center + height / 2:
                return index, center
        return None

    def _row_center_for(self, index: int) -> float:
        for row_index, center, _height in self._visible_rows():
            if row_index == index:
                return center
        return self.height() / 2

    def _page_for(self, index: int) -> int:
        return self._date_entries[index].page_index if self._mode == "date" else index

    def _page_caption(self, index: int) -> str:
        page = self._pages[index]
        if page.page_label:
            return page.page_label
        return self._translator.tr("preview.navigation.page",
                                   page=page.page_number or index + 1,
                                   total=self._numbered_pages or len(self._pages))

    def _update_callout(self, index: int, row_y: float) -> None:
        if self._callout is None or not self._pages:
            return
        page_index = self._page_for(index)
        page = self._pages[page_index]
        date = (self._date_entries[index].full_label if self._mode == "date"
                else page.date_label or "—")
        if self._mode == "page" and " – " in date:
            start, end = date.split(" – ", 1)
            date = self._translator.tr(
                "preview.navigation.date_range", start=start, end=end,
            )
        x = 0 if self._mode == "date" else self.width()
        anchor = self.mapTo(self.parentWidget(), QPoint(x, round(row_y)))
        self._callout.display(self._page_caption(page_index), date, anchor)

    def _hide_callout(self) -> None:
        if self._callout is not None:
            self._callout.hide()

    def _hover_at(self, y: float) -> None:
        hit = self._hit_at(y)
        if hit is None:
            self._hover = None
            self._hide_callout()
        else:
            self._hover = hit[0]
            self._update_callout(*hit)
        self.update()

    def _explore(self, index: int) -> None:
        """Synchronize the two indexes, without emitting a page activation."""
        count = self._count()
        if not count:
            return
        index = max(0, min(count - 1, index))
        page = self._page_for(index)
        date_entry = index if self._mode == "date" else -1
        self.set_explored_index(page, date_entry=date_entry)
        self.page_explored.emit(page, date_entry)

    def _choose(self, index: int) -> None:
        """Click/Return commits a destination to the preview."""
        count = self._count()
        if not count:
            return
        index = max(0, min(count - 1, index))
        page = self._page_for(index)
        if self._mode == "date":
            self._date_cursor = index
            self._requested_date = index
        else:
            self._current_index = page
        self.update()
        try:
            self.page_activated.emit(page)
        finally:
            self._requested_date = None
            # Standalone rulers also finish browsing on selection.
            self.clear_exploration()

    def wheelEvent(self, event) -> None:
        steps = int(event.angleDelta().y() / 120)
        if not steps and event.pixelDelta().y():
            steps = 1 if event.pixelDelta().y() > 0 else -1
        if steps and self._count():
            destination = max(0, min(self._count() - 1, self._cursor() - steps))
            if destination != self._cursor():
                self._explore(destination)
            # The panel describes the explored entry (not an unrelated line
            # under a stationary mouse after the content has scrolled).
            self._hover = self._cursor()
            self._update_callout(self._cursor(),
                                 self._row_center_for(self._cursor()))
            self.update()
        event.accept()

    def mouseMoveEvent(self, event) -> None:
        y = event.position().y()
        if self._dragging is None:
            self._hover_at(y)
        else:
            start_y, start_index, was_dragged = self._dragging
            if not was_dragged and abs(start_y - y) >= 5:
                was_dragged = True
                self._dragging = (start_y, start_index, was_dragged)
            if was_dragged:
                # Dragging explores both indexes, just like the wheel.  A
                # press/release without a drag is the only click that commits.
                step_pixels = 12 if self._mode == "date" else self.PAGE_HEIGHT
                destination = start_index + round((start_y - y) / step_pixels)
                destination = max(0, min(self._count() - 1, destination))
                if destination != self._cursor() or self._explore_index is None:
                    self._explore(destination)
                self._hover = self._cursor()
                self._update_callout(self._cursor(),
                                     self._row_center_for(self._cursor()))
                self.update()
        event.accept()

    def mousePressEvent(self, event) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return super().mousePressEvent(event)
        hit = self._hit_at(event.position().y())
        if hit is None:
            event.ignore()
            return
        self._dragging = (event.position().y(), hit[0], False)
        self._hover = hit[0]
        self._update_callout(*hit)
        self.update()
        event.accept()

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._dragging is not None:
            _start_y, pressed_index, was_dragged = self._dragging
            self._dragging = None
            if not was_dragged:
                hit = self._hit_at(event.position().y())
                if hit is not None and hit[0] == pressed_index:
                    self._choose(hit[0])
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def leaveEvent(self, event) -> None:
        if self._dragging is None:
            self._hover = None
            self._hide_callout()
            self.update()
        super().leaveEvent(event)

    def hideEvent(self, event) -> None:
        self._hide_callout()
        super().hideEvent(event)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        base = self.palette().base().color()
        ink = self.palette().text().color()
        accent = self.palette().highlight().color()
        quiet = QColor(ink)
        quiet.setAlpha(160)
        painter.fillRect(self.rect(), base)
        # Subtle inner edges separate the left page index from the preview
        # and the right date index from the preview.
        frame_pen = QPen(self.palette().mid().color(), 1)
        painter.setPen(frame_pen)
        if self._mode == "page":
            painter.drawLine(self.WIDTH - 1, 0, self.WIDTH - 1, self.height())
        else:
            painter.drawLine(0, 0, 0, self.height())
        if not self._count():
            painter.end()
            return
        rows = self._visible_rows()
        current = self._cursor()
        for index, center, height in sorted(rows, key=lambda row: row[1]):
            if center + height / 2 < 0 or center - height / 2 > self.height():
                continue
            selected = index == current
            hovered = self._hover == index
            if selected:
                wash = QColor(accent)
                wash.setAlpha(28 if self._explore_index is not None else 43)
                painter.fillRect(1, round(center - height / 2), self.WIDTH - 2,
                                 round(height), wash)
            elif hovered:
                wash = QColor(quiet)
                wash.setAlpha(25)
                painter.fillRect(1, round(center - height / 2), self.WIDTH - 2,
                                 round(height), wash)
            if self._mode == "date":
                item = self._date_entries[index]
                if item.kind == "day":
                    # No text for days: one observed day is one fine, compact tick.
                    painter.setPen(QPen(accent if selected or hovered else quiet,
                                        2 if selected or hovered else 1))
                    painter.drawLine(19 if selected or hovered else 24, round(center),
                                     self.WIDTH - 7, round(center))
                else:
                    font = QFont(self.font())
                    font.setPixelSize(self.YEAR_FONT_SIZE if item.kind == "year"
                                      else self.MONTH_FONT_SIZE)
                    font.setBold(item.kind == "year" or selected)
                    painter.setFont(font)
                    # Both months and years use the same blue as selected pages.
                    painter.setPen(accent)
                    painter.drawText(1, round(center - height / 2), self.WIDTH - 3,
                                     round(height), Qt.AlignmentFlag.AlignCenter,
                                     item.short_label)
            else:
                label = self._pages[index].short_label or str(
                    self._pages[index].page_number or index + 1)
                font = QFont(self.font())
                font.setPixelSize(self.PAGE_FONT_SIZE)
                font.setBold(selected)
                painter.setFont(font)
                painter.setPen(accent if selected else quiet)
                painter.drawText(1, round(center - height / 2), self.WIDTH - 3,
                                 round(height), Qt.AlignmentFlag.AlignCenter, label)
        painter.end()
