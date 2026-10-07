from __future__ import annotations

from PySide6.QtCore import QEvent, QPoint, QSortFilterProxyModel, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView, QHBoxLayout, QHeaderView,
    QLabel, QMenu, QPlainTextEdit, QProgressBar, QPushButton,
    QSplitter, QTableView, QVBoxLayout, QWidget, QGroupBox,
)

from photoalbum.gui.models import PhotoTableModel
from photoalbum.gui.hover_photo_preview import HoverPhotoPreview
from photoalbum.gui.preview_image_cache import PreviewImageCache
from photoalbum.gui.widgets.photo_actions_delegate import (
    PhotoActionsDelegate,
    PhotoCellDelegate,
    PhotoFilenameDelegate,
)
from photoalbum.i18n import Translator
from photoalbum.models import Photo


class PhotoSourcesWidget(QWidget):
    """Source controls and sortable photo browser, including hover previews."""

    source_requested = Signal()
    synology_source_requested = Signal()
    scan_requested = Signal()
    sync_requested = Signal()
    source_sync_requested = Signal(str)
    edit_datetime_requested = Signal(object)
    edit_gps_requested = Signal(object)
    open_photo_requested = Signal(object)
    edit_usage_requested = Signal(object)
    source_enabled_changed = Signal(str, bool)
    edit_source_requested = Signal(str)
    delete_source_requested = Signal(str)
    source_policy_changed = Signal(str, object)
    source_recursive_changed = Signal(str, bool)

    def __init__(
        self,
        translator: Translator,
        parent=None,
        *,
        hover_preview: HoverPhotoPreview | None = None,
    ) -> None:
        super().__init__(parent)
        self._translator = translator
        self._hover_preview = hover_preview or HoverPhotoPreview(
            PreviewImageCache(self), self
        )
        self._source_controls_enabled = True
        self._expanded_source_id = None
        self._create_content()
        self.model.modelAboutToBeReset.connect(self._cancel_source_photo_preview)
        self.proxy_model.layoutAboutToBeChanged.connect(self._cancel_source_photo_preview)

    def hideEvent(self, event) -> None:
        self._cancel_source_photo_preview()
        super().hideEvent(event)

    def _create_content(self) -> None:
        sources_layout = QVBoxLayout(self)

        add_group = QGroupBox(self._translator.tr("sources.add"))
        add_layout = QHBoxLayout(add_group)
        self.modify_source_button = QPushButton(self._translator.tr("sources.add_button"))
        menu = QMenu(self.modify_source_button)
        self.browse_action = menu.addAction(self._translator.tr("photos.source.local"))
        self.synology_action = menu.addAction(self._translator.tr("source.synology.choose"))
        self.browse_action.triggered.connect(self.source_requested.emit)
        self.synology_action.triggered.connect(self.synology_source_requested.emit)
        self.modify_source_button.setMenu(menu)
        add_layout.addWidget(self.modify_source_button)
        add_layout.addStretch()
        sources_layout.addWidget(add_group)

        # Each source is a self-contained card. Avoid a nested scroll area here:
        # the cards should simply grow with the page so their actions and state
        # remain immediately visible.
        source_container = QWidget()
        self._source_cards = QVBoxLayout(source_container)
        self._source_cards.setContentsMargins(0, 0, 0, 0)
        self._source_cards.setSpacing(8)
        sources_layout.addWidget(source_container)
        self._sources = []

        # Explicit cancellation remains available even though the former global
        # analysis block was removed from the UI.
        self.cancel_scan_button = QPushButton(
            self._translator.tr("main.analysis_cancel_button")
        )
        self.cancel_scan_button.setVisible(False)
        self.cancel_scan_button.clicked.connect(self.scan_requested.emit)
        cancel_layout = QHBoxLayout()
        cancel_layout.addStretch(1)
        cancel_layout.addWidget(self.cancel_scan_button)
        sources_layout.addLayout(cancel_layout)

        # Processing progress.
        self.source_progress_label = QLabel(
            self._translator.tr("photos.progress.source")
        )
        self.source_progress_bar = QProgressBar()

        self.source_progress_label.setVisible(False)
        self.source_progress_bar.setVisible(False)

        self.source_progress_layout = QHBoxLayout()
        self.source_progress_layout.addWidget(
            self.source_progress_label
        )
        self.source_progress_layout.addWidget(
            self.source_progress_bar,
            1,
        )

        sources_layout.addLayout(
            self.source_progress_layout
        )

        # Scan phase progress.
        self.metadata_progress_label = QLabel(
            self._translator.tr("photos.progress.metadata")
        )
        self.metadata_progress_bar = QProgressBar()
        self.metadata_progress_bar.setVisible(False)

        self.metadata_progress_layout = QHBoxLayout()
        self.metadata_progress_layout.addWidget(
            self.metadata_progress_label
        )
        self.metadata_progress_layout.addWidget(
            self.metadata_progress_bar,
            1,
        )

        self.metadata_progress_label.setVisible(False)

        sources_layout.addLayout(
            self.metadata_progress_layout
        )

        self.nominatim_progress_label = QLabel(
            self._translator.tr("photos.progress.nominatim")
        )
        self.nominatim_progress_bar = QProgressBar()

        self.nominatim_progress_label.setVisible(False)
        self.nominatim_progress_bar.setVisible(False)

        self.nominatim_progress_layout = QHBoxLayout()
        self.nominatim_progress_layout.addWidget(
            self.nominatim_progress_label
        )
        self.nominatim_progress_layout.addWidget(
            self.nominatim_progress_bar,
            1,
        )

        sources_layout.addLayout(
            self.nominatim_progress_layout
        )

        # Kept as an internal status sink for existing controller workflows,
        # but operation results belong in the journal rather than as a persistent
        # line between the source cards and the photo table.
        self.summary_label = QLabel(self._translator.tr('main.no_analysis'))
        self.summary_label.setVisible(False)

        self.model = PhotoTableModel(translator=self._translator, parent=self)
        self._provider_label = self._translator.tr("photos.policy.provider")

        self.proxy_model = QSortFilterProxyModel(self)
        self.proxy_model.setSourceModel(self.model)
        self.proxy_model.setSortRole(PhotoTableModel.SORT_ROLE)
        self.proxy_model.setSortCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.proxy_model.setDynamicSortFilter(True)

        self.table = QTableView()
        self.table.setModel(self.proxy_model)

        self._source_preview_row = None
        self._source_preview_position = QPoint()

        self.table.setMouseTracking(True)
        self.table.viewport().installEventFilter(self)

        self._photo_filename_delegate = PhotoFilenameDelegate(
            self.table,
            translator=self._translator,
        )
        self._photo_filename_delegate.open_photo_requested.connect(
            self.open_photo_requested.emit
        )

        self._photo_actions_delegate = PhotoActionsDelegate(
            self.table,
            translator=self._translator,
        )
        self._photo_actions_delegate.edit_datetime_requested.connect(
            self.edit_datetime_requested.emit
        )
        self._photo_actions_delegate.edit_gps_requested.connect(
            self.edit_gps_requested.emit
        )
        self._photo_actions_delegate.edit_usage_requested.connect(
            self.edit_usage_requested.emit
        )

        # Keep the Photos table visually passive across platform styles:
        # alternate rows remain visible, but row selection/hover/focus painting
        # is deliberately neutralized. Mouse tracking stays enabled because
        # filename hover previews and delegate tooltips depend on it.
        self._photo_cell_delegate = PhotoCellDelegate(self.table)
        self.table.setItemDelegate(self._photo_cell_delegate)
        self.table.setItemDelegateForColumn(0, self._photo_filename_delegate)
        self.table.setItemDelegateForColumn(1, self._photo_actions_delegate)

        self.table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)

        self.table.sortByColumn(2, Qt.SortOrder.AscendingOrder)

        header = self.table.horizontalHeader()

        # Let the user resize columns manually.
        header.setSectionResizeMode(
            QHeaderView.ResizeMode.Interactive
        )
        # Filename is the elastic column. It keeps a real minimum
        # width, but absorbs any horizontal space left by the other
        # columns.
        self._filename_column_min_width = 300

        # Sensible initial widths. Long filenames must not force
        # the complete table to become excessively wide.
        self.table.setColumnWidth(1, 112)
        self.table.setColumnWidth(2, 170)
        self.table.setColumnWidth(3, 130)
        self.table.setColumnWidth(4, 70)
        self.table.setColumnWidth(5, 150)
        self.table.setColumnWidth(6, 160)
        self.table.setColumnWidth(7, 120)
        self.table.setColumnWidth(8, 155)

        self._update_filename_column_width()


        header.setStretchLastSection(False)

        # Keep the sorted section visually consistent with the
        # other column headers.
        header_font = header.font()
        header_font.setBold(False)
        header.setFont(header_font)
        header.setStyleSheet('QHeaderView::section { font-weight: normal; }')

        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)

        log_container = QWidget()
        log_layout = QVBoxLayout(log_container)
        log_layout.setContentsMargins(0, 0, 0, 0)
        log_layout.setSpacing(4)
        log_layout.addWidget(QLabel(self._translator.tr("main.activity_log")))
        log_layout.addWidget(self.log_view, 1)

        splitter = QSplitter(Qt.Orientation.Vertical)

        splitter.addWidget(self.table)
        splitter.addWidget(log_container)

        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)

        sources_layout.addWidget(QLabel(self._translator.tr('main.photos')))
        sources_layout.addWidget(splitter, 1)

    def set_sources(self, sources, available, labels, sessions=None) -> None:
        from .source_card import SourceCard
        sessions = sessions or {}
        previous_expanded = self._expanded_source_id
        while self._source_cards.count():
            item = self._source_cards.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        source_ids = {source.id for source in sources}
        if previous_expanded not in source_ids:
            previous_expanded = sources[0].id if sources else None
        self._expanded_source_id = previous_expanded
        for source in sources:
            card = SourceCard(
                source,
                available.get(source.id, {}),
                self._translator,
                session_available=(
                    sessions.get(source.id)
                    if source.kind != "local"
                    else None
                ),
            )
            card.enabled_changed.connect(self.source_enabled_changed.emit)
            card.sync_requested.connect(self.source_sync_requested.emit)
            card.edit_requested.connect(self.edit_source_requested.emit)
            card.delete_requested.connect(self.delete_source_requested.emit)
            card.policy_changed.connect(self.source_policy_changed.emit)
            card.recursive_changed.connect(self.source_recursive_changed.emit)
            card.expansion_requested.connect(self._source_expansion_requested)
            card.set_expanded(source.id == self._expanded_source_id)
            card.setEnabled(self._source_controls_enabled)
            self._source_cards.addWidget(card)
        self.model.set_sources(labels, {source.id: source.collection_name for source in sources})
        self._sources = list(sources)


    def _source_expansion_requested(self, source_id: str, expanded: bool) -> None:
        """Keep at most one source details row expanded at a time."""
        self._expanded_source_id = source_id if expanded else None
        for index in range(self._source_cards.count()):
            card = self._source_cards.itemAt(index).widget()
            if card is not None and hasattr(card, "set_expanded"):
                card.set_expanded(expanded and card.source.id == source_id)

    def set_processing_cancellable(self, cancellable: bool) -> None:
        self.cancel_scan_button.setText(
            self._translator.tr("main.analysis_cancel_button")
        )
        self.cancel_scan_button.setVisible(bool(cancellable))
        self.cancel_scan_button.setEnabled(bool(cancellable))

    def set_processing_stopping(self) -> None:
        self.cancel_scan_button.setText(
            self._translator.tr("main.analysis_stopping_button")
        )
        self.cancel_scan_button.setEnabled(False)

    def set_source_controls_enabled(self, enabled: bool) -> None:
        """Enable or disable every per-source card action.

        The cards replaced the former sources QGroupBox, so scan-state handling
        must target the cards themselves rather than a removed container.
        Remember the state as cards may be rebuilt while an operation is active.
        """
        self._source_controls_enabled = bool(enabled)
        for index in range(self._source_cards.count()):
            widget = self._source_cards.itemAt(index).widget()
            if widget is not None:
                widget.setEnabled(self._source_controls_enabled)

    @property
    def has_active_sources(self) -> bool:
        return any(source.enabled for source in self._sources)

    @property
    def has_active_remote_sources(self) -> bool:
        return any(
            source.enabled and source.kind != "local"
            for source in self._sources
        )

    def prepare_source_progress(self, provider_label: str | None = None) -> None:
        """Show source synchronization and hide scan-only phases."""
        self.source_progress_label.setVisible(True)
        self.source_progress_label.setText(
            self._translator.tr(
                "photos.progress.source_provider",
                provider=provider_label or self._provider_label,
            )
        )
        self.source_progress_bar.setVisible(True)
        self.source_progress_bar.setRange(0, 0)
        self.source_progress_bar.setValue(0)
        self.source_progress_bar.setFormat(
            self._translator.tr(
                "photos.progress.source_waiting",
                provider=provider_label or self._provider_label,
            )
        )

        self.metadata_progress_label.setVisible(False)
        self.metadata_progress_bar.setVisible(False)
        self.nominatim_progress_label.setVisible(False)
        self.nominatim_progress_bar.setVisible(False)

    def update_source_progress(
        self,
        current: int,
        total: int,
    ) -> None:
        current = max(current, 0)
        total = max(total, 0)

        if total <= 0:
            self.source_progress_bar.setRange(0, 0)
            self.source_progress_bar.setFormat(
                self._translator.tr(
                    "photos.progress.source_waiting",
                    provider=self._provider_label,
                )
            )
            return

        current = min(current, total)
        self.source_progress_bar.setRange(0, total)
        self.source_progress_bar.setValue(current)
        self.source_progress_bar.setFormat(
            self._translator.tr(
                "photos.progress.value",
                current=current,
                total=total,
            )
        )

    def finish_processing_progress(self) -> None:
        """Hide transient processing indicators after an operation."""
        self.set_processing_cancellable(False)
        for widget in (
            self.source_progress_label,
            self.source_progress_bar,
            self.metadata_progress_label,
            self.metadata_progress_bar,
            self.nominatim_progress_label,
            self.nominatim_progress_bar,
        ):
            widget.setVisible(False)

    def prepare_scan_progress(
        self,
        *,
        nominatim_enabled: bool,
    ) -> None:
        """Reset and expose progress rows for a new scan."""
        self.source_progress_label.setVisible(False)
        self.source_progress_bar.setVisible(False)

        self.metadata_progress_label.setVisible(True)
        self.metadata_progress_bar.setVisible(True)
        self.metadata_progress_bar.setRange(0, 0)
        self.metadata_progress_bar.setValue(0)
        self.metadata_progress_bar.setFormat(
            self._translator.tr("photos.progress.waiting")
        )

        self.nominatim_progress_label.setVisible(
            nominatim_enabled
        )
        self.nominatim_progress_bar.setVisible(
            nominatim_enabled
        )

        if nominatim_enabled:
            self.nominatim_progress_bar.setRange(0, 0)
            self.nominatim_progress_bar.setValue(0)
            self.nominatim_progress_bar.setFormat(
                self._translator.tr("photos.progress.waiting")
            )

    def update_scan_phase_progress(
        self,
        phase: str,
        current: int,
        total: int,
    ) -> None:
        """Update one scan phase without coupling the widget to scanner types."""
        if phase == "metadata":
            progress_bar = self.metadata_progress_bar
        elif phase == "nominatim":
            progress_bar = self.nominatim_progress_bar
        else:
            return

        current = max(current, 0)
        total = max(total, 0)

        if total <= 0:
            progress_bar.setRange(0, 1)
            progress_bar.setValue(0)
            progress_bar.setFormat(
                self._translator.tr(
                    "photos.progress.value",
                    current=0,
                    total=0,
                )
            )
            return

        current = min(current, total)

        progress_bar.setRange(0, total)
        progress_bar.setValue(current)
        progress_bar.setFormat(
            self._translator.tr(
                "photos.progress.value",
                current=current,
                total=total,
            )
        )

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._update_filename_column_width()

    def _update_filename_column_width(self) -> None:
        """Share spare width between filename and city columns."""
        if not hasattr(
            self,
            "_filename_column_min_width",
        ):
            return

        filename_min = (
            self._filename_column_min_width
        )
        city_min = 150

        # Columns 0 (filename) and 5 (city) are elastic.
        # All other columns keep their current widths.
        fixed_width = sum(
            self.table.columnWidth(column)
            for column in range(
                self.table.model().columnCount()
            )
            if column not in (0, 5)
        )

        elastic_available = (
            self.table.viewport().width()
            - fixed_width
        )

        extra = max(
            0,
            elastic_available
            - filename_min
            - city_min,
        )

        filename_width = (
            filename_min
            + round(extra * 2 / 3)
        )
        city_width = (
            city_min
            + extra
            - round(extra * 2 / 3)
        )

        self.table.setColumnWidth(
            0,
            filename_width,
        )
        self.table.setColumnWidth(
            5,
            city_width,
        )


    def select_photo(self, photo: Photo) -> None:
        source_model = self.model

        for source_row in range(source_model.rowCount()):
            index = source_model.index(source_row, 0)

            candidate = source_model.data(index, Qt.ItemDataRole.UserRole)

            if isinstance(candidate, Photo) and candidate.identity == photo.identity:
                proxy_index = self.proxy_model.mapFromSource(index)

                if not proxy_index.isValid():
                    return

                # Keep programmatic navigation without creating a visual
                # selection. The current index is still useful to callers and
                # tests, while NoSelection/NoFocus keep the table passive.
                self.table.setCurrentIndex(proxy_index)
                self.table.scrollTo(proxy_index, QAbstractItemView.ScrollHint.PositionAtCenter)
                return

    def eventFilter(self, watched, event) -> bool:
        if hasattr(self, 'table') and watched is self.table.viewport():
            if event.type() == QEvent.Type.MouseMove:
                position = event.position().toPoint()
                index = self.table.indexAt(position)

                if index.isValid() and index.column() == 0:
                    cell_rect = self.table.visualRect(index)
                    if PhotoFilenameDelegate.is_over_open_icon(
                        cell_rect,
                        position,
                    ):
                        self._cancel_source_photo_preview()
                    else:
                        row = index.row()
                        self._source_preview_position = (
                            event.globalPosition().toPoint()
                        )

                        if row != self._source_preview_row:
                            self._cancel_source_photo_preview()
                            self._source_preview_row = row
                            self._schedule_source_photo_preview()
                        else:
                            self._hover_preview.update_position(
                                self._source_preview_position
                            )
                else:
                    self._cancel_source_photo_preview()

            elif event.type() in (
                QEvent.Type.Leave,
                QEvent.Type.MouseButtonPress,
                QEvent.Type.Wheel,
            ):
                self._cancel_source_photo_preview()

        return super().eventFilter(watched, event)

    def _schedule_source_photo_preview(self) -> None:
        if self._source_preview_row is None:
            return

        proxy_index = self.proxy_model.index(self._source_preview_row, 0)

        if not proxy_index.isValid():
            return

        source_index = self.proxy_model.mapToSource(proxy_index)

        photo = self.model.photo_at(source_index.row())

        if photo is None:
            return

        self._hover_preview.schedule(
            photo.path,
            self._source_preview_position,
        )

    def _cancel_source_photo_preview(self) -> None:
        self._hover_preview.cancel()
        self._source_preview_row = None
