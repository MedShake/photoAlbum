from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Sequence
from pathlib import Path

from PySide6.QtCore import (
    QEvent,
    QPoint,
    QRect,
    QSize,
    QTimer,
    Qt,
)
from PySide6.QtGui import (
    QBrush,
    QColor,
    QImageReader,
    QPixmap,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QComboBox,
    QRadioButton,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from photoalbum.geocoding.location_caption_builder import (
    LocationCaptionBuilder,
)
from photoalbum.gui.hover_photo_preview import HoverPhotoPreview
from photoalbum.gui.preview_image_cache import PreviewImageCache
from photoalbum.i18n import Translator
from photoalbum.i18n.date_formatter import (
    format_datetime,
)
from photoalbum.models import LocationComponent, Photo



class FlowLayout(QLayout):
    """Compact wrapping layout used for location components."""

    def __init__(
        self,
        parent=None,
        margin: int = 0,
        h_spacing: int = 10,
        v_spacing: int = 2,
    ) -> None:
        super().__init__(parent)

        if parent is not None:
            self.setContentsMargins(
                margin,
                margin,
                margin,
                margin,
            )

        self._items = []
        self._h_spacing = h_spacing
        self._v_spacing = v_spacing

    def __del__(self):
        while self.count():
            self.takeAt(0)

    def addItem(self, item) -> None:
        self._items.append(item)

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index):
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index):
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        return self._do_layout(
            QRect(0, 0, max(0, width), 0),
            True,
        )

    def setGeometry(self, rect: QRect) -> None:
        super().setGeometry(rect)
        self._do_layout(rect, False)

    def sizeHint(self) -> QSize:
        return self.minimumSize()

    def minimumSize(self) -> QSize:
        size = QSize()

        for item in self._items:
            size = size.expandedTo(
                item.minimumSize()
            )

        margins = self.contentsMargins()
        size += QSize(
            margins.left() + margins.right(),
            margins.top() + margins.bottom(),
        )
        return size

    def _do_layout(
        self,
        rect: QRect,
        test_only: bool,
    ) -> int:
        margins = self.contentsMargins()

        effective = rect.adjusted(
            margins.left(),
            margins.top(),
            -margins.right(),
            -margins.bottom(),
        )

        x = effective.x()
        y = effective.y()
        line_height = 0

        for item in self._items:
            widget = item.widget()

            if widget is None:
                continue

            hint = item.sizeHint()

            next_x = (
                x
                + hint.width()
                + self._h_spacing
            )

            if (
                line_height > 0
                and next_x - self._h_spacing
                > effective.right() + 1
            ):
                x = effective.x()
                y += line_height + self._v_spacing
                next_x = (
                    x
                    + hint.width()
                    + self._h_spacing
                )
                line_height = 0

            if not test_only:
                item.setGeometry(
                    QRect(
                        QPoint(x, y),
                        hint,
                    )
                )

            x = next_x
            line_height = max(
                line_height,
                hint.height(),
            )

        return (
            y
            + line_height
            - rect.y()
            + margins.bottom()
        )


class PhotoPlacesWidget(QWidget):
    """
    Chronological editorial view for photo locations and captions.

    The tree itself is the navigation model:
        undated photos
        year
            month
                photo

    Location and caption edits are persisted immediately, while
    filtering always reflects the final editorial values displayed
    to the user.
    """

    GROUP_LOCATION_PRIORITIES = {
        # Named places.
        "aerialway": 1,
        "tourism": 1,
        "amenity": 1,
        "historic": 1,
        "leisure": 1,
        "shop": 1,
        "building": 1,
        "office": 1,
        "attraction": 1,

        # Roads.
        "road": 2,
        "pedestrian": 2,
        "square": 2,
        "residential": 2,
        "footway": 2,
        "path": 2,

        # Local context.
        "neighbourhood": 3,
        "quarter": 3,
        "suburb": 3,
        "borough": 3,
        "city_district": 3,

        # Small localities.
        "hamlet": 4,
        "isolated_dwelling": 4,

        # Localities.
        "city": 5,
        "town": 5,
        "village": 5,
        "municipality": 5,

        # Administrative context.
        "county": 6,
        "state_district": 6,
        "state": 6,
        "region": 6,

        # Country.
        "country": 8,
    }

    HIDDEN_COMPONENT_KEYS = {
        "country_code",
        "house_number",
        "postcode",
    }

    PHOTO_ROLE = Qt.ItemDataRole.UserRole
    GROUP_ROLE = Qt.ItemDataRole.UserRole + 1

    THUMBNAIL_WIDTH = 72
    THUMBNAIL_HEIGHT = 54
    NATURAL_ROW_HEIGHT = 64

    def __init__(
        self,
        translator: Translator | None = None,
        save_location: Callable[
            [
                Photo,
                tuple[LocationComponent, ...],
                str | None,
            ],
            None,
        ]
        | None = None,
        save_caption: Callable[
            [Photo, str | None],
            None,
        ]
        | None = None,
        save_locations: Callable[
            [
                list[
                    tuple[
                        Photo,
                        tuple[LocationComponent, ...],
                        str | None,
                    ]
                ]
            ],
            None,
        ]
        | None = None,
        edit_source_photo: Callable[
            [Photo],
            None,
        ]
        | None = None,
        parent=None,
        hover_preview: HoverPhotoPreview | None = None,
    ) -> None:
        super().__init__(parent)

        self._translator = translator or Translator("en")
        self._save_location = save_location
        self._save_caption = save_caption
        self._save_locations = save_locations
        self._edit_source_photo = edit_source_photo
        self._hover_preview = hover_preview or HoverPhotoPreview(
            PreviewImageCache(self), self
        )

        self._caption_builder = LocationCaptionBuilder()
        self._photos: list[Photo] = []

        self._photo_items: dict[str, QTreeWidgetItem] = {}
        self._caption_editors: dict[str, QLineEdit] = {}
        self._thumbnail_labels: dict[QLabel, Photo] = {}

        # Pixmaps shared by the tree and batch dialog lazy loader.
        self._thumbnail_cache: dict[str, QPixmap] = {}

        self._editor_rows: dict[
            str,
            tuple[QTreeWidgetItem, QWidget, FlowLayout],
        ] = {}
        self._truth_labels: dict[
            str,
            tuple[QLabel, QLabel],
        ] = {}
        self._pencil_buttons: dict[
            str,
            QPushButton,
        ] = {}

        self._filter_text = ""

        # Photos belonging to a month are kept as plain data until
        # that month is expanded. Closed months therefore cost only
        # one lightweight QTreeWidgetItem.
        self._month_photos: dict[
            tuple[int, int],
            tuple[Photo, ...],
        ] = {}
        self._materialized_months: set[
            tuple[int, int]
        ] = set()
        self._initial_expansion_pending = True

        self._thumbnail_queue: list[
            tuple[QLabel, Photo]
        ] = []
        self._thumbnail_loading = False
        self._thumbnail_generation = 0

        self._preview_photo: Photo | None = None
        self._preview_position = QPoint()

        self._create_ui()

    # --------------------------------------------------------
    # Public API
    # --------------------------------------------------------

    def set_photos(
        self,
        photos: Sequence[Photo],
    ) -> None:
        self._cancel_photo_preview()
        self._hover_preview.invalidate_changed_sources()
        self._photos = sorted(
            photos,
            key=lambda photo: (
                photo.capture_datetime is None,
                photo.capture_datetime,
                photo.filename.casefold(),
            ),
        )
        self._initial_expansion_pending = True
        self._thumbnail_generation += 1
        self._thumbnail_queue.clear()
        self._thumbnail_loading = False
        self._rebuild_tree()

    def clear(self) -> None:
        self._cancel_photo_preview()
        self._photos = []
        self._photo_items.clear()
        self._caption_editors.clear()
        self._thumbnail_labels.clear()
        self._thumbnail_cache.clear()
        self._editor_rows.clear()
        self._truth_labels.clear()
        self._pencil_buttons.clear()
        self._month_photos.clear()
        self._materialized_months.clear()
        self._thumbnail_generation += 1
        self._thumbnail_queue.clear()
        self._thumbnail_loading = False
        self._tree.clear()
        self._clear_undated_panel()
        self._update_counter(0)

    def hideEvent(self, event) -> None:
        self._cancel_photo_preview()
        super().hideEvent(event)

    # --------------------------------------------------------
    # UI
    # --------------------------------------------------------

    def _create_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(8)

        description = QLabel(
            self._translator.tr(
                "photos.places.description"
            )
        )
        description.setWordWrap(True)
        layout.addWidget(description)

        search_row = QHBoxLayout()

        search_label = QLabel(
            self._translator.tr(
                "photos.places.search"
            )
        )

        self._search_edit = QLineEdit()
        self._search_edit.setClearButtonEnabled(True)
        self._search_edit.setPlaceholderText(
            self._translator.tr(
                "photos.places.search_placeholder"
            )
        )
        # Searching is deliberately explicit. Rebuilding the lazy
        # result hierarchy can be relatively expensive on large
        # albums, so typing must never trigger a rebuild per key.
        self._search_edit.returnPressed.connect(
            self._apply_search
        )
        self._search_edit.textChanged.connect(
            self._search_text_changed
        )

        self._search_button = QPushButton(
            self._translator.tr(
                "photos.places.search_button"
            )
        )
        self._search_button.clicked.connect(
            self._apply_search
        )

        self._counter_label = QLabel()

        search_row.addWidget(search_label)
        search_row.addWidget(self._search_edit, 1)
        search_row.addWidget(self._search_button)
        search_row.addWidget(self._counter_label)

        layout.addLayout(search_row)

        # ----------------------------------------------------
        # Independent panel for photos without a capture date.
        # It is deliberately outside the chronological tree.
        # ----------------------------------------------------

        self._undated_frame = QFrame()
        self._undated_frame.setFrameShape(
            QFrame.Shape.NoFrame
        )
        self._undated_frame.setObjectName(
            "_undated_frame"
        )
        self._undated_frame.setStyleSheet(
            "QFrame#_undated_frame {"
            " border: none;"
            " border-bottom: 1px solid #874247;"
            "}"
        )
        self._undated_frame.setVisible(False)

        self._undated_layout = QVBoxLayout(
            self._undated_frame
        )
        self._undated_layout.setContentsMargins(
            0, 6, 0, 8
        )
        self._undated_layout.setSpacing(4)

        self._undated_title = QLabel()
        title_font = self._undated_title.font()
        title_font.setBold(True)
        self._undated_title.setFont(title_font)

        self._undated_title.setStyleSheet(
            "QLabel {"
            " background-color: #a65359;"
            " color: white;"
            " border: none;"
            " padding: 6px 10px;"
            "}"
        )
        self._undated_title.setMinimumHeight(30)

        self._undated_layout.addWidget(
            self._undated_title
        )

        layout.addWidget(self._undated_frame)

        # Clear visual separation between the exceptional
        # undated-photo panel and the normal chronology.
        layout.addSpacing(14)

        # ----------------------------------------------------
        # Chronological panel: dated photos only.
        # ----------------------------------------------------

        self._dated_frame = QFrame()
        self._dated_frame.setFrameShape(
            QFrame.Shape.NoFrame
        )

        dated_layout = QVBoxLayout(
            self._dated_frame
        )
        dated_layout.setContentsMargins(
            0, 0, 0, 0
        )
        dated_layout.setSpacing(0)

        self._tree = QTreeWidget()
        self._tree.setFrameShape(
            QFrame.Shape.NoFrame
        )
        self._tree.setColumnCount(4)

        self._tree.setHeaderLabels(
            [
                self._translator.tr(
                    "photos.places.column.photo"
                ),
                self._translator.tr(
                    "photos.places.column.date"
                ),
                self._translator.tr(
                    "photos.places.column.location_caption"
                ),
                self._translator.tr(
                    "photos.places.column.edit"
                ),
            ]
        )

        self._tree.setSelectionMode(
            QAbstractItemView.SelectionMode.NoSelection
        )
        self._tree.setUniformRowHeights(False)
        self._tree.setAnimated(False)
        self._tree.setAlternatingRowColors(False)
        self._tree.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._tree.setTextElideMode(
            Qt.TextElideMode.ElideRight
        )

        header = self._tree.header()
        header.setStretchLastSection(False)

        header.setSectionResizeMode(
            0,
            QHeaderView.ResizeMode.Interactive,
        )
        header.setSectionResizeMode(
            1,
            QHeaderView.ResizeMode.Interactive,
        )
        header.setSectionResizeMode(
            2,
            QHeaderView.ResizeMode.Interactive,
        )
        header.setSectionResizeMode(
            3,
            QHeaderView.ResizeMode.Stretch,
        )

        self._tree.setColumnWidth(0, 135)
        self._tree.setColumnWidth(1, 125)
        self._tree.setColumnWidth(2, 320)

        header_font = header.font()
        header_font.setBold(False)
        header.setFont(header_font)
        header.sectionResized.connect(
            lambda *_: QTimer.singleShot(
                0,
                self._update_all_editor_heights,
            )
        )

        header.setStyleSheet(
            "QHeaderView::section {"
            " font-weight: normal;"
            " border-top: 1px solid #aeb6bd;"
            " border-right: 1px solid #aeb6bd;"
            " border-bottom: 1px solid #aeb6bd;"
            " padding-left: 6px;"
            " padding-right: 6px;"
            "}"
        )

        self._tree.setStyleSheet(
            "QTreeWidget {"
            " border-left: none;"
            " border-right: none;"
            "}"
            "QTreeWidget::item {"
            " padding-top: 1px;"
            " padding-bottom: 1px;"
            "}"
        )

        self._tree.itemSelectionChanged.connect(
            self._selection_changed
        )

        self._tree.itemExpanded.connect(
            self._group_expanded
        )
        self._tree.itemClicked.connect(
            self._group_clicked
        )

        dated_layout.addWidget(
            self._tree,
            1,
        )
        layout.addWidget(
            self._dated_frame,
            1,
        )

        # Recalculate wrapping when the available tree width changes.
        self._tree.viewport().installEventFilter(self)

    def _apply_photo_row_backgrounds(self) -> None:
        """
        Alternate photo backgrounds inside each month.

        Every month restarts with alternateBase:
        grey, white, grey, white...
        """
        month_positions: dict[
            tuple[int, int],
            int,
        ] = {}

        for item in QTreeWidgetItemIteratorCompat(
            self._tree
        ):
            photo = item.data(
                0,
                self.PHOTO_ROLE,
            )

            if (
                not isinstance(photo, Photo)
                or photo.capture_datetime is None
            ):
                continue

            month_key = (
                photo.capture_datetime.year,
                photo.capture_datetime.month,
            )

            position = month_positions.get(
                month_key,
                0,
            )
            month_positions[month_key] = (
                position + 1
            )

            brush = QBrush(
                QColor(
                    "#f3f5f6"
                    if position % 2 == 0
                    else "#ffffff"
                )
            )

            for column in range(
                self._tree.columnCount()
            ):
                item.setBackground(
                    column,
                    brush,
                )

                widget = self._tree.itemWidget(
                    item,
                    column,
                )

                if widget is None:
                    continue

                widget.setAutoFillBackground(True)

                palette = widget.palette()
                palette.setColor(
                    widget.backgroundRole(),
                    brush.color(),
                )
                widget.setPalette(palette)

                # Non-interactive containers must not hide the
                # background belonging to the complete photo row.
                # Interactive controls retain their current/native
                # rendering -- in particular QCheckBox.
                for child in widget.findChildren(
                    QWidget
                ):
                    if isinstance(
                        child,
                        (
                            QLineEdit,
                            QCheckBox,
                            QPushButton,
                        ),
                    ):
                        continue

                    child.setAutoFillBackground(False)

    def _style_group_separators(self) -> None:
        # Full-width year/month banners are installed immediately
        # after insertion into the tree.
        pass

    # --------------------------------------------------------
    # Filtering / state
    # --------------------------------------------------------

    def _apply_search(
        self,
    ) -> None:
        text = (
            self._search_edit.text()
            .strip()
            .casefold()
        )

        # Avoid rebuilding when Enter/the button is pressed again
        # without changing the effective query.
        if text == self._filter_text:
            return

        self._filter_text = text
        self._rebuild_tree()

    def _search_text_changed(
        self,
        text: str,
    ) -> None:
        # Typing only edits the pending query. The sole exception is
        # clearing the field: the clear button should restore the
        # complete chronology immediately.
        if text:
            return

        if not self._filter_text:
            return

        self._filter_text = ""
        self._rebuild_tree()

    def _matches_filter(
        self,
        photo: Photo,
    ) -> bool:
        if not self._filter_text:
            return True

        values = (
            photo.filename,
            self._effective_location(photo),
            photo.caption or "",
        )

        return any(
            self._filter_text in value.casefold()
            for value in values
        )

    def _capture_view_state(self):
        expanded: set[tuple] = set()

        iterator = QTreeWidgetItemIteratorCompat(
            self._tree
        )

        for item in iterator:
            group_key = item.data(
                0,
                self.GROUP_ROLE,
            )
            if (
                group_key is not None
                and item.isExpanded()
            ):
                expanded.add(tuple(group_key))

        selected_path = None
        current = self._tree.currentItem()

        if current is not None:
            photo = current.data(
                0,
                self.PHOTO_ROLE,
            )
            if isinstance(photo, Photo):
                selected_path = str(photo.path)

        scroll = (
            self._tree.verticalScrollBar().value()
        )

        return expanded, selected_path, scroll

    def _restore_view_state(
        self,
        expanded: set[tuple],
        selected_path: str | None,
        scroll: int,
        *,
        first_build: bool,
    ) -> None:
        iterator = QTreeWidgetItemIteratorCompat(
            self._tree
        )

        for item in iterator:
            group_key = item.data(
                0,
                self.GROUP_ROLE,
            )

            if group_key is None:
                continue

            item.setExpanded(
                first_build
                or tuple(group_key) in expanded
            )

        if selected_path:
            item = self._photo_items.get(
                selected_path
            )
            if item is not None:
                self._tree.setCurrentItem(item)

        QTimer.singleShot(
            0,
            lambda value=scroll:
                self._tree.verticalScrollBar().setValue(
                    value
                ),
        )

    # --------------------------------------------------------
    # Tree construction
    # --------------------------------------------------------

    def _rebuild_tree(self) -> None:
        (
            expanded,
            selected_path,
            scroll,
        ) = self._capture_view_state()

        self._cancel_photo_preview()

        self._tree.setUpdatesEnabled(False)

        try:
            self._tree.clear()
            self._clear_undated_panel()

            self._photo_items.clear()
            self._caption_editors.clear()
            self._thumbnail_labels.clear()
            self._editor_rows.clear()
            self._truth_labels.clear()
            self._pencil_buttons.clear()

            self._month_photos.clear()
            self._materialized_months.clear()

            undated = [
                photo
                for photo in self._photos
                if photo.capture_datetime is None
            ]

            dated = [
                photo
                for photo in self._photos
                if photo.capture_datetime is not None
                and self._matches_filter(photo)
            ]

            # Missing-date photos remain deliberately independent
            # from the search filter.
            self._populate_undated_panel(
                undated
            )

            grouped: dict[
                int,
                dict[int, list[Photo]],
            ] = defaultdict(
                lambda: defaultdict(list)
            )

            for photo in dated:
                assert photo.capture_datetime is not None
                grouped[
                    photo.capture_datetime.year
                ][
                    photo.capture_datetime.month
                ].append(photo)

            for year in sorted(grouped):
                months = grouped[year]

                year_count = sum(
                    len(photos)
                    for photos in months.values()
                )

                year_text = self._translator.tr(
                    "photos.places.year_group",
                    year=year,
                    count=year_count,
                )

                year_item = self._group_item(
                    year_text,
                    ("year", year),
                )
                self._tree.addTopLevelItem(
                    year_item
                )
                self._install_group_banner(
                    year_item,
                    year_text,
                    kind="year",
                )

                for month in sorted(months):
                    photos = months[month]

                    month_name = (
                        self._translator.month_name(month)
                    )
                    if month_name:
                        month_name = (
                            month_name[0].upper()
                            + month_name[1:]
                        )

                    month_text = self._translator.tr(
                        "photos.places.month_group",
                        month=month_name,
                        count=len(photos),
                    )

                    month_item = self._group_item(
                        month_text,
                        ("month", year, month),
                    )
                    year_item.addChild(
                        month_item
                    )
                    self._install_group_banner(
                        month_item,
                        month_text,
                        kind="month",
                    )

                    key = (year, month)
                    self._month_photos[key] = tuple(
                        photos
                    )

                    # A dummy child gives Qt a disclosure arrow while
                    # avoiding creation of the actual photo rows.
                    placeholder = QTreeWidgetItem(
                        ["", "", "", ""]
                    )
                    placeholder.setData(
                        0,
                        self.GROUP_ROLE,
                        ("placeholder", year, month),
                    )
                    month_item.addChild(
                        placeholder
                    )

            self._update_counter(
                len(dated)
            )

            # Search is intentionally different: matching results
            # must be immediately visible, so matching months are
            # materialized. A normal album opening materializes none.
            if self._filter_text:
                for year_index in range(
                    self._tree.topLevelItemCount()
                ):
                    year_item = self._tree.topLevelItem(
                        year_index
                    )
                    year_item.setExpanded(True)

                    for month_index in range(
                        year_item.childCount()
                    ):
                        month_item = year_item.child(
                            month_index
                        )
                        self._materialize_month(
                            month_item
                        )
                        month_item.setExpanded(True)

            elif self._initial_expansion_pending:
                # First year visible, but its months remain cheap and
                # closed. No photo row is constructed here.
                if self._tree.topLevelItemCount():
                    self._tree.topLevelItem(
                        0
                    ).setExpanded(True)

                self._initial_expansion_pending = False

            else:
                # Restore only group state. Expanding a month below
                # automatically materializes it on demand.
                iterator = QTreeWidgetItemIteratorCompat(
                    self._tree
                )

                for item in iterator:
                    group_key = item.data(
                        0,
                        self.GROUP_ROLE,
                    )
                    if group_key is None:
                        continue

                    key = tuple(group_key)

                    if key in expanded:
                        if (
                            key
                            and key[0] == "month"
                        ):
                            self._materialize_month(
                                item
                            )

                        item.setExpanded(True)

        finally:
            self._tree.setUpdatesEnabled(True)

        if selected_path:
            item = self._photo_items.get(
                selected_path
            )
            if item is not None:
                self._tree.setCurrentItem(item)

        QTimer.singleShot(
            0,
            lambda value=scroll:
            self._tree.verticalScrollBar().setValue(
                value
            ),
        )

    def _group_clicked(
        self,
        item: QTreeWidgetItem,
        column: int,
    ) -> None:
        group_key = item.data(
            0,
            self.GROUP_ROLE,
        )

        if group_key is None:
            return

        key = tuple(group_key)

        if (
            not key
            or key[0] not in ("year", "month")
        ):
            return

        # A click on Qt's native disclosure indicator already toggles
        # the item before itemClicked is emitted. Do not toggle it a
        # second time.
        viewport_pos = self._tree.viewport().mapFromGlobal(
            self._tree.cursor().pos()
        )
        item_rect = self._tree.visualItemRect(
            item
        )

        indicator_width = max(
            24,
            self._tree.indentation(),
        )

        if (
            viewport_pos.x()
            < item_rect.left() + indicator_width
        ):
            return

        item.setExpanded(
            not item.isExpanded()
        )

    def _group_expanded(
        self,
        item: QTreeWidgetItem,
    ) -> None:
        group_key = item.data(
            0,
            self.GROUP_ROLE,
        )

        if group_key is None:
            return

        key = tuple(group_key)

        if (
            len(key) == 3
            and key[0] == "month"
        ):
            self._materialize_month(
                item
            )

    def _materialize_month(
        self,
        month_item: QTreeWidgetItem,
    ) -> None:
        group_key = month_item.data(
            0,
            self.GROUP_ROLE,
        )

        if group_key is None:
            return

        group_key = tuple(group_key)

        if (
            len(group_key) != 3
            or group_key[0] != "month"
        ):
            return

        key = (
            int(group_key[1]),
            int(group_key[2]),
        )

        if key in self._materialized_months:
            return

        photos = self._month_photos.get(
            key,
            ()
        )

        self._materialized_months.add(
            key
        )

        # Remove the lightweight disclosure placeholder.
        while month_item.childCount():
            month_item.takeChild(0)

        self._tree.setUpdatesEnabled(False)

        try:
            for photo in photos:
                self._add_photo_item(
                    month_item,
                    photo,
                )

            self._apply_photo_row_backgrounds()
            self._style_group_separators()

        finally:
            self._tree.setUpdatesEnabled(True)

        # Newly inserted editor widgets do not yet have their
        # definitive geometry here. In particular, FlowLayout may
        # wrap differently once QTreeWidget has assigned the real
        # width of column 3.
        #
        # First let Qt complete insertion/layout, then compute row
        # heights. A second event-loop turn catches geometry changes
        # caused by the first height update.
        QTimer.singleShot(
            0,
            self._stabilize_materialized_rows,
        )


    def _stabilize_materialized_rows(
        self,
    ) -> None:
        # Pass 1: force the freshly inserted widgets/layouts to use
        # the actual tree-column geometry.
        self._tree.doItemsLayout()
        self._tree.viewport().updateGeometry()

        self._update_all_editor_heights()

        QTimer.singleShot(
            0,
            self._finish_materialized_rows_layout,
        )

    def _finish_materialized_rows_layout(
        self,
    ) -> None:
        # Pass 2: row heights may themselves have changed the
        # viewport geometry, so recompute wrapping once more.
        self._tree.doItemsLayout()
        self._tree.viewport().updateGeometry()

        self._update_all_editor_heights()

        self._tree.doItemsLayout()
        self._tree.viewport().update()

    def _group_item(
        self,
        text: str,
        key: tuple,
    ) -> QTreeWidgetItem:
        item = QTreeWidgetItem(
            [text, "", "", ""]
        )

        item.setData(
            0,
            self.GROUP_ROLE,
            key,
        )

        # Native QTreeWidget colspan: the first column spans
        # the complete width of the tree.
        item.setFirstColumnSpanned(True)
        item.setToolTip(0, text)

        font = item.font(0)
        font.setBold(True)
        item.setFont(0, font)

        # The item itself owns the full-width span. No QWidget is
        # embedded here: that previously caused a native crash.
        item.setBackground(
            0,
            self.palette().alternateBase(),
        )

        group_kind = (
            key[0]
            if key
            else "group"
        )

        if group_kind == "year":
            item.setSizeHint(
                0,
                QSize(0, 27),
            )
        elif group_kind == "month":
            item.setSizeHint(
                0,
                QSize(0, 25),
            )
        else:
            item.setSizeHint(
                0,
                QSize(0, 27),
            )

        return item

    def _clear_undated_panel(
        self,
    ) -> None:
        if not hasattr(
            self,
            "_undated_layout",
        ):
            return

        # Preserve the permanent title at index 0.
        while self._undated_layout.count() > 1:
            item = self._undated_layout.takeAt(1)
            widget = item.widget()

            if widget is not None:
                widget.deleteLater()

        self._undated_frame.setVisible(False)

    def _populate_undated_panel(
        self,
        photos: Sequence[Photo],
    ) -> None:
        if not photos:
            self._undated_frame.setVisible(False)
            return

        self._undated_title.setText(
            self._translator.tr(
                "photos.places.undated_group",
                count=len(photos),
            )
        )

        for index, photo in enumerate(photos):
            row = QFrame()
            row.setFrameShape(
                QFrame.Shape.NoFrame
            )

            if index % 2:
                row.setAutoFillBackground(True)
                palette = row.palette()
                palette.setColor(
                    row.backgroundRole(),
                    self.palette()
                    .alternateBase()
                    .color(),
                )
                row.setPalette(palette)

            layout = QHBoxLayout(row)
            layout.setContentsMargins(
                0, 5, 8, 5
            )
            layout.setSpacing(0)

            # Mirror the first two tree columns exactly.
            # This remains stable regardless of whether the tree
            # currently exposes year+month or only one group level.
            photo_cell = QWidget()
            photo_cell.setFixedWidth(
                self._tree.columnWidth(0)
            )
            photo_layout = QHBoxLayout(photo_cell)
            photo_layout.setContentsMargins(
                0, 0, 0, 0
            )
            photo_layout.setSpacing(0)

            thumb = self._create_thumbnail_label(
                photo
            )
            photo_layout.addWidget(
                thumb,
                0,
                Qt.AlignmentFlag.AlignCenter,
            )

            layout.addWidget(photo_cell)

            date_cell = QWidget()
            date_cell.setFixedWidth(
                self._tree.columnWidth(1)
            )
            date_layout = QHBoxLayout(date_cell)
            date_layout.setContentsMargins(
                8, 0, 8, 0
            )
            date_layout.setSpacing(0)

            date = QLabel("—")
            date_layout.addWidget(
                date,
                0,
                Qt.AlignmentFlag.AlignVCenter,
            )

            layout.addWidget(date_cell)

            message = QLabel(
                self._translator.tr(
                    "photos.places.missing_date"
                )
            )
            message.setWordWrap(True)
            message.setContentsMargins(
                8, 0, 12, 0
            )
            layout.addWidget(
                message,
                1,
                Qt.AlignmentFlag.AlignVCenter,
            )

            button = QPushButton(
                self._translator.tr(
                    "photos.places.fix_in_photos"
                )
            )
            button.clicked.connect(
                lambda _checked=False, p=photo:
                    self._request_source_photo(p)
            )
            layout.addWidget(
                button,
                0,
                Qt.AlignmentFlag.AlignVCenter,
            )

            self._undated_layout.addWidget(row)

        self._undated_frame.setVisible(True)

    def _install_group_banner(
        self,
        item: QTreeWidgetItem,
        text: str,
        *,
        kind: str,
    ) -> None:
        """
        Full-width chronological separator with breathing room.

        The outer widget provides vertical spacing.
        The inner frame provides the coloured band.
        """
        item.setFirstColumnSpanned(True)

        item.setText(0, "")
        item.setToolTip(0, text)

        outer = QWidget()
        outer.setAutoFillBackground(False)

        # The banner is purely visual. Let mouse events pass through
        # to the underlying QTreeWidget item so the whole coloured
        # separator behaves like an expand/collapse target.
        outer.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents,
            True,
        )

        outer_layout = QVBoxLayout(outer)
        outer_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )
        outer_layout.setSpacing(0)

        band = QFrame()
        band.setFrameShape(
            QFrame.Shape.NoFrame
        )

        band_layout = QHBoxLayout(band)
        band_layout.setSpacing(0)

        label = QLabel(text)

        font = label.font()
        font.setBold(True)
        label.setFont(font)

        band_layout.addWidget(label)
        band_layout.addStretch(1)

        if kind == "year":
            background = "#465565"
            foreground = "#ffffff"

            top_space = 6
            band_height = 30

            band_layout.setContentsMargins(
                10,
                4,
                10,
                4,
            )

        else:
            background = "#dce3e8"
            foreground = "#27333d"

            top_space = 4
            band_height = 27

            band_layout.setContentsMargins(
                10,
                3,
                10,
                3,
            )

        outer_layout.setContentsMargins(
            0,
            top_space,
            0,
            0,
        )

        band.setStyleSheet(
            "QFrame {"
            f" background-color: {background};"
            " border: none;"
            "}"
            "QLabel {"
            " background: transparent;"
            f" color: {foreground};"
            " border: none;"
            "}"
        )

        band.setFixedHeight(
            band_height
        )

        outer_layout.addWidget(band)

        total_height = (
            top_space + band_height
        )

        outer.setFixedHeight(
            total_height
        )

        item.setSizeHint(
            0,
            QSize(0, total_height),
        )

        self._tree.setItemWidget(
            item,
            0,
            outer,
        )

    def _add_photo_item(
        self,
        parent: QTreeWidgetItem,
        photo: Photo,
    ) -> None:
        assert photo.capture_datetime is not None

        item = QTreeWidgetItem(
            ["", "", "", ""]
        )

        item.setData(
            0,
            self.PHOTO_ROLE,
            photo,
        )

        item.setToolTip(
            0,
            photo.filename,
        )
        item.setToolTip(
            1,
            format_datetime(
                photo.capture_datetime,
                include_seconds=True,
            ),
        )

        parent.addChild(item)

        self._install_thumbnail(
            item,
            photo,
        )
        self._install_date_widget(
            item,
            photo,
        )
        self._install_truth_widget(
            item,
            photo,
        )
        self._install_editor_widget(
            item,
            photo,
        )

        self._photo_items[
            str(photo.path)
        ] = item

    # --------------------------------------------------------
    # Thumbnail / hover preview
    # --------------------------------------------------------

    def _create_thumbnail_label(
        self,
        photo: Photo,
        *,
        hover_preview: bool = True,
    ) -> QLabel:
        label = QLabel()
        label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )
        label.setFixedSize(
            self.THUMBNAIL_WIDTH,
            self.THUMBNAIL_HEIGHT,
        )

        # Reserve the final geometry immediately. Image decoding is
        # deliberately deferred so expanding a month never waits for
        # every JPEG to be read before the rows become visible.
        label.setText("…")

        label.setToolTip(photo.filename)
        if hover_preview:
            label.setMouseTracking(True)
            label.installEventFilter(self)

        self._thumbnail_labels[label] = photo
        self._queue_thumbnail(
            label,
            photo,
        )
        return label

    def _install_thumbnail(
        self,
        item: QTreeWidgetItem,
        photo: Photo,
    ) -> None:
        label = self._create_thumbnail_label(
            photo
        )

        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.addWidget(
            label,
            0,
            Qt.AlignmentFlag.AlignCenter,
        )

        self._tree.setItemWidget(
            item,
            0,
            container,
        )

        item.setSizeHint(
            0,
            QSize(
                self.THUMBNAIL_WIDTH + 8,
                self.NATURAL_ROW_HEIGHT,
            ),
        )

    def _queue_thumbnail(
        self,
        label: QLabel,
        photo: Photo,
    ) -> None:
        cached = self._thumbnail_cache.get(str(photo.path))
        if cached is not None:
            label.setPixmap(cached)
            return

        self._thumbnail_queue.append(
            (label, photo)
        )

        if self._thumbnail_loading:
            return

        self._thumbnail_loading = True
        generation = self._thumbnail_generation

        QTimer.singleShot(
            0,
            lambda: self._load_next_thumbnail(
                generation
            ),
        )

    def _load_next_thumbnail(
        self,
        generation: int,
    ) -> None:
        if generation != self._thumbnail_generation:
            return

        if not self._thumbnail_queue:
            self._thumbnail_loading = False
            return

        label, photo = self._thumbnail_queue.pop(0)

        # The row may have disappeared after a filter/project change.
        if label in self._thumbnail_labels:
            pixmap = self._thumbnail_cache.get(str(photo.path))
            if pixmap is None:
                pixmap = self._thumbnail_pixmap(photo.path)

            if pixmap is not None:
                # Keep the already-decoded pixmap available for other
                # lightweight views such as the batch-edit dialog.
                self._thumbnail_cache[
                    str(photo.path)
                ] = pixmap

                label.setText("")
                label.setPixmap(pixmap)
            else:
                label.setPixmap(QPixmap())
                label.setText("—")

        # Exactly one decode per event-loop turn. This keeps painting,
        # scrolling and input responsive while thumbnails arrive.
        QTimer.singleShot(
            0,
            lambda: self._load_next_thumbnail(
                generation
            ),
        )

    def _thumbnail_pixmap(
        self,
        path: Path,
    ) -> QPixmap | None:
        reader = QImageReader(str(path))
        reader.setAutoTransform(True)

        size = reader.size()

        if size.isValid():
            size.scale(
                self.THUMBNAIL_WIDTH,
                self.THUMBNAIL_HEIGHT,
                Qt.AspectRatioMode.KeepAspectRatio,
            )
            reader.setScaledSize(size)

        image = reader.read()

        if image.isNull():
            return None

        return QPixmap.fromImage(image).scaled(
            self.THUMBNAIL_WIDTH,
            self.THUMBNAIL_HEIGHT,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

    def eventFilter(
        self,
        watched,
        event,
    ) -> bool:
        if (
            watched is self._tree.viewport()
            and event.type() == QEvent.Type.Resize
        ):
            QTimer.singleShot(
                0,
                self._update_all_editor_heights,
            )

        if watched in self._thumbnail_labels:
            photo = self._thumbnail_labels[
                watched
            ]

            if event.type() == QEvent.Type.Enter:
                self._cancel_photo_preview()
                self._preview_photo = photo
                self._preview_position = (
                    watched.mapToGlobal(
                        QPoint(
                            watched.width(),
                            watched.height() // 2,
                        )
                    )
                )
                self._hover_preview.schedule(
                    photo.path,
                    self._preview_position,
                )

            elif event.type() in (
                QEvent.Type.Leave,
                QEvent.Type.MouseButtonPress,
            ):
                self._cancel_photo_preview()

        return super().eventFilter(
            watched,
            event,
        )

    def _show_pending_photo_preview(
        self,
    ) -> None:
        photo = self._preview_photo

        if photo is None:
            return
        self._hover_preview.schedule(
            photo.path,
            self._preview_position,
        )

    def _cancel_photo_preview(
        self,
    ) -> None:
        self._hover_preview.cancel()
        self._preview_photo = None

    def _install_date_widget(
        self,
        item: QTreeWidgetItem,
        photo: Photo,
    ) -> None:
        assert photo.capture_datetime is not None

        label = QLabel(
            photo.capture_datetime.strftime(
                "%d • %H:%M"
            )
        )
        label.setContentsMargins(
            10,
            0,
            10,
            0,
        )
        label.setAlignment(
            Qt.AlignmentFlag.AlignVCenter
            | Qt.AlignmentFlag.AlignLeft
        )

        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(
            8,
            0,
            8,
            0,
        )
        layout.addWidget(label)

        self._tree.setItemWidget(
            item,
            1,
            container,
        )

    # --------------------------------------------------------
    # Truth column
    # --------------------------------------------------------

    def _install_truth_widget(
        self,
        item: QTreeWidgetItem,
        photo: Photo,
    ) -> None:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(8, 3, 8, 3)
        layout.setSpacing(1)

        location = QLabel(
            self._effective_location(photo)
        )
        location.setWordWrap(True)
        location.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Preferred,
        )
        location.setTextInteractionFlags(
            Qt.TextInteractionFlag.NoTextInteraction
        )

        caption = QLabel(
            self._display_caption(photo)
        )
        caption.setWordWrap(True)
        caption.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Preferred,
        )
        caption.setTextInteractionFlags(
            Qt.TextInteractionFlag.NoTextInteraction
        )

        layout.addWidget(location)
        layout.addWidget(caption)

        self._truth_labels[
            str(photo.path)
        ] = (
            location,
            caption,
        )

        self._tree.setItemWidget(
            item,
            2,
            container,
        )

    def _display_caption(
        self,
        photo: Photo,
    ) -> str:
        if photo.caption:
            text = photo.caption.strip()
            if text:
                return text

        return "—"

    # --------------------------------------------------------
    # Location
    # --------------------------------------------------------

    def _caption_result(
        self,
        photo: Photo,
    ):
        return self._caption_builder.build(
            photo.raw_location_data
        )

    def _effective_components(
        self,
        photo: Photo,
    ) -> tuple[LocationComponent, ...]:
        if photo.location_selection_edited:
            return tuple(
                photo.selected_location_components
            )

        result = self._caption_result(photo)

        return tuple(
            LocationComponent(
                key=candidate.key,
                value=candidate.value,
            )
            for candidate in result.selected
            if self._component_is_visible(
                candidate.key
            )
        )

    def _components_text(
        self,
        components: Sequence[
            LocationComponent
        ],
    ) -> str | None:
        text = ", ".join(
            component.value
            for component in components
            if component.value.strip()
        ).strip()

        return text or None

    def _has_custom_location(
        self,
        photo: Photo,
    ) -> bool:
        if not photo.location_selection_edited:
            return False

        component_text = self._components_text(
            photo.selected_location_components
        )

        actual = (
            photo.location_text.strip()
            if photo.location_text
            else None
        )

        return actual != component_text

    def _effective_location(
        self,
        photo: Photo,
    ) -> str:
        if photo.location_selection_edited:
            if photo.location_text:
                text = photo.location_text.strip()
                if text:
                    return text
            return "—"

        result = self._caption_result(photo)
        return result.caption or "—"

    def _component_is_visible(
        self,
        key: str,
    ) -> bool:
        normalized = key.casefold()

        if normalized in self.HIDDEN_COMPONENT_KEYS:
            return False

        if normalized.startswith("iso3166"):
            return False

        return True

    # --------------------------------------------------------
    # Edit column
    # --------------------------------------------------------

    def _install_editor_widget(
        self,
        item: QTreeWidgetItem,
        photo: Photo,
    ) -> None:
        """
        Fluid editor.

        Geographic components wrap naturally according to the
        available width. The caption always starts below them.
        No local scrollbar is used.
        """
        container = QWidget()
        container.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )

        outer = QVBoxLayout(container)
        outer.setContentsMargins(6, 3, 6, 3)
        outer.setSpacing(2)

        location_widget = QWidget()
        location_widget.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )

        location_layout = FlowLayout(
            location_widget,
            margin=0,
            h_spacing=10,
            v_spacing=2,
        )

        result = self._caption_result(photo)

        selected = {
            (
                component.key,
                component.value,
            )
            for component
            in self._effective_components(photo)
        }

        visible_count = 0

        for candidate in result.candidates:
            if not self._component_is_visible(
                candidate.key
            ):
                continue

            checkbox = QCheckBox(
                candidate.value
            )
            checkbox.setAutoFillBackground(False)
            checkbox.setChecked(
                (
                    candidate.key,
                    candidate.value,
                )
                in selected
            )
            checkbox.setToolTip(
                candidate.key
            )
            checkbox.setProperty(
                "location_key",
                candidate.key,
            )
            checkbox.setProperty(
                "location_value",
                candidate.value,
            )

            checkbox.setProperty(
                "group_edit_pending",
                False,
            )

            checkbox.pressed.connect(
                lambda cb=checkbox,
                p=photo:
                    self._location_checkbox_pressed(
                        p,
                        cb,
                    )
            )

            checkbox.toggled.connect(
                lambda checked,
                p=photo,
                row_widget=location_widget,
                cb=checkbox:
                    self._location_checkbox_toggled(
                        p,
                        row_widget,
                        cb,
                        checked,
                    )
            )

            location_layout.addWidget(
                checkbox
            )
            visible_count += 1

        if visible_count == 0:
            location_layout.addWidget(
                QLabel("—")
            )

        pencil = QPushButton("✎")
        pencil.setFlat(True)
        pencil.setFixedSize(18, 18)
        pencil.setCursor(
            Qt.CursorShape.PointingHandCursor
        )
        pencil.setToolTip(
            self._translator.tr(
                "photos.places.free_location"
            )
        )

        self._style_pencil(
            pencil,
            photo,
        )
        self._pencil_buttons[
            str(photo.path)
        ] = pencil

        pencil.clicked.connect(
            lambda _checked=False, p=photo:
                self._edit_free_location(p)
        )

        location_layout.addWidget(
            pencil
        )

        outer.addWidget(
            location_widget
        )

        # Caption is deliberately a separate row: equivalent to
        # a hard line break after the complete component flow.
        caption_container = QWidget()
        caption_layout = QHBoxLayout(
            caption_container
        )
        caption_layout.setContentsMargins(
            0, 0, 0, 0
        )
        caption_layout.setSpacing(5)

        caption_label = QLabel(
            self._translator.tr(
                "photos.places.caption"
            )
        )
        caption_layout.addWidget(
            caption_label,
            0,
        )

        editor = QLineEdit(
            photo.caption or ""
        )
        editor.setClearButtonEnabled(True)
        editor.setFixedHeight(22)

        path_key = str(photo.path)
        self._caption_editors[
            path_key
        ] = editor

        editor.editingFinished.connect(
            lambda p=photo, e=editor:
                self._caption_finished(
                    p,
                    e,
                )
        )

        editor.returnPressed.connect(
            lambda p=photo:
                self._caption_return_pressed(
                    p
                )
        )

        caption_layout.addWidget(
            editor,
            1,
        )

        outer.addWidget(
            caption_container
        )

        self._tree.setItemWidget(
            item,
            3,
            container,
        )

        self._editor_rows[path_key] = (
            item,
            container,
            location_layout,
        )

        QTimer.singleShot(
            0,
            self._update_all_editor_heights,
        )

    def _update_all_editor_heights(
        self,
    ) -> None:
        if not self._editor_rows:
            return

        editor_available = max(
            80,
            self._tree.columnWidth(3) - 12,
        )

        # Column 2 has 8 px left + 8 px right margins.
        truth_available = max(
            40,
            self._tree.columnWidth(2) - 16,
        )

        for path_key, (
            item,
            container,
            flow,
        ) in tuple(
            self._editor_rows.items()
        ):
            flow_height = flow.heightForWidth(
                editor_available
            )

            editor_height = (
                flow_height + 30
            )

            # Measure the two wrapped QLabel instances at the
            # width they really have in column 2.
            truth_height = 0

            labels = self._truth_labels.get(
                path_key
            )

            if labels is not None:
                location, caption = labels

                location_height = (
                    location.heightForWidth(
                        truth_available
                    )
                )
                caption_height = (
                    caption.heightForWidth(
                        truth_available
                    )
                )

                if location_height < 0:
                    location_height = (
                        location.sizeHint().height()
                    )

                if caption_height < 0:
                    caption_height = (
                        caption.sizeHint().height()
                    )

                # QVBoxLayout:
                # top/bottom margins = 3 + 3
                # spacing between labels = 1
                truth_height = (
                    location_height
                    + caption_height
                    + 7
                )

            desired = max(
                self.NATURAL_ROW_HEIGHT,
                editor_height,
                truth_height,
            )

            container.setMinimumHeight(
                desired
            )
            container.setMaximumHeight(
                desired
            )

            item.setSizeHint(
                0,
                QSize(
                    self.THUMBNAIL_WIDTH + 8,
                    desired,
                ),
            )

        self._tree.viewport().update()

    def _update_item_height(
        self,
        item: QTreeWidgetItem,
        widget: QWidget,
    ) -> None:
        # Compatibility entry point for older callers.
        self._update_all_editor_heights()

    def _style_pencil(
        self,
        pencil: QPushButton,
        photo: Photo,
    ) -> None:
        if self._has_custom_location(photo):
            pencil.setStyleSheet(
                "QPushButton {"
                " font-size: 14px;"
                " font-weight: bold;"
                " color: palette(highlight);"
                " border: none;"
                " padding: 0px;"
                "}"
            )
        else:
            pencil.setStyleSheet(
                "QPushButton {"
                " font-size: 14px;"
                " color: palette(text);"
                " border: none;"
                " padding: 0px;"
                "}"
            )

    def _location_checkbox_pressed(
        self,
        photo: Photo,
        checkbox: QCheckBox,
    ) -> None:
        if not (
            Qt.KeyboardModifier.ControlModifier
            & QApplication.keyboardModifiers()
        ):
            checkbox.setProperty(
                "group_edit_pending",
                False,
            )
            return

        checkbox.setProperty(
            "group_edit_pending",
            True,
        )

        # Opening the dialog after the current mouse event prevents
        # the Ctrl+click itself from becoming a normal checkbox edit.
        QTimer.singleShot(
            0,
            lambda p=photo, cb=checkbox:
                self._open_group_location_dialog(
                    p,
                    cb,
                ),
        )

    def _location_checkbox_toggled(
        self,
        photo: Photo,
        location_widget: QWidget,
        checkbox: QCheckBox,
        checked: bool,
    ) -> None:
        if checkbox.property(
            "group_edit_pending"
        ):
            checkbox.blockSignals(True)
            checkbox.setChecked(
                not checked
            )
            checkbox.blockSignals(False)
            return

        self._composition_changed(
            photo,
            location_widget,
        )

    def _location_candidates_by_key(
        self,
        photo: Photo,
    ) -> dict[str, str]:
        result = self._caption_result(photo)

        values: dict[str, str] = {}

        for candidate in result.candidates:
            key = candidate.key.casefold()
            value = candidate.value.strip()

            if (
                not value
                or not self._component_is_visible(key)
            ):
                continue

            values.setdefault(
                key,
                value,
            )

        return values

    def _location_priority(
        self,
        key: str,
    ) -> int | None:
        return self.GROUP_LOCATION_PRIORITIES.get(
            key.casefold()
        )

    @staticmethod
    def _same_location_value(
        left: str,
        right: str,
    ) -> bool:
        return (
            left.strip().casefold()
            == right.strip().casefold()
        )

    def _group_target_options(
        self,
        photo: Photo,
        source_key: str,
    ) -> list[tuple[str, str]]:
        source_priority = self._location_priority(
            source_key
        )

        if source_priority is None:
            return []

        candidates = self._location_candidates_by_key(
            photo
        )

        options: list[tuple[int, str, str]] = []

        for key, value in candidates.items():
            priority = self._location_priority(
                key
            )

            if (
                priority is None
                or priority <= source_priority
            ):
                continue

            options.append(
                (priority, key, value)
            )

        options.sort(
            key=lambda value: (
                value[0],
                value[1],
            )
        )

        return [
            (key, value)
            for _priority, key, value in options
        ]

    def _location_component_is_selected(
        self,
        photo: Photo,
        key: str,
    ) -> bool:
        key = key.casefold()

        return any(
            component.key.casefold() == key
            for component in self._effective_components(
                photo
            )
        )

    def _group_candidate_is_compatible(
        self,
        reference: Photo,
        candidate: Photo,
        target_key: str,
    ) -> bool:
        reference_values = (
            self._location_candidates_by_key(
                reference
            )
        )
        candidate_values = (
            self._location_candidates_by_key(
                candidate
            )
        )

        target_priority = self._location_priority(
            target_key
        )

        if target_priority is None:
            return False

        reference_target = reference_values.get(
            target_key
        )
        candidate_target = candidate_values.get(
            target_key
        )

        # The replacement level itself is our geographic anchor.
        if (
            reference_target is None
            or candidate_target is None
            or not self._same_location_value(
                reference_target,
                candidate_target,
            )
        ):
            return False

        # Safety rule:
        # every broader component available on BOTH photos must agree.
        # Missing information on either side is neutral.
        for key, reference_value in (
            reference_values.items()
        ):
            priority = self._location_priority(
                key
            )

            if (
                priority is None
                or priority <= target_priority
            ):
                continue

            candidate_value = candidate_values.get(
                key
            )

            if candidate_value is None:
                continue

            if not self._same_location_value(
                reference_value,
                candidate_value,
            ):
                return False

        return True

    def _group_location_candidates(
        self,
        reference: Photo,
        source_key: str,
        target_key: str | None,
    ) -> list[Photo]:
        result: list[Photo] = []

        reference_values = (
            self._location_candidates_by_key(
                reference
            )
        )

        reference_source_value = (
            reference_values.get(source_key)
        )

        if reference_source_value is None:
            return result

        reference_selected = (
            self._location_component_is_selected(
                reference,
                source_key,
            )
        )

        source_priority = self._location_priority(
            source_key
        )

        for photo in self._photos:
            values = (
                self._location_candidates_by_key(
                    photo
                )
            )

            candidate_source_value = (
                values.get(source_key)
            )

            if candidate_source_value is None:
                continue

            # The batch operation is about THIS component value.
            # Ctrl+click on "Connexion (shop)" must never include
            # another shop/place value.
            if not self._same_location_value(
                reference_source_value,
                candidate_source_value,
            ):
                continue

            # Fundamental batch-editing rule:
            # only photos where the clicked component has exactly
            # the same selected/unselected status are eligible.
            if (
                self._location_component_is_selected(
                    photo,
                    source_key,
                )
                != reference_selected
            ):
                continue

            if target_key is not None:
                # Normal replacement:
                # the target value is the geographic anchor.
                if not self._group_candidate_is_compatible(
                    reference,
                    photo,
                    target_key,
                ):
                    continue

            else:
                # "Replace by nothing":
                # the source itself becomes the anchor.
                if not self._same_location_value(
                    reference_source_value,
                    candidate_source_value,
                ):
                    continue

                # Broader geographic components shared by both
                # photos must not contradict one another.
                if source_priority is not None:
                    compatible = True

                    for (
                        key,
                        reference_value,
                    ) in reference_values.items():
                        priority = (
                            self._location_priority(
                                key
                            )
                        )

                        if (
                            priority is None
                            or priority
                            <= source_priority
                        ):
                            continue

                        candidate_value = (
                            values.get(key)
                        )

                        # Missing on one side is neutral.
                        if candidate_value is None:
                            continue

                        if not self._same_location_value(
                            reference_value,
                            candidate_value,
                        ):
                            compatible = False
                            break

                    if not compatible:
                        continue

            result.append(photo)

        return result

    def _group_future_location(
        self,
        photo: Photo,
        source_key: str,
        action: str,
        target_key: str | None,
    ) -> str:
        """
        Preview a grouped activation, deactivation or replacement.

        This is deliberately side-effect free: the Photo is not modified
        until the dialog is accepted.
        """
        values = self._location_candidates_by_key(
            photo
        )

        source_value = values.get(source_key)

        target_value = (
            values.get(target_key)
            if target_key is not None
            else None
        )

        current = list(
            self._effective_components(photo)
        )

        if action in ("deactivate", "replace"):
            current = [
                component
                for component in current
                if component.key.casefold()
                != source_key
            ]

        if (
            action == "activate"
            and source_value is not None
            and not any(
                component.key.casefold()
                == source_key
                for component in current
            )
        ):
            current.append(
                LocationComponent(
                    key=source_key,
                    value=source_value,
                )
            )

        if (
            action == "replace"
            and target_key is not None
            and target_value is not None
            and not any(
                component.key.casefold()
                == target_key
                for component in current
            )
        ):
            current.append(
                LocationComponent(
                    key=target_key,
                    value=target_value,
                )
            )

        current.sort(
            key=lambda component:
            self._location_priority(
                component.key
            )
            or 100
        )

        return (
            self._components_text(current)
            or "—"
        )

    def _group_context_text(
        self,
        reference: Photo,
        target_key: str,
    ) -> str:
        """
        Human-readable geographic safety context.

        Only components broader than the replacement component are shown.
        """
        values = self._location_candidates_by_key(
            reference
        )

        target_priority = self._location_priority(
            target_key
        )

        if target_priority is None:
            return "—"

        labels = {
            "neighbourhood": "Quartier",
            "quarter": "Quartier",
            "suburb": "Quartier",
            "borough": "Arrondissement",
            "city_district": "District",
            "hamlet": "Hameau",
            "isolated_dwelling": "Lieu-dit",
            "city": "Ville",
            "town": "Ville",
            "village": "Village",
            "municipality": "Commune",
            "county": "Département",
            "state_district": "District",
            "state": "Région",
            "region": "Région",
            "country": "Pays",
        }

        context: list[
            tuple[int, str, str]
        ] = []

        for key, value in values.items():
            priority = self._location_priority(
                key
            )

            if (
                priority is None
                or priority <= target_priority
            ):
                continue

            label = labels.get(
                key,
                key.replace("_", " ").capitalize(),
            )

            context.append(
                (
                    priority,
                    label,
                    value,
                )
            )

        context.sort(
            key=lambda item: (
                item[0],
                item[1],
            )
        )

        if not context:
            return "—"

        return " • ".join(
            f"{label} : {value}"
            for _priority, label, value
            in context
        )

    def _open_group_location_dialog(
        self,
        reference: Photo,
        checkbox: QCheckBox,
    ) -> None:
        # Keep the Ctrl+click from becoming a normal checkbox edit.
        checkbox.setProperty(
            "group_edit_pending",
            True,
        )

        source_key = checkbox.property(
            "location_key"
        )
        source_value = checkbox.property(
            "location_value"
        )

        if (
            not isinstance(source_key, str)
            or not isinstance(source_value, str)
        ):
            checkbox.setProperty(
                "group_edit_pending",
                False,
            )
            return

        source_key = source_key.casefold()

        options = self._group_target_options(
            reference,
            source_key,
        )

        dialog = QDialog(self)
        dialog.setWindowTitle(
            self._translator.tr(
                "photos.places.group.title"
            )
        )
        dialog.resize(1050, 620)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(
            16, 16, 16, 16
        )
        layout.setSpacing(10)

        # ----------------------------------------------------
        # Replacement summary
        # ----------------------------------------------------

        replace_title = QLabel(
            self._translator.tr(
                "photos.places.group.replace"
            )
        )
        replace_font = replace_title.font()
        replace_font.setBold(True)
        replace_title.setFont(replace_font)

        source_label = QLabel(
            f"{source_value} ({source_key})"
        )
        source_label.setWordWrap(True)

        layout.addWidget(replace_title)
        layout.addWidget(source_label)

        action_title = QLabel(
            self._translator.tr(
                "photos.places.group.action"
            )
        )
        action_font = action_title.font()
        action_font.setBold(True)
        action_title.setFont(action_font)

        layout.addWidget(action_title)

        activate_radio = QRadioButton(
            self._translator.tr(
                "photos.places.group.activate"
            )
        )

        deactivate_radio = QRadioButton(
            self._translator.tr(
                "photos.places.group.deactivate"
            )
        )

        replace_radio = QRadioButton(
            self._translator.tr(
                "photos.places.group.replace_by"
            )
        )

        layout.addWidget(activate_radio)
        layout.addWidget(deactivate_radio)
        layout.addWidget(replace_radio)

        target_combo = QComboBox()

        for key, value in options:
            target_combo.addItem(
                f"{value} ({key})",
                key,
            )

        target_combo.setEnabled(False)
        layout.addWidget(target_combo)

        source_is_selected = (
            self._location_component_is_selected(
                reference,
                source_key,
            )
        )

        # Only offer actions that can actually change the source.
        #
        # All batch candidates have the same initial source state as
        # the reference photo, so:
        #   selected   -> activation would be a no-op
        #   unselected -> deactivation would be a no-op
        if source_is_selected:
            activate_radio.setVisible(False)
            deactivate_radio.setChecked(True)
        else:
            deactivate_radio.setVisible(False)
            activate_radio.setChecked(True)

        # Replacement is unavailable when no broader component exists,
        # but activation/deactivation remain perfectly valid.
        replace_radio.setEnabled(
            bool(options)
        )

        context_title = QLabel(
            self._translator.tr(
                "photos.places.group.context"
            )
        )
        context_font = context_title.font()
        context_font.setBold(True)
        context_title.setFont(context_font)

        context_label = QLabel()
        context_label.setWordWrap(True)

        layout.addWidget(context_title)
        layout.addWidget(context_label)

        info_label = QLabel()
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        # ----------------------------------------------------
        # Preview table
        # ----------------------------------------------------

        table = QTableWidget()
        table.setColumnCount(5)

        table.setHorizontalHeaderLabels(
            [
                "",
                self._translator.tr(
                    "photos.places.group.photo"
                ),
                self._translator.tr(
                    "photos.places.group.date"
                ),
                self._translator.tr(
                    "photos.places.group.current_location"
                ),
                self._translator.tr(
                    "photos.places.group.future_location"
                ),
            ]
        )

        table.verticalHeader().setVisible(False)

        table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        table.setSelectionMode(
            QAbstractItemView.SelectionMode.NoSelection
        )
        table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )

        header = table.horizontalHeader()
        header.setStretchLastSection(True)

        header.setSectionResizeMode(
            0,
            QHeaderView.ResizeMode.Fixed,
        )
        table.setColumnWidth(0, 34)

        header.setSectionResizeMode(
            1,
            QHeaderView.ResizeMode.Interactive,
        )
        table.setColumnWidth(
            1,
            max(
                self.THUMBNAIL_WIDTH + 28,
                155,
            ),
        )

        header.setSectionResizeMode(
            2,
            QHeaderView.ResizeMode.ResizeToContents,
        )
        header.setSectionResizeMode(
            3,
            QHeaderView.ResizeMode.Stretch,
        )
        header.setSectionResizeMode(
            4,
            QHeaderView.ResizeMode.Stretch,
        )

        # Header checkbox. Using a real QCheckBox here gives us
        # checked / unchecked / partially checked states.
        select_all = QCheckBox()
        select_all.setTristate(True)
        select_all.setToolTip(
            self._translator.tr(
                "photos.places.group.select_all"
            )
        )

        header_container = QWidget()
        header_layout = QHBoxLayout(
            header_container
        )
        header_layout.setContentsMargins(
            0, 0, 0, 0
        )
        header_layout.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )
        header_layout.addWidget(
            select_all
        )

        layout.addWidget(
            table,
            1,
        )

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel
            | QDialogButtonBox.StandardButton.Ok
        )

        apply_button = buttons.button(
            QDialogButtonBox.StandardButton.Ok
        )

        buttons.rejected.connect(
            dialog.reject
        )
        buttons.accepted.connect(
            dialog.accept
        )

        layout.addWidget(buttons)

        state: dict[str, object] = {
            "photos": [],
            "updating_checks": False,
        }

        # Qt does not provide a native checkable QHeaderView section.
        # Overlay the checkbox on the first header section.
        select_all.setParent(
            table.horizontalHeader()
        )
        select_all.show()

        def position_header_checkbox() -> None:
            section_x = header.sectionViewportPosition(
                0
            )
            section_width = header.sectionSize(
                0
            )

            size = select_all.sizeHint()

            select_all.move(
                section_x
                + (section_width - size.width()) // 2,
                (
                    header.height()
                    - size.height()
                )
                // 2,
            )

        header.sectionResized.connect(
            lambda *_:
            position_header_checkbox()
        )
        header.geometriesChanged.connect(
            position_header_checkbox
        )

        def checked_count() -> int:
            count = 0

            for row in range(
                table.rowCount()
            ):
                item = table.item(
                    row,
                    0,
                )

                if (
                    item is not None
                    and item.checkState()
                    == Qt.CheckState.Checked
                ):
                    count += 1

            return count

        def update_header_check() -> None:
            if state["updating_checks"]:
                return

            count = checked_count()
            total = table.rowCount()

            state["updating_checks"] = True

            select_all.blockSignals(True)

            if total == 0 or count == 0:
                select_all.setCheckState(
                    Qt.CheckState.Unchecked
                )
            elif count == total:
                select_all.setCheckState(
                    Qt.CheckState.Checked
                )
            else:
                select_all.setCheckState(
                    Qt.CheckState.PartiallyChecked
                )

            select_all.blockSignals(False)

            state["updating_checks"] = False

        def update_apply_text() -> None:
            count = checked_count()

            apply_button.setText(
                self._translator.tr(
                    "photos.places.group.apply",
                    count=count,
                )
            )
            apply_button.setEnabled(
                count > 0
            )

            update_header_check()

        def set_all_checked(
            state_value: int,
        ) -> None:
            if state["updating_checks"]:
                return

            # Clicking the partial state means "select all".
            checked = (
                state_value
                != Qt.CheckState.Unchecked.value
            )

            state["updating_checks"] = True
            table.blockSignals(True)

            try:
                for row in range(
                    table.rowCount()
                ):
                    item = table.item(
                        row,
                        0,
                    )

                    if item is None:
                        continue

                    item.setCheckState(
                        Qt.CheckState.Checked
                        if checked
                        else Qt.CheckState.Unchecked
                    )
            finally:
                table.blockSignals(False)
                state["updating_checks"] = False

            update_apply_text()

        select_all.stateChanged.connect(
            set_all_checked
        )

        def current_action() -> str:
            if activate_radio.isChecked():
                return "activate"

            if deactivate_radio.isChecked():
                return "deactivate"

            return "replace"

        batch_thumbnails: set[QLabel] = set()

        def clear_batch_thumbnails() -> None:
            self._cancel_photo_preview()
            for label in batch_thumbnails:
                self._thumbnail_labels.pop(label, None)
            self._thumbnail_queue[:] = [
                (label, photo)
                for label, photo in self._thumbnail_queue
                if label not in batch_thumbnails
            ]
            batch_thumbnails.clear()

        def rebuild_candidates() -> None:
            action = current_action()

            target_key = (
                target_combo.currentData()
                if action == "replace"
                else None
            )

            if (
                target_key is not None
                and not isinstance(
                    target_key,
                    str,
                )
            ):
                return

            context_key = (
                target_key
                if action == "replace"
                and target_key is not None
                else source_key
            )

            context_label.setText(
                self._group_context_text(
                    reference,
                    context_key,
                )
            )

            candidates = (
                self._group_location_candidates(
                    reference,
                    source_key,
                    target_key,
                )
            )

            state["photos"] = candidates

            state["updating_checks"] = True
            table.blockSignals(True)

            try:
                clear_batch_thumbnails()
                table.clearContents()
                table.setRowCount(
                    len(candidates)
                )

                for row, photo in enumerate(
                    candidates
                ):
                    check_item = QTableWidgetItem()
                    check_item.setFlags(
                        Qt.ItemFlag.ItemIsEnabled
                        | Qt.ItemFlag.ItemIsUserCheckable
                    )
                    check_item.setCheckState(
                        Qt.CheckState.Checked
                    )
                    check_item.setTextAlignment(
                        Qt.AlignmentFlag.AlignCenter
                    )

                    table.setItem(
                        row,
                        0,
                        check_item,
                    )

                    # Share the deferred, cache-aware thumbnail loader.
                    photo_widget = QWidget()
                    photo_layout = QVBoxLayout(
                        photo_widget
                    )
                    photo_layout.setContentsMargins(
                        4, 4, 4, 4
                    )
                    photo_layout.setSpacing(3)

                    thumbnail = self._create_thumbnail_label(photo)
                    batch_thumbnails.add(thumbnail)
                    photo_layout.addWidget(
                        thumbnail,
                        0,
                        Qt.AlignmentFlag.AlignHCenter,
                    )

                    filename = QLabel(
                        photo.filename
                    )
                    filename.setAlignment(
                        Qt.AlignmentFlag.AlignCenter
                    )
                    filename.setWordWrap(True)
                    filename.setToolTip(
                        photo.filename
                    )

                    photo_layout.addWidget(
                        filename
                    )

                    table.setCellWidget(
                        row,
                        1,
                        photo_widget,
                    )

                    table.setRowHeight(
                        row,
                        self.THUMBNAIL_HEIGHT + 42,
                    )

                    date_text = ""

                    if (
                        photo.capture_datetime
                        is not None
                    ):
                        date_text = format_datetime(
                            photo.capture_datetime
                        )

                    table.setItem(
                        row,
                        2,
                        QTableWidgetItem(
                            date_text
                        ),
                    )

                    current_location = (
                        self._effective_location(
                            photo
                        )
                    )

                    future_location = (
                        self._group_future_location(
                            photo,
                            source_key,
                            action,
                            target_key,
                        )
                    )

                    current_item = (
                        QTableWidgetItem(
                            current_location
                        )
                    )
                    current_item.setToolTip(
                        current_location
                    )

                    future_item = (
                        QTableWidgetItem(
                            future_location
                        )
                    )
                    future_item.setToolTip(
                        future_location
                    )

                    table.setItem(
                        row,
                        3,
                        current_item,
                    )
                    table.setItem(
                        row,
                        4,
                        future_item,
                    )

            finally:
                table.blockSignals(False)
                state["updating_checks"] = False

            info_label.setText(
                self._translator.tr(
                    "photos.places.group.compatible",
                    count=len(candidates),
                )
            )

            update_apply_text()

            QTimer.singleShot(
                0,
                position_header_checkbox,
            )

        def action_changed() -> None:
            replacing = (
                replace_radio.isChecked()
            )

            target_combo.setEnabled(
                replacing and bool(options)
            )

            rebuild_candidates()

        activate_radio.toggled.connect(
            lambda checked:
            action_changed()
            if checked
            else None
        )

        deactivate_radio.toggled.connect(
            lambda checked:
            action_changed()
            if checked
            else None
        )

        replace_radio.toggled.connect(
            lambda checked:
            action_changed()
            if checked
            else None
        )

        target_combo.currentIndexChanged.connect(
            lambda _index:
            rebuild_candidates()
            if replace_radio.isChecked()
            else None
        )

        table.itemChanged.connect(
            lambda _item:
            update_apply_text()
        )

        rebuild_candidates()

        QTimer.singleShot(
            0,
            position_header_checkbox,
        )

        try:
            result = dialog.exec()
        finally:
            clear_batch_thumbnails()

        checkbox.setProperty(
            "group_edit_pending",
            False,
        )

        if (
            result
            != QDialog.DialogCode.Accepted
        ):
            return

        action = current_action()

        target_key = (
            target_combo.currentData()
            if action == "replace"
            else None
        )

        if (
            target_key is not None
            and not isinstance(
                target_key,
                str,
            )
        ):
            return

        photos = state["photos"]

        if not isinstance(
            photos,
            list,
        ):
            return

        selected_photos: list[Photo] = []

        for row, photo in enumerate(
            photos
        ):
            item = table.item(
                row,
                0,
            )

            if (
                item is not None
                and item.checkState()
                == Qt.CheckState.Checked
            ):
                selected_photos.append(
                    photo
                )

        if not selected_photos:
            return

        self._apply_group_location_change(
            selected_photos,
            source_key,
            action,
            target_key,
        )

    def _apply_group_location_change(
        self,
        photos: list[Photo],
        source_key: str,
        action: str,
        target_key: str | None,
    ) -> None:
        pending_saves: list[
            tuple[
                Photo,
                tuple[LocationComponent, ...],
                str | None,
            ]
        ] = []

        for photo in photos:
            values = self._location_candidates_by_key(
                photo
            )

            source_value = values.get(
                source_key
            )

            target_value = (
                values.get(target_key)
                if target_key is not None
                else None
            )

            if (
                action == "activate"
                and source_value is None
            ):
                continue

            if (
                action == "replace"
                and (
                    target_key is None
                    or target_value is None
                )
            ):
                continue

            current = list(
                self._effective_components(
                    photo
                )
            )

            if action in (
                "deactivate",
                "replace",
            ):
                current = [
                    component
                    for component in current
                    if component.key.casefold()
                    != source_key
                ]

            if (
                action == "activate"
                and source_value is not None
                and not any(
                    component.key.casefold()
                    == source_key
                    for component in current
                )
            ):
                current.append(
                    LocationComponent(
                        key=source_key,
                        value=source_value,
                    )
                )

            if (
                action == "replace"
                and target_key is not None
                and target_value is not None
                and not any(
                    component.key.casefold()
                    == target_key
                    for component in current
                )
            ):
                current.append(
                    LocationComponent(
                        key=target_key,
                        value=target_value,
                    )
                )

            # Preserve the geographic ordering used by the builder.
            current.sort(
                key=lambda component:
                    self._location_priority(
                        component.key
                    )
                    or 100
            )

            selected = tuple(current)
            location_text = (
                self._components_text(
                    selected
                )
            )

            photo.selected_location_components = (
                selected
            )
            photo.location_text = location_text
            photo.location_selection_edited = True

            pending_saves.append(
                (
                    photo,
                    selected,
                    location_text,
                )
            )

        if pending_saves:
            if self._save_locations is not None:
                self._save_locations(
                    pending_saves
                )
            elif self._save_location is not None:
                # Compatibility fallback for callers that only
                # provide the historical per-photo callback.
                for (
                    photo,
                    selected,
                    location_text,
                ) in pending_saves:
                    self._save_location(
                        photo,
                        selected,
                        location_text,
                    )

        # One widget refresh after the complete grouped operation.
        self._rebuild_tree()

    def _composition_changed(
        self,
        photo: Photo,
        location_widget: QWidget,
    ) -> None:
        components: list[
            LocationComponent
        ] = []

        for checkbox in location_widget.findChildren(
            QCheckBox
        ):
            if not checkbox.isChecked():
                continue

            key = checkbox.property(
                "location_key"
            )
            value = checkbox.property(
                "location_value"
            )

            if (
                isinstance(key, str)
                and isinstance(value, str)
            ):
                components.append(
                    LocationComponent(
                        key=key,
                        value=value,
                    )
                )

        selected = tuple(components)
        location_text = self._components_text(
            selected
        )

        photo.selected_location_components = (
            selected
        )
        photo.location_text = location_text
        photo.location_selection_edited = True

        if self._save_location is not None:
            self._save_location(
                photo,
                selected,
                location_text,
            )

        self._after_editorial_change(
            photo
        )

    def _edit_free_location(
        self,
        photo: Photo,
    ) -> None:
        # Establish the automatic components before the first
        # free-text override so clearing the override can always
        # return to the composition.
        if not photo.location_selection_edited:
            components = self._effective_components(
                photo
            )
        else:
            components = tuple(
                photo.selected_location_components
            )

        component_text = self._components_text(
            components
        )

        if self._has_custom_location(photo):
            initial_text = (
                photo.location_text or ""
            )
        else:
            initial_text = (
                component_text
                or (
                    ""
                    if self._effective_location(photo)
                    == "—"
                    else self._effective_location(photo)
                )
            )

        dialog = QDialog(self)
        dialog.setWindowTitle(
            self._translator.tr(
                "photos.places.free_location"
            )
        )
        dialog.setMinimumWidth(560)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(
            18,
            18,
            18,
            18,
        )
        layout.setSpacing(10)

        label = QLabel(
            self._translator.tr(
                "photos.places.free_location_prompt"
            )
        )
        layout.addWidget(label)

        editor = QLineEdit(
            initial_text
        )
        editor.setClearButtonEnabled(True)
        layout.addWidget(editor)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(
            dialog.accept
        )
        buttons.rejected.connect(
            dialog.reject
        )
        layout.addWidget(buttons)

        editor.returnPressed.connect(
            dialog.accept
        )
        editor.setFocus()

        if (
            dialog.exec()
            != QDialog.DialogCode.Accepted
        ):
            return

        custom_text = (
            editor.text().strip()
        )

        # Empty text means "remove the override", not "force an
        # empty location". The structured composition becomes the
        # truth again.
        location_text = (
            custom_text
            or component_text
        )

        photo.selected_location_components = (
            components
        )
        photo.location_text = (
            location_text or None
        )
        photo.location_selection_edited = True

        if self._save_location is not None:
            self._save_location(
                photo,
                components,
                photo.location_text,
            )

        self._after_editorial_change(
            photo
        )

    # --------------------------------------------------------
    # Caption editing
    # --------------------------------------------------------

    def _caption_finished(
        self,
        photo: Photo,
        editor: QLineEdit,
    ) -> None:
        text = editor.text().strip()
        value = text or None

        if value == photo.caption:
            return

        photo.caption = value

        if self._save_caption is not None:
            self._save_caption(
                photo,
                value,
            )

        self._after_editorial_change(
            photo
        )

    def _caption_return_pressed(
        self,
        photo: Photo,
    ) -> None:
        visible = self._visible_dated_photos()

        try:
            index = next(
                i
                for i, candidate
                in enumerate(visible)
                if candidate.path == photo.path
            )
        except StopIteration:
            return

        next_photo = (
            visible[index + 1]
            if index + 1 < len(visible)
            else None
        )

        editor = self._caption_editors.get(
            str(photo.path)
        )

        if editor is not None:
            self._caption_finished(
                photo,
                editor,
            )

        if next_photo is None:
            return

        next_editor = self._caption_editors.get(
            str(next_photo.path)
        )

        if next_editor is not None:
            next_editor.setFocus()

            item = self._photo_items.get(
                str(next_photo.path)
            )
            if item is not None:
                self._tree.scrollToItem(
                    item,
                    QAbstractItemView.ScrollHint.EnsureVisible,
                )

    def _visible_dated_photos(
        self,
    ) -> list[Photo]:
        return [
            photo
            for photo in self._photos
            if photo.capture_datetime is not None
            and self._matches_filter(photo)
        ]

    # --------------------------------------------------------
    # Editorial refresh
    # --------------------------------------------------------

    def _after_editorial_change(
        self,
        photo: Photo,
    ) -> None:
        """
        Refresh only the edited photo.

        Rebuilding the complete view on every checkbox click caused
        visible flashing, focus loss and unnecessary recreation of
        every thumbnail/editor.

        An active search is the only case where a rebuild is needed:
        editing a location or caption can change whether the photo
        still matches the filter.
        """
        if self._filter_text:
            self._rebuild_tree()
            return

        path_key = str(photo.path)

        truth = self._truth_labels.get(
            path_key
        )

        if truth is not None:
            location_label, caption_label = truth

            location_label.setText(
                self._effective_location(photo)
            )
            caption_label.setText(
                self._display_caption(photo)
            )

        pencil = self._pencil_buttons.get(
            path_key
        )

        if pencil is not None:
            self._style_pencil(
                pencil,
                photo,
            )

    def _update_counter(
        self,
        visible_dated: int,
    ) -> None:
        total_dated = sum(
            photo.capture_datetime is not None
            for photo in self._photos
        )

        if self._filter_text:
            text = self._translator.tr(
                "photos.places.counter_filtered",
                visible=visible_dated,
                total=total_dated,
            )
        else:
            text = self._translator.tr(
                "photos.places.counter",
                count=total_dated,
            )

        self._counter_label.setText(text)

    # --------------------------------------------------------
    # Selection / source navigation
    # --------------------------------------------------------

    def _selection_changed(
        self,
    ) -> None:
        # Selection is deliberately only a visual/navigation
        # marker. No editing action is triggered here.
        pass

    def _request_source_photo(
        self,
        photo: Photo,
    ) -> None:
        if self._edit_source_photo is not None:
            self._edit_source_photo(photo)


class QTreeWidgetItemIteratorCompat:
    """
    Small Python iterator avoiding Qt-version-specific iterator
    behaviour in the rest of PhotoPlacesWidget.
    """

    def __init__(
        self,
        tree: QTreeWidget,
    ) -> None:
        self._items: list[
            QTreeWidgetItem
        ] = []

        for index in range(
            tree.topLevelItemCount()
        ):
            self._collect(
                tree.topLevelItem(index)
            )

    def _collect(
        self,
        item: QTreeWidgetItem,
    ) -> None:
        self._items.append(item)

        for index in range(
            item.childCount()
        ):
            self._collect(
                item.child(index)
            )

    def __iter__(self):
        return iter(self._items)
