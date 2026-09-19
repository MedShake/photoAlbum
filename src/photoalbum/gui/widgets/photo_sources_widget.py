from __future__ import annotations

from PySide6.QtCore import QEvent, QPoint, QSortFilterProxyModel, QTimer, Qt, Signal
from PySide6.QtGui import QImageReader, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QFrame, QHBoxLayout, QHeaderView,
    QLabel, QLineEdit, QPlainTextEdit, QProgressBar, QPushButton,
    QSplitter, QTableView, QVBoxLayout, QWidget,
)

from photoalbum.gui.models import PhotoTableModel
from photoalbum.gui.widgets.photo_actions_delegate import PhotoActionsDelegate
from photoalbum.i18n import Translator
from photoalbum.models import Photo


class PhotoSourcesWidget(QWidget):
    """Source controls and sortable photo browser, including hover previews."""

    source_requested = Signal()
    recursive_changed = Signal(bool)
    scan_requested = Signal()
    edit_datetime_requested = Signal(object)
    edit_gps_requested = Signal(object)
    open_photo_requested = Signal(object)

    def __init__(self, translator: Translator, parent=None) -> None:
        super().__init__(parent)
        self._translator = translator
        self._create_content()
        self.model.modelAboutToBeReset.connect(self._cancel_source_photo_preview)
        self.proxy_model.layoutAboutToBeChanged.connect(self._cancel_source_photo_preview)

    def hideEvent(self, event) -> None:
        self._cancel_source_photo_preview()
        super().hideEvent(event)

    def _create_content(self) -> None:
        sources_layout = QVBoxLayout(self)

        # Source folder.
        source_layout = QHBoxLayout()

        self.source_edit = QLineEdit()
        self.source_edit.setReadOnly(True)

        self.browse_button = QPushButton(self._translator.tr('main.choose_source'))

        self.browse_button.clicked.connect(self.source_requested.emit)

        source_layout.addWidget(QLabel(self._translator.tr('main.source_folder')))

        source_layout.addWidget(self.source_edit, 1)

        source_layout.addWidget(self.browse_button)

        sources_layout.addLayout(source_layout)

        # Recursive scan.
        self.recursive_checkbox = QCheckBox(self._translator.tr('main.include_subdirectories'))

        self.recursive_checkbox.toggled.connect(self.recursive_changed.emit)

        sources_layout.addWidget(self.recursive_checkbox)

        # Analysis controls.
        action_layout = QHBoxLayout()

        self.analyze_button = QPushButton(self._translator.tr('main.analyze_photos'))

        self.analyze_button.clicked.connect(self.scan_requested.emit)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)

        action_layout.addWidget(self.analyze_button)

        action_layout.addWidget(self.progress_bar, 1)

        sources_layout.addLayout(action_layout)

        # Analysis summary.
        self.summary_label = QLabel(self._translator.tr('main.no_analysis'))

        sources_layout.addWidget(self.summary_label)

        self.model = PhotoTableModel(translator=self._translator, parent=self)

        self.proxy_model = QSortFilterProxyModel(self)
        self.proxy_model.setSourceModel(self.model)
        self.proxy_model.setSortRole(PhotoTableModel.SORT_ROLE)
        self.proxy_model.setSortCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.proxy_model.setDynamicSortFilter(True)

        self.table = QTableView()
        self.table.setModel(self.proxy_model)

        self._source_preview = None
        self._source_preview_row = None
        self._source_preview_position = QPoint()

        self._source_preview_timer = QTimer(self)
        self._source_preview_timer.setSingleShot(True)
        self._source_preview_timer.setInterval(350)
        self._source_preview_timer.timeout.connect(self._show_pending_source_photo_preview)

        self.table.setMouseTracking(True)
        self.table.viewport().installEventFilter(self)

        self._photo_actions_delegate = PhotoActionsDelegate(self.table)

        self._photo_actions_delegate.edit_datetime_requested.connect(
            self.edit_datetime_requested.emit
        )
        self._photo_actions_delegate.edit_gps_requested.connect(self.edit_gps_requested.emit)
        self._photo_actions_delegate.open_photo_requested.connect(
            self.open_photo_requested.emit
        )

        self.table.setItemDelegateForColumn(1, self._photo_actions_delegate)

        self.table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)

        self.table.sortByColumn(2, Qt.SortOrder.AscendingOrder)

        header = self.table.horizontalHeader()

        # Let the user resize columns manually.
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)

        # Sensible initial widths. Long filenames must not force
        # the complete table to become excessively wide.
        self.table.setColumnWidth(0, 260)
        self.table.setColumnWidth(1, 116)
        self.table.setColumnWidth(2, 170)
        self.table.setColumnWidth(3, 130)
        self.table.setColumnWidth(4, 70)
        self.table.setColumnWidth(5, 150)
        self.table.setColumnWidth(6, 160)
        self.table.setColumnWidth(7, 120)

        header.setStretchLastSection(False)

        # Keep the sorted section visually consistent with the
        # other column headers.
        header_font = header.font()
        header_font.setBold(False)
        header.setFont(header_font)
        header.setStyleSheet('QHeaderView::section { font-weight: normal; }')

        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)

        splitter = QSplitter(Qt.Orientation.Vertical)

        splitter.addWidget(self.table)
        splitter.addWidget(self.log_view)

        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)

        sources_layout.addWidget(QLabel(self._translator.tr('main.photos')))
        sources_layout.addWidget(splitter, 1)

    def select_photo(self, photo: Photo) -> None:
        source_model = self.model

        for source_row in range(source_model.rowCount()):
            index = source_model.index(source_row, 0)

            candidate = source_model.data(index, Qt.ItemDataRole.UserRole)

            if isinstance(candidate, Photo) and candidate.path == photo.path:
                proxy_index = self.proxy_model.mapFromSource(index)

                if not proxy_index.isValid():
                    return

                self.table.selectRow(proxy_index.row())
                self.table.scrollTo(proxy_index, QAbstractItemView.ScrollHint.PositionAtCenter)
                self.table.setFocus()
                return

    def eventFilter(self, watched, event) -> bool:
        if hasattr(self, 'table') and watched is self.table.viewport():
            if event.type() == QEvent.Type.MouseMove:
                position = event.position().toPoint()
                index = self.table.indexAt(position)

                if index.isValid() and index.column() == 0:
                    row = index.row()

                    if row != self._source_preview_row:
                        self._cancel_source_photo_preview()
                        self._source_preview_row = row

                    self._source_preview_position = event.globalPosition().toPoint()

                    if (
                        self._source_preview is None
                        and not self._source_preview_timer.isActive()
                    ):
                        self._source_preview_timer.start()
                else:
                    self._cancel_source_photo_preview()

            elif event.type() in (
                QEvent.Type.Leave,
                QEvent.Type.MouseButtonPress,
                QEvent.Type.Wheel,
            ):
                self._cancel_source_photo_preview()

        return super().eventFilter(watched, event)

    def _show_pending_source_photo_preview(self) -> None:
        if self._source_preview_row is None:
            return

        proxy_index = self.proxy_model.index(self._source_preview_row, 0)

        if not proxy_index.isValid():
            return

        source_index = self.proxy_model.mapToSource(proxy_index)

        photo = self.model.photo_at(source_index.row())

        if photo is None:
            return

        reader = QImageReader(str(photo.path))
        reader.setAutoTransform(True)

        image = reader.read()

        if image.isNull():
            return

        pixmap = QPixmap.fromImage(image).scaled(
            420,
            320,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

        preview = QLabel(None, Qt.WindowType.ToolTip)
        preview.setPixmap(pixmap)
        preview.setFrameShape(QFrame.Shape.Box)
        preview.setContentsMargins(4, 4, 4, 4)
        preview.adjustSize()

        preview.move(self._source_preview_position + QPoint(16, 20))
        preview.show()

        self._source_preview = preview

    def _hide_source_photo_preview(self) -> None:
        if self._source_preview is not None:
            self._source_preview.close()
            self._source_preview.deleteLater()
            self._source_preview = None

    def _cancel_source_photo_preview(self) -> None:
        self._source_preview_timer.stop()
        self._hide_source_photo_preview()
        self._source_preview_row = None
