from __future__ import annotations

from collections.abc import Callable, Sequence

from PySide6.QtCore import (
    QEvent,
    QPoint,
    QTimer,
    Qt,
)
from PySide6.QtGui import (
    QImageReader,
    QPixmap,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QStyledItemDelegate,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from photoalbum.gui.models.photo_places_table_model import (
    PhotoPlacesTableModel,
)
from photoalbum.i18n import Translator
from photoalbum.models import LocationComponent, Photo

from .flow_layout import FlowLayout
from .photo_actions_delegate import PhotoActionsDelegate


class _PhotoDateDelegate(QStyledItemDelegate):
    """Paint the same calendar icon as the Sources table."""

    def paint(
        self,
        painter,
        option,
        index,
    ) -> None:
        base_option = type(option)(option)
        base_option.text = ""

        from PySide6.QtWidgets import QApplication, QStyle

        QApplication.style().drawControl(
            QStyle.ControlElement.CE_ItemViewItem,
            base_option,
            painter,
        )

        photo = index.data(
            Qt.ItemDataRole.UserRole
        )

        if not isinstance(photo, Photo):
            return

        PhotoActionsDelegate._paint_calendar(
            painter,
            option.rect,
            missing=(
                photo.capture_datetime is None
            ),
        )


class PhotoPlacesWidget(QWidget):
    # Données techniques conservées dans raw_location_data mais
    # inutiles comme choix éditoriaux dans l'écran Lieux.
    HIDDEN_COMPONENT_KEYS = {
        "country_code",
        "house_number",
        "postcode",
    }

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
        parent=None,
    ) -> None:
        super().__init__(parent)

        self._translator = translator or Translator("en")
        self._save_location = save_location

        self._preview = None
        self._preview_row = None
        self._preview_position = QPoint()

        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(350)
        self._preview_timer.timeout.connect(
            self._show_pending_photo_preview
        )

        self._model = PhotoPlacesTableModel(
            translator=self._translator,
            parent=self,
        )

        self._create_ui()

    def _create_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 0)

        description = QLabel(
            self._translator.tr(
                "photos.places.description"
            )
        )
        description.setWordWrap(True)

        layout.addWidget(description)

        self._table = QTableView()
        self._table.setModel(self._model)

        self._date_delegate = _PhotoDateDelegate(
            self._table
        )
        self._table.setItemDelegateForColumn(
            1,
            self._date_delegate,
        )

        # Le numéro de photo est déjà une vraie colonne du modèle.
        # Masquer les numéros de lignes natifs de QTableView.
        self._table.verticalHeader().setVisible(False)

        # Lieux is edited directly through its controls.
        # A selected row has no meaning here.
        self._table.setSelectionMode(
            QAbstractItemView.SelectionMode.NoSelection
        )

        self._table.setAlternatingRowColors(True)
        self._table.setSortingEnabled(True)
        self._table.sortByColumn(
            1,
            Qt.SortOrder.AscendingOrder,
        )
        self._table.setMouseTracking(True)

        self._table.setTextElideMode(
            Qt.TextElideMode.ElideRight
        )

        # La colonne Photo utilise le viewport pour afficher
        # une vraie prévisualisation au survol.
        self._table.viewport().installEventFilter(self)

        header = self._table.horizontalHeader()

        header.setSectionResizeMode(
            0,
            QHeaderView.ResizeMode.ResizeToContents,
        )
        header.setSectionResizeMode(
            1,
            QHeaderView.ResizeMode.Fixed,
        )
        header.setSectionResizeMode(
            2,
            QHeaderView.ResizeMode.Interactive,
        )
        header.setSectionResizeMode(
            3,
            QHeaderView.ResizeMode.Interactive,
        )
        header.setSectionResizeMode(
            4,
            QHeaderView.ResizeMode.Stretch,
        )
        header.setSectionResizeMode(
            5,
            QHeaderView.ResizeMode.Fixed,
        )

        self._table.setColumnWidth(5, 38)

        header.sectionResized.connect(
            self._section_resized
        )

        header_font = header.font()
        header_font.setBold(False)
        header.setFont(header_font)
        header.setStyleSheet(
            "QHeaderView::section { font-weight: normal; }"
        )

        self._table.setColumnWidth(1, 42)
        self._table.setColumnWidth(2, 240)
        self._table.setColumnWidth(3, 280)

        layout.addWidget(self._table, 1)

    def set_photos(
        self,
        photos: Sequence[Photo],
    ) -> None:
        self._model.set_photos(photos)
        self._rebuild_composition_widgets()

    def clear(self) -> None:
        self._model.clear()

    def _rebuild_composition_widgets(self) -> None:
        for row in range(self._model.rowCount()):
            self._install_composition_widget(row)
            self._install_free_location_button(row)

        # The stretched Composition column receives its final width only
        # after Qt has completed the current layout pass. Recalculate row
        # heights once that geometry is available.
        QTimer.singleShot(
            0,
            self._resize_composition_rows,
        )

    def _install_composition_widget(
        self,
        row: int,
    ) -> None:
        result = self._model.caption_result_at(row)

        if result is None:
            return

        container = QFrame()
        container.setFrameShape(QFrame.Shape.NoFrame)

        flow = FlowLayout(
            container,
            margin=3,
            horizontal_spacing=10,
            vertical_spacing=3,
        )

        photo = self._model.photo_at(row)

        if (
            photo is not None
            and photo.location_selection_edited
        ):
            selected = {
                (component.key, component.value)
                for component
                in photo.selected_location_components
            }
        else:
            selected = {
                (candidate.key, candidate.value)
                for candidate in result.selected
            }

        visible_count = 0

        for candidate in result.candidates:
            if not self._component_is_visible(
                candidate.key
            ):
                continue

            checkbox = QCheckBox(candidate.value)

            checkbox.setChecked(
                (candidate.key, candidate.value)
                in selected
            )

            # Le vocabulaire Nominatim reste disponible pour
            # comprendre la provenance sans polluer l'écran.
            checkbox.setToolTip(candidate.key)

            checkbox.setProperty(
                "location_key",
                candidate.key,
            )
            checkbox.setProperty(
                "location_value",
                candidate.value,
            )

            checkbox.toggled.connect(
                lambda _checked, current_row=row:
                    self._composition_changed(current_row)
            )

            flow.addWidget(checkbox)
            visible_count += 1

        if visible_count == 0:
            empty = QLabel("—")
            flow.addWidget(empty)

        self._table.setIndexWidget(
            self._model.index(row, 4),
            container,
        )

        # Première estimation. Les lignes seront recalculées
        # également lors d'un redimensionnement.
        self._resize_composition_row(row)

    def _composition_changed(
        self,
        row: int,
    ) -> None:
        index = self._model.index(row, 4)
        container = self._table.indexWidget(index)

        if container is None:
            return

        components = []

        for checkbox in container.findChildren(QCheckBox):
            if not checkbox.isChecked():
                continue

            key = checkbox.property("location_key")
            value = checkbox.property("location_value")

            if not isinstance(key, str):
                continue

            if not isinstance(value, str):
                continue

            components.append(
                LocationComponent(
                    key=key,
                    value=value,
                )
            )

        selected = tuple(components)

        location_text = self._model.set_selected_components(
            row,
            selected,
        )

        photo = self._model.photo_at(row)

        if (
            photo is not None
            and self._save_location is not None
        ):
            self._save_location(
                photo,
                selected,
                location_text,
            )

    def _install_free_location_button(
        self,
        row: int,
    ) -> None:
        button = QPushButton("✎")
        button.setFlat(True)
        button.setToolTip(
            self._translator.tr(
                "photos.places.free_location"
            )
        )
        button.setCursor(
            Qt.CursorShape.PointingHandCursor
        )
        button.setStyleSheet(
            "QPushButton {"
            " color: #555555;"
            " border: none;"
            " font-size: 16px;"
            " padding: 0px;"
            "}"
            "QPushButton:hover {"
            " color: #222222;"
            "}"
        )

        button.clicked.connect(
            lambda _checked=False, current_row=row:
                self._edit_free_location(current_row)
        )

        self._table.setIndexWidget(
            self._model.index(row, 5),
            button,
        )

    def _edit_free_location(
        self,
        row: int,
    ) -> None:
        photo = self._model.photo_at(row)

        if photo is None:
            return

        # If an editorial text already exists, edit that text.
        # Otherwise start from the currently displayed automatic
        # suggestion so the user does not have to retype it.
        if photo.location_selection_edited:
            initial_text = photo.location_text or ""
        else:
            index = self._model.index(row, 3)
            displayed = self._model.data(
                index,
                Qt.ItemDataRole.DisplayRole,
            )
            initial_text = (
                ""
                if displayed in (None, "—")
                else str(displayed)
            )

        dialog = QDialog(self)
        dialog.setWindowTitle(
            self._translator.tr(
                "photos.places.free_location"
            )
        )
        dialog.setMinimumWidth(560)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(10)

        label = QLabel(
            self._translator.tr(
                "photos.places.free_location_prompt"
            )
        )
        layout.addWidget(label)

        editor = QLineEdit(initial_text)
        editor.setMinimumHeight(34)
        editor.setClearButtonEnabled(True)
        editor.setStyleSheet(
            "QLineEdit {"
            " border: 1px solid palette(mid);"
            " border-radius: 3px;"
            " padding: 5px 7px;"
            " background: palette(base);"
            " color: palette(text);"
            "}"
            "QLineEdit:focus {"
            " border: 2px solid palette(highlight);"
            " padding: 4px 6px;"
            "}"
        )
        editor.selectAll()
        layout.addWidget(editor)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        editor.returnPressed.connect(dialog.accept)

        editor.setFocus()

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        location_text = self._model.set_location_text(
            row,
            editor.text(),
        )

        # The structured selection is deliberately preserved.
        # Only its editorial wording is overridden.
        if self._save_location is not None:
            self._save_location(
                photo,
                photo.selected_location_components,
                location_text,
            )

    def _component_is_visible(
        self,
        key: str,
    ) -> bool:
        normalized = key.casefold()

        if normalized in self.HIDDEN_COMPONENT_KEYS:
            return False

        # Nominatim peut renvoyer différentes clés ISO3166
        # selon le niveau administratif.
        if normalized.startswith("iso3166"):
            return False

        return True

    def _resize_composition_rows(self) -> None:
        for row in range(self._model.rowCount()):
            self._resize_composition_row(row)

    def _resize_composition_row(
        self,
        row: int,
    ) -> None:
        index = self._model.index(row, 4)
        widget = self._table.indexWidget(index)

        if widget is None or widget.layout() is None:
            return

        width = max(
            80,
            self._table.columnWidth(4) - 8,
        )

        height = widget.layout().heightForWidth(width)

        self._table.setRowHeight(
            row,
            max(30, height + 6),
        )

    def showEvent(self, event) -> None:
        super().showEvent(event)

        # set_photos() can run while the Places tab is hidden.
        # At that point the stretched Composition column does not
        # necessarily have its final geometry yet. Recalculate once
        # the widget is actually shown.
        QTimer.singleShot(
            0,
            self._resize_composition_rows,
        )

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._resize_composition_rows()

    def _section_resized(
        self,
        logical_index: int,
        _old_size: int,
        _new_size: int,
    ) -> None:
        if logical_index != 4:
            return

        # Let QHeaderView finish applying the new section geometry
        # before asking FlowLayout for its height.
        QTimer.singleShot(
            0,
            self._resize_composition_rows,
        )

    def eventFilter(
        self,
        watched,
        event,
    ) -> bool:
        if watched is self._table.viewport():
            if event.type() == QEvent.Type.MouseMove:
                position = event.position().toPoint()
                index = self._table.indexAt(position)

                if (
                    index.isValid()
                    and index.column() == 2
                ):
                    row = index.row()

                    if row != self._preview_row:
                        self._hide_photo_preview()
                        self._preview_row = row

                    self._preview_position = (
                        event.globalPosition().toPoint()
                    )

                    if (
                        self._preview is None
                        and not self._preview_timer.isActive()
                    ):
                        self._preview_timer.start()

                else:
                    self._cancel_photo_preview()

            elif event.type() in (
                QEvent.Type.Leave,
                QEvent.Type.MouseButtonPress,
                QEvent.Type.Wheel,
            ):
                self._cancel_photo_preview()

        return super().eventFilter(
            watched,
            event,
        )

    def _show_pending_photo_preview(self) -> None:
        if self._preview_row is None:
            return

        photo = self._model.photo_at(
            self._preview_row
        )

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

        preview = QLabel(
            None,
            Qt.WindowType.ToolTip,
        )
        preview.setPixmap(pixmap)
        preview.setFrameShape(
            QFrame.Shape.Box
        )
        preview.setContentsMargins(
            4,
            4,
            4,
            4,
        )
        preview.adjustSize()

        preview.move(
            self._preview_position
            + QPoint(16, 20)
        )
        preview.show()

        self._preview = preview

    def _hide_photo_preview(self) -> None:
        if self._preview is not None:
            self._preview.close()
            self._preview.deleteLater()
            self._preview = None

    def _cancel_photo_preview(self) -> None:
        self._preview_timer.stop()
        self._hide_photo_preview()
        self._preview_row = None

