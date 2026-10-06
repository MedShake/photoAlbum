from __future__ import annotations
from dataclasses import replace

from photoalbum.i18n import Translator
from photoalbum.album.composition import PageComposer

from photoalbum.gui.icon_resources import resource_icon
from photoalbum.gui.template_labels import template_display_name

from PySide6.QtCore import QDate, QEvent, QLocale, QPoint, QRect, QSize, QTimer, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QGuiApplication, QPainter
from shiboken6 import isValid

from PySide6.QtWidgets import (
    QHeaderView,
    QGroupBox,
    QScrollArea,
    QLabel,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
    QHBoxLayout,
    QToolButton,
    QStyle,
    QStyleOptionGroupBox,
    QFrame,
)

from photoalbum.album import (
    CoverPosition,
    AlbumStructureSettings,
    AlbumBuildResult,
    AlbumSummaryBuilder,
    BlankPageReason,
    PlanItemKind,
    TemplateRegistry,
)



class _IconTitleGroupBox(QGroupBox):
    """Native QGroupBox title with a small SVG icon before the text.

    The group box itself is left entirely to the platform style.  A leading
    em-space reserves room inside the native title area, and the icon is
    painted into that reserved area.  This avoids QSS title styling, whose
    frame/title rendering differs between Linux and Windows.
    """

    _TITLE_PREFIX = "\u2003 "

    def __init__(
        self,
        title: str,
        icon_filename: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(self._TITLE_PREFIX + title, parent)
        self._title_icon = resource_icon(icon_filename)

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt API
        super().paintEvent(event)

        option = QStyleOptionGroupBox()
        self.initStyleOption(option)
        title_rect = self.style().subControlRect(
            QStyle.ComplexControl.CC_GroupBox,
            option,
            QStyle.SubControl.SC_GroupBoxLabel,
            self,
        )
        if not title_rect.isValid():
            return

        icon_size = max(10, min(14, title_rect.height() - 2))
        icon_rect = QRect(
            title_rect.left() + 1,
            title_rect.center().y() - icon_size // 2,
            icon_size,
            icon_size,
        )
        painter = QPainter(self)
        self._title_icon.paint(painter, icon_rect)


_COVER_POSITION_ROLE = int(Qt.ItemDataRole.UserRole) + 1
_PAGE_PREVIEW_WIDTH = 450
_PAGE_PREVIEW_DELAY_MS = 350


class AlbumPlanWidget(QWidget):
    settings_changed = Signal(object)
    def __init__(
        self,
        registry: TemplateRegistry,
        translator: Translator | None = None,
        parent: QWidget | None = None,
        preview_widget=None,
    ) -> None:
        super().__init__(parent)

        self._registry = registry
        self._translator = translator or Translator()
        self._summary_builder = AlbumSummaryBuilder()
        self._caption_overflows = {}
        self._hovered_plan_item = None
        self._action_hover_items = {}
        self._preview_hover_items = {}
        self._preview_widget = preview_widget
        self._pending_page_preview = None
        self._page_preview_popup = None
        self._page_preview_timer = QTimer(self)
        self._page_preview_timer.setSingleShot(True)
        self._page_preview_timer.setInterval(_PAGE_PREVIEW_DELAY_MS)
        self._page_preview_timer.timeout.connect(self._show_pending_page_preview)

        self._create_ui()
        self.clear()

    def _create_ui(self) -> None:
        layout = QVBoxLayout(self)

        summary_group = QGroupBox(
            self._translator.tr("plan.summary")
        )
        summary_layout = QVBoxLayout(summary_group)

        self._summary_label = QLabel()
        self._summary_label.setWordWrap(True)

        summary_layout.addWidget(self._summary_label)

        layout.addWidget(summary_group)

        # Warnings are exceptional: the whole panel disappears
        # when there is nothing requiring the user's attention.
        self._warnings_group = _IconTitleGroupBox(
            self._translator.tr("plan.warnings"),
            "plan-warning-red.svg",
        )
        warnings_layout = QVBoxLayout(
            self._warnings_group
        )

        self._warnings_label = QLabel()
        self._warnings_label.setWordWrap(True)
        self._warnings_label.setAlignment(
            Qt.AlignmentFlag.AlignTop
            | Qt.AlignmentFlag.AlignLeft
        )
        self._warnings_label.setContentsMargins(4, 2, 4, 2)

        self._warnings_scroll = QScrollArea()
        self._warnings_scroll.setWidgetResizable(True)
        self._warnings_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._warnings_scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self._warnings_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._warnings_scroll.setMaximumHeight(90)
        self._warnings_scroll.setWidget(
            self._warnings_label
        )

        warnings_layout.addWidget(
            self._warnings_scroll
        )

        layout.addWidget(self._warnings_group)

        # Optimizations are contextual: hide the whole panel when there is
        # nothing to suggest and show it again whenever a recalculation
        # produces at least one optimization.
        self._optimizations_group = _IconTitleGroupBox(
            self._translator.tr("plan.optimizations"),
            "plan-warning-orange.svg",
        )
        optimizations_layout = QVBoxLayout(
            self._optimizations_group
        )

        self._suggestions_label = QLabel()
        self._suggestions_label.setWordWrap(True)
        self._suggestions_label.setAlignment(
            Qt.AlignmentFlag.AlignTop
            | Qt.AlignmentFlag.AlignLeft
        )
        self._suggestions_label.setContentsMargins(4, 2, 4, 2)

        self._suggestions_scroll = QScrollArea()
        self._suggestions_scroll.setWidgetResizable(True)
        self._suggestions_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._suggestions_scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self._suggestions_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._suggestions_scroll.setMaximumHeight(90)
        self._suggestions_scroll.setWidget(
            self._suggestions_label
        )

        optimizations_layout.addWidget(
            self._suggestions_scroll
        )

        layout.addWidget(self._optimizations_group)

        structure_group = QGroupBox(
            self._translator.tr("plan.structure")
        )
        structure_layout = QVBoxLayout(
            structure_group
        )

        self._tree = QTreeWidget()
        self._tree.setMouseTracking(True)
        self._tree.itemEntered.connect(self._on_plan_item_entered)
        self._tree.viewport().setMouseTracking(True)
        self._tree.viewport().installEventFilter(self)
        self._tree.setHeaderLabels(
            [
                self._translator.tr("plan.section"),
                self._translator.tr("plan.pages"),
                self._translator.tr("plan.photos"),
                self._translator.tr("photos.column.actions"),
                self._translator.tr("plan.model"),
                self._translator.tr("plan.observations"),
            ]
        )

        header = self._tree.header()
        header.setStretchLastSection(False)

        # Every column remains user-resizable.  Initial widths only provide a
        # sensible starting layout; the user can then adapt the Plan to the
        # information that matters for the current album.
        for column in range(self._tree.columnCount()):
            header.setSectionResizeMode(
                column,
                QHeaderView.ResizeMode.Interactive,
            )

        for column, width in enumerate((500, 70, 70, 86, 260, 300)):
            self._tree.setColumnWidth(column, width)


        structure_layout.addWidget(self._tree)

        layout.addWidget(structure_group, 1)

    def clear(self) -> None:
        self._cancel_page_preview()
        self._summary_label.setText(
            self._translator.tr("plan.no_plan")
        )
        self._warnings_label.clear()
        self._warnings_group.setVisible(False)
        self._suggestions_label.clear()
        self._optimizations_group.setVisible(False)
        self._reset_tree()

    def set_result(
        self,
        result: AlbumBuildResult,
        settings: AlbumStructureSettings | None = None,
    ) -> None:
        self._result = result
        self._settings = settings
        summary = self._summary_builder.build(result)
        self._caption_overflows = self._collect_caption_overflows(result, settings)

        self._summary_label.setText(
            " | ".join(
                [
                    (
                        f"{self._translator.tr('plan.photos')}: "
                        f"{summary.photo_count}"
                    ),
                    (
                        f"{self._translator.tr('plan.pages')}: "
                        f"{summary.total_pages}"
                    ),
                    (
                        f"{self._translator.tr('plan.photo_pages')}: "
                        f"{summary.photo_pages}"
                    ),
                    (
                        f"{self._translator.tr('plan.dividers')}: "
                        f"{summary.divider_pages}"
                    ),
                    (
                        f"{self._translator.tr('plan.special_pages')}: "
                        f"{summary.special_pages}"
                    ),
                    (
                        f"{self._translator.tr('plan.technical_blanks')}: "
                        f"{summary.technical_blank_pages}"
                    ),
                    (
                        f"{self._translator.tr('plan.editorial_blanks')}: "
                        f"{summary.editorial_blank_pages}"
                    ),
                ]
            )
        )

        self._set_suggestions(
            summary,
            result=result,
            settings=settings,
        )
        self._set_structure(
            result,
            settings,
        )
        self._install_page_actions()

    def _install_page_actions(self) -> None:
        from photoalbum.album.settings import ContentAnchor
        if self._settings is None:
            return
        def install(item):
            # Keep the entire tree visually regular: covers, structural groups
            # (years/months/days), dividers and physical pages all use the same
            # row height as rows containing 24 px action buttons.
            item.setSizeHint(0, QSize(0, 26))
            page = item.data(0, Qt.ItemDataRole.UserRole)
            cover_value = item.data(0, _COVER_POSITION_ROLE)
            if page is not None or cover_value:
                cover_position = CoverPosition(cover_value) if cover_value else None
                self._install_preview_button(item, page=page, cover_position=cover_position)
            if page is not None:
                container = QWidget()
                row = QHBoxLayout(container)
                row.setContentsMargins(0, 0, 0, 0)
                row.setSpacing(2)
                row.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                self._register_action_hover(container, item)
                def button(key, icon_name, callback):
                    action = QToolButton()
                    action.setIcon(resource_icon(icon_name))
                    action.setIconSize(QSize(16, 16))
                    action.setFixedSize(24, 24)
                    action.setAutoRaise(True)
                    action.setToolTip(self._translator.tr(key))
                    action.setAccessibleName(self._translator.tr(key))
                    action.clicked.connect(callback)
                    row.addWidget(action)
                if page.kind == PlanItemKind.PHOTO_GROUP and page.photos:
                    button("plan.modify", "plan-edit.svg", lambda _=False, p=page: self._edit_photo_page(p))
                    anchor = ContentAnchor("photo", photo_identity=page.photos[-1].identity)
                    button("plan.insert_special", "plan-add-special.svg", lambda _=False, a=anchor, p=page: self._insert_page(a, p))
                elif page.kind in (PlanItemKind.YEAR_DIVIDER, PlanItemKind.MONTH_DIVIDER, PlanItemKind.DAY_DIVIDER):
                    anchor = ContentAnchor(page.kind.value, year=page.year, month=page.month, day=page.day)
                    button("plan.insert_special", "plan-add-special.svg", lambda _=False, a=anchor, p=page: self._insert_page(a, p))
                elif page.kind == PlanItemKind.BODY_SPECIAL_PAGE:
                    self._insertion_buttons(row, page.page_instance.instance_id, page)
                self._tree.setItemWidget(item, 3, container)
                item.setSizeHint(0, QSize(0, 26))
            for index in range(item.childCount()):
                install(item.child(index))
        for index in range(self._tree.topLevelItemCount()):
            install(self._tree.topLevelItem(index))
        effective_ids = {page.page_instance.instance_id for page in self._result.pagination.pages if page.page_instance}
        for insertion in self._settings.body_insertions:
            if insertion.page.instance_id in effective_ids:
                continue
            state = "plan.disabled" if not insertion.enabled else "plan.dormant"
            item = QTreeWidgetItem([self._template_name(insertion.page.template_id), "—", "—", "", "", self._translator.tr(state)])
            for column in range(6):
                item.setForeground(column, QColor("#777777"))
            self._tree.addTopLevelItem(item)
            container = QWidget()
            row = QHBoxLayout(container)
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(2)
            row.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            self._register_action_hover(container, item)
            self._insertion_buttons(row, insertion.page.instance_id, None)
            self._tree.setItemWidget(item, 3, container)
            item.setSizeHint(0, QSize(0, 26))

    def _install_preview_button(
        self,
        item: QTreeWidgetItem,
        *,
        page=None,
        cover_position: CoverPosition | None = None,
    ) -> None:
        container = QWidget()
        row = QHBoxLayout(container)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)
        row.setAlignment(Qt.AlignmentFlag.AlignCenter)

        icon = QLabel()
        icon.setPixmap(resource_icon("plan-page-preview.svg").pixmap(QSize(16, 16)))
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setFixedSize(22, 22)
        icon.setToolTip(self._translator.tr("plan.page_preview"))
        icon.setAccessibleName(self._translator.tr("plan.page_preview"))
        icon.installEventFilter(self)
        row.addWidget(icon)

        self._preview_hover_items[icon] = (item, page, cover_position)
        self._tree.setItemWidget(item, 1, container)
        item.setText(1, "")

    def _schedule_page_preview(
        self,
        button: QWidget,
        item: QTreeWidgetItem,
        page,
        cover_position: CoverPosition | None,
    ) -> None:
        self._cancel_page_preview()
        if self._preview_widget is None or self._settings is None:
            return
        anchor = button.mapToGlobal(QPoint(button.width(), button.height() // 2))
        self._pending_page_preview = (item, page, cover_position, anchor)
        self._page_preview_timer.start()

    def _show_pending_page_preview(self) -> None:
        pending = self._pending_page_preview
        self._pending_page_preview = None
        if pending is None or self._preview_widget is None or self._settings is None:
            return
        item, page, cover_position, anchor = pending
        if not isValid(item):
            return

        popup = QFrame(None, Qt.WindowType.ToolTip)
        popup.setFrameShape(QFrame.Shape.Box)
        layout = QVBoxLayout(popup)
        layout.setContentsMargins(5, 5, 5, 5)

        try:
            if cover_position is not None:
                preview = self._preview_widget.create_cover_preview(
                    self._settings,
                    cover_position,
                    page_width=_PAGE_PREVIEW_WIDTH,
                    parent=popup,
                )
            else:
                preview = self._preview_widget.create_page_preview(
                    page,
                    self._settings,
                    page_width=_PAGE_PREVIEW_WIDTH,
                    parent=popup,
                    prioritize_images=True,
                )
        except Exception:
            popup.deleteLater()
            return

        layout.addWidget(preview)
        popup.adjustSize()

        screen = QGuiApplication.screenAt(anchor) or QGuiApplication.primaryScreen()
        x = anchor.x() + 12
        y = anchor.y() - popup.height() // 2
        if screen is not None:
            area = screen.availableGeometry()
            if x + popup.width() > area.right():
                x = anchor.x() - popup.width() - 12
            x = max(area.left(), min(x, area.right() - popup.width() + 1))
            y = max(area.top(), min(y, area.bottom() - popup.height() + 1))
        popup.move(x, y)
        popup.show()
        self._page_preview_popup = popup

    def _cancel_page_preview(self) -> None:
        if hasattr(self, "_page_preview_timer"):
            self._page_preview_timer.stop()
        self._pending_page_preview = None
        popup = getattr(self, "_page_preview_popup", None)
        if popup is not None:
            popup.close()
            popup.deleteLater()
            self._page_preview_popup = None

    def _register_action_hover(self, container: QWidget, item: QTreeWidgetItem) -> None:
        self._action_hover_items[container] = item
        container.setMouseTracking(True)
        container.installEventFilter(self)

    def _on_plan_item_entered(self, item: QTreeWidgetItem, _column: int) -> None:
        self._set_hovered_plan_item(item)

    def _reset_tree(self) -> None:
        # Rebuilding the tree destroys the underlying C++ QTreeWidgetItem
        # objects.  Never retain hover/action references across that boundary.
        hovered = self._hovered_plan_item
        self._hovered_plan_item = None
        if hovered is not None and isValid(hovered):
            for column in range(self._tree.columnCount()):
                hovered.setBackground(column, QBrush())
        self._action_hover_items.clear()
        self._preview_hover_items.clear()
        self._cancel_page_preview()
        self._tree.clear()

    def _set_hovered_plan_item(self, item: QTreeWidgetItem | None) -> None:
        if item is not None and not isValid(item):
            item = None
        if item is self._hovered_plan_item:
            return
        previous = self._hovered_plan_item
        self._hovered_plan_item = item
        if previous is not None and isValid(previous):
            for column in range(self._tree.columnCount()):
                previous.setBackground(column, QBrush())
        if item is not None:
            background = QBrush(QColor("#eeeeee"))
            for column in range(self._tree.columnCount()):
                item.setBackground(column, background)

    def eventFilter(self, watched, event):
        if watched in self._preview_hover_items:
            item, page, cover_position = self._preview_hover_items.get(watched, (None, None, None))
            if event.type() == QEvent.Type.Enter:
                if item is not None and isValid(item):
                    self._set_hovered_plan_item(item)
                    self._schedule_page_preview(watched, item, page, cover_position)
            elif event.type() == QEvent.Type.Leave:
                self._cancel_page_preview()
                self._set_hovered_plan_item(None)
        elif watched is self._tree.viewport():
            if event.type() == QEvent.Type.MouseMove:
                self._set_hovered_plan_item(self._tree.itemAt(event.position().toPoint()))
            elif event.type() == QEvent.Type.Leave:
                self._set_hovered_plan_item(None)
        elif watched in self._action_hover_items:
            if event.type() == QEvent.Type.Enter:
                item = self._action_hover_items.get(watched)
                self._set_hovered_plan_item(item if item is not None and isValid(item) else None)
            elif event.type() == QEvent.Type.Leave:
                self._set_hovered_plan_item(None)
        return super().eventFilter(watched, event)

    def _insertion_buttons(self, row, instance_id, page):
        insertion = next(item for item in self._settings.body_insertions if item.page.instance_id == instance_id)
        for key, icon_name, callback in (
            ("plan.modify", "plan-edit.svg", lambda: self._edit_insertion(insertion, page)),
            (("plan.disable" if insertion.enabled else "plan.enable"),
             ("plan-disable.svg" if insertion.enabled else "plan-enable.svg"),
             lambda: self._replace_insertion(insertion, replace(insertion, enabled=not insertion.enabled))),
            ("sources.delete", "plan-delete.svg", lambda: self._replace_insertion(insertion, None)),
        ):
            action = QToolButton()
            action.setIcon(resource_icon(icon_name))
            action.setIconSize(QSize(16, 16))
            action.setFixedSize(24, 24)
            action.setAutoRaise(True)
            action.setToolTip(self._translator.tr(key))
            action.setAccessibleName(self._translator.tr(key))
            action.clicked.connect(lambda _=False, cb=callback: cb())
            row.addWidget(action)

    def _replace_insertion(self, insertion, replacement, pack_settings=None):
        items = [replacement if item.page.instance_id == insertion.page.instance_id else item
                 for item in self._settings.body_insertions]
        self.settings_changed.emit(replace(self._settings,
            body_insertions=[item for item in items if item is not None],
            template_pack_settings=pack_settings if pack_settings is not None else self._settings.template_pack_settings))

    def _edit_insertion(self, insertion, page):
        from photoalbum.gui.plan_page_editor import choose_page
        chosen = choose_page(self, self._registry, self._settings, self._result, self._translator,
                             page=page, instance=insertion.page)
        if chosen is not None:
            _, instance, pack_settings = chosen
            self._replace_insertion(insertion, replace(insertion, page=instance), pack_settings)

    def _insert_page(self, anchor, page):
        from photoalbum.album.settings import BodyPageInsertion
        from photoalbum.gui.plan_page_editor import choose_page
        chosen = choose_page(self, self._registry, self._settings, self._result, self._translator, page=page)
        if chosen is not None:
            _, instance, pack_settings = chosen
            self.settings_changed.emit(replace(self._settings,
                body_insertions=[*self._settings.body_insertions, BodyPageInsertion(anchor, instance)],
                template_pack_settings=pack_settings))

    def _edit_photo_page(self, page):
        from photoalbum.album.settings import PhotoPageOverride
        from photoalbum.gui.plan_page_editor import choose_page
        existing = next((item for item in self._settings.photo_page_overrides
                         if item.photo_identity == page.photos[0].identity), None)
        chosen = choose_page(self, self._registry, self._settings, self._result, self._translator,
                             page=page,
                             instance=existing.page if existing else page.page_instance,
                             photo_override=True)
        if chosen is not None:
            identity, instance, pack_settings = chosen
            overrides = [item for item in self._settings.photo_page_overrides if item.photo_identity != identity]
            if instance is not None:
                overrides.append(PhotoPageOverride(identity, instance))
            self.settings_changed.emit(replace(self._settings, photo_page_overrides=overrides,
                                               template_pack_settings=pack_settings))

    def _set_suggestions(
        self,
        summary,
        *,
        result: AlbumBuildResult | None = None,
        settings: AlbumStructureSettings | None = None,
    ) -> None:
        warning_lines = []

        if (
            summary.print_page_multiple is not None
            and not summary.print_compatible
        ):
            warning_lines.append(
                self._translator.tr(
                    (
                        "plan.print_incompatible_one"
                        if summary.print_pages_to_add == 1
                        else "plan.print_incompatible_many"
                    ),
                    pages=summary.total_pages,
                    multiple=summary.print_page_multiple,
                    additional=summary.print_pages_to_add,
                )
            )

        for page in result.excluded_photo_overrides:
            warning_lines.append(self._translator.tr("plan.override_incompatible", template=self._template_name(page.template_id)))
        for page in result.excluded_special_pages:
            warning_lines.append(self._translator.tr(
                "plan.special_page_excluded",
                template=(template_display_name(self._registry.get(page.template_id), self._translator)
                          if self._registry is not None else page.template_id),
            ))

        warning_lines.extend(
            self._caption_warning_lines(
                result,
                settings,
            )
        )

        self._warnings_label.setText(
            "\n".join(warning_lines)
        )
        self._warnings_group.setVisible(
            bool(warning_lines)
        )

        optimization_lines = []

        for suggestion in summary.period_fill_suggestions:
            slots = suggestion.available_photo_slots
            count_key = "one" if slots == 1 else "many"

            if suggestion.scope == "day":
                month_name = self._translator.month_name(suggestion.month)
                optimization_lines.append(
                    self._translator.tr(
                        f"plan.suggestion_day_{count_key}",
                        day=suggestion.day,
                        month=month_name,
                        year=suggestion.year,
                        slots=slots,
                    )
                )
            elif suggestion.scope == "year":
                optimization_lines.append(
                    self._translator.tr(
                        f"plan.suggestion_year_{count_key}",
                        year=suggestion.year,
                        slots=slots,
                    )
                )
            elif suggestion.scope == "album":
                optimization_lines.append(
                    self._translator.tr(
                        f"plan.suggestion_album_{count_key}",
                        slots=slots,
                    )
                )
            else:
                month_name = self._translator.month_name(suggestion.month)
                if month_name:
                    month_name = month_name[0].upper() + month_name[1:]
                optimization_lines.append(
                    self._translator.tr(
                        f"plan.suggestion_{count_key}",
                        month=month_name,
                        year=suggestion.year,
                        slots=slots,
                    )
                )

        self._suggestions_label.setText(
            "\n".join(optimization_lines)
        )
        self._optimizations_group.setVisible(
            bool(optimization_lines)
        )

    def _collect_caption_overflows(self, result, settings):
        if result is None or settings is None:
            return {}
        page_format = settings.effective_page_format()
        width_mm = page_format.width_mm
        height_mm = page_format.height_mm
        composer = PageComposer()
        pages = tuple(result.pagination.pages)
        found = {}
        for page in pages:
            if page.kind != PlanItemKind.PHOTO_GROUP or not page.template_id:
                continue
            try:
                reserve = composer.spread_caption_lines(
                    page, pages, settings.photo_pages,
                    page_width_mm=width_mm, page_height_mm=height_mm,
                )
                composition = composer.compose(
                    page, settings.photo_pages, settings.page_numbers,
                    page_width_mm=width_mm, page_height_mm=height_mm,
                    reserved_caption_lines=reserve,
                )
            except KeyError:
                continue
            for index, slot in enumerate(composition.photo_slots[:len(page.photos)]):
                if slot.caption_overflow:
                    found.setdefault(page.number, []).append((
                        page.photos[index].filename,
                        slot.required_caption_lines,
                        slot.max_caption_lines,
                    ))
        return found

    def _caption_warning_lines(self, result, settings) -> list[str]:
        # An empty result is a completed diagnostic, not a cache miss.
        diagnostics = self._caption_overflows
        return [
            self._translator.tr(
                "plan.caption_overflow", page=page_number, photo=photo,
                required=required, available=available,
            )
            for page_number in sorted(diagnostics)
            for photo, required, available in diagnostics[page_number]
        ]

    def _set_basic_structure(
        self,
        result: AlbumBuildResult,
    ) -> None:
        self._reset_tree()
        self._append_chronological_pages(
            list(result.pagination.pages),
            root=None,
        )

        self._update_group_totals()
        self._tree.collapseAll()

    def _append_chronological_pages(
        self,
        pages: list,
        *,
        root: QTreeWidgetItem | None,
        group_days: bool = False,
    ) -> None:
        """Append physical pages without letting grouping reorder them."""
        previous_scoped = []
        previous = None

        for page in pages:
            previous_scoped.append(previous)
            if page.year is not None:
                previous = page

        next_scoped = [None] * len(pages)
        following = None

        for index in range(len(pages) - 1, -1, -1):
            next_scoped[index] = following
            if pages[index].year is not None:
                following = pages[index]

        scopes: list[tuple[int | None, int | None]] = []

        for index, page in enumerate(pages):
            year = page.year
            month = page.month

            if year is None:
                before = previous_scoped[index]
                after = next_scoped[index]

                if (
                    before is not None
                    and after is not None
                    and before.year == after.year
                ):
                    year = before.year

                    if (
                        before.month is not None
                        and before.month == after.month
                    ):
                        month = before.month

            scopes.append((year, month))

        current_year = None
        current_month = None
        year_item = None
        month_item = None
        current_day = None
        day_item = None

        def append(parent, item) -> None:
            if parent is None:
                self._tree.addTopLevelItem(item)
            else:
                parent.addChild(item)

        for page, (year, month) in zip(pages, scopes):
            if year is None:
                append(root, self._page_item(page))
                current_year = None
                current_month = None
                year_item = None
                month_item = None
                day_item = None
                continue

            if year_item is None or current_year != year:
                year_item = QTreeWidgetItem(
                    [str(year), "", "", "", "", ""]
                )
                append(root, year_item)
                current_year = year
                current_month = None
                month_item = None
                day_item = None

            if month is None:
                year_item.addChild(self._page_item(page))
                current_month = None
                month_item = None
                day_item = None
                continue

            if month_item is None or current_month != month:
                month_name = self._translator.month_name(month)
                if month_name:
                    month_name = month_name[0].upper() + month_name[1:]
                month_item = QTreeWidgetItem(
                    [month_name, "", "", "", "", ""]
                )
                year_item.addChild(month_item)
                current_month = month
                day_item = None

            if not group_days or page.day is None:
                month_item.addChild(self._page_item(page))
                day_item = None
                continue

            if day_item is None or current_day != page.day:
                weekday = QLocale(self._translator.language).dayName(
                    QDate(year, month, page.day).dayOfWeek()
                )
                day_item = QTreeWidgetItem(
                    [f"{page.day}  {weekday.capitalize()}", "", "", "", "", ""]
                )
                month_item.addChild(day_item)
                current_day = page.day

            day_item.addChild(self._page_item(page))

    def _set_structure(
        self,
        result: AlbumBuildResult,
        settings: AlbumStructureSettings | None = None,
    ) -> None:
        # Without AlbumStructureSettings we cannot know where
        # covers/front matter/back matter belong. Preserve the
        # historical year/month tree in that case. This also
        # keeps AlbumPlanWidget usable independently.
        if settings is None:
            self._set_basic_structure(
                result
            )
            return

        self._reset_tree()

        pages = list(
            result.pagination.pages
        )

        # ----------------------------------------------------
        # Covers
        # ----------------------------------------------------

        if settings is not None:
            self._tree.addTopLevelItem(
                self._cover_item(
                    settings,
                    CoverPosition.FRONT,
                    "album.front_cover",
                )
            )

            self._tree.addTopLevelItem(
                self._cover_item(
                    settings,
                    CoverPosition.INSIDE_FRONT,
                    "album.inside_front_cover",
                )
            )

        # ----------------------------------------------------
        # Determine which special pages belong before/after
        # the album body.
        #
        # Prefer PageInstance IDs. The page-number fallback
        # also keeps this robust during development.
        # ----------------------------------------------------

        front_ids: set[str] = set()
        back_ids: set[str] = set()

        front_count = 0
        back_count = 0

        if settings is not None:
            front_count = len(
                settings.front_matter
            )
            back_count = len(
                settings.back_matter
            )

            front_ids = {
                page.instance_id
                for page in settings.front_matter
            }

            back_ids = {
                page.instance_id
                for page in settings.back_matter
            }

        front_fallback_numbers = {
            page.number
            for page in pages[:front_count]
        }

        back_fallback_numbers = (
            {
                page.number
                for page in pages[
                    len(pages) - back_count:
                ]
            }
            if back_count
            else set()
        )

        front_pages = []
        back_pages = []
        body_pages = []

        for page in pages:
            instance_id = None

            if page.page_instance is not None:
                instance_id = (
                    page.page_instance.instance_id
                )

            if (
                page.kind == PlanItemKind.SPECIAL_PAGE
                and (
                    instance_id in front_ids
                    or (
                        instance_id is None
                        and page.number
                        in front_fallback_numbers
                    )
                )
            ):
                front_pages.append(
                    page
                )
                continue

            if (
                page.kind == PlanItemKind.SPECIAL_PAGE
                and (
                    instance_id in back_ids
                    or (
                        instance_id is None
                        and page.number
                        in back_fallback_numbers
                    )
                )
            ):
                back_pages.append(
                    page
                )
                continue

            body_pages.append(
                page
            )

        # ----------------------------------------------------
        # Pages immediately after inside-front cover
        # ----------------------------------------------------

        if front_pages:
            front_root = QTreeWidgetItem(
                [
                    self._translator.tr(
                        "album.front_matter"
                    ),
                    "",
                    "",
                    "",
                    "",
                    "",
                ]
            )

            self._tree.addTopLevelItem(
                front_root
            )

            for page in front_pages:
                front_root.addChild(
                    self._page_item(
                        page
                    )
                )

        # ----------------------------------------------------
        # Main album body
        # ----------------------------------------------------

        body_root = QTreeWidgetItem(
            [
                self._translator.tr(
                    "plan.album_body"
                ),
                "",
                "",
                "",
            ]
        )

        self._append_chronological_pages(
            body_pages,
            root=body_root,
            group_days=settings.day_dividers.enabled,
        )

        if body_pages:
            self._tree.addTopLevelItem(
                body_root
            )

        # ----------------------------------------------------
        # Pages immediately before inside-back cover
        # ----------------------------------------------------

        if back_pages:
            back_root = QTreeWidgetItem(
                [
                    self._translator.tr(
                        "album.back_matter"
                    ),
                    "",
                    "",
                    "",
                    "",
                    "",
                ]
            )

            self._tree.addTopLevelItem(
                back_root
            )

            for page in back_pages:
                back_root.addChild(
                    self._page_item(
                        page
                    )
                )

        # ----------------------------------------------------
        # Back covers
        # ----------------------------------------------------

        if settings is not None:
            self._tree.addTopLevelItem(
                self._cover_item(
                    settings,
                    CoverPosition.INSIDE_BACK,
                    "album.inside_back_cover",
                )
            )

            self._tree.addTopLevelItem(
                self._cover_item(
                    settings,
                    CoverPosition.BACK,
                    "album.back_cover",
                )
            )

        self._update_group_totals()

        self._tree.expandAll()

    def _template_name(
        self,
        template_id: str,
    ) -> str:
        if self._registry is not None:
            try:
                template = self._registry.get(
                    template_id
                )
                return template_display_name(
                    template,
                    self._translator,
                )
            except KeyError:
                pass

        return template_id

    def _cover_item(
        self,
        settings: AlbumStructureSettings,
        position: CoverPosition,
        label_key: str,
    ) -> QTreeWidgetItem:
        cover = settings.covers[
            position
        ]

        item = QTreeWidgetItem(
            [
                self._translator.tr(
                    label_key
                ),
                "",
                "—",
                "",
                self._template_name(
                    cover.template_id
                ),
                "",
            ]
        )
        item.setData(0, _COVER_POSITION_ROLE, position.value)
        return item

    def _page_item(
        self,
        page,
    ) -> QTreeWidgetItem:
        if page.blank_reason is not None:
            if (
                page.blank_reason
                == BlankPageReason.TECHNICAL
            ):
                page_type = self._translator.tr("plan.technical_blank")
            else:
                page_type = self._translator.tr("plan.editorial_blank")

        elif page.kind == PlanItemKind.PHOTO_GROUP:
            page_type = self._translator.tr("plan.photos_page")

        elif page.kind == PlanItemKind.DAY_DIVIDER:
            page_type = self._translator.tr("plan.day_divider")

        elif page.kind == PlanItemKind.MONTH_DIVIDER:
            page_type = self._translator.tr("plan.month_divider")

        elif page.kind == PlanItemKind.YEAR_DIVIDER:
            page_type = self._translator.tr("plan.year_divider")

        elif page.kind in (PlanItemKind.SPECIAL_PAGE, PlanItemKind.BODY_SPECIAL_PAGE):
            page_type = self._translator.tr("plan.special_page")

        else:
            page_type = (
                page.kind.value
                if page.kind is not None
                else "Page"
            )

        photo_count = len(page.photos)
        model = ""
        if page.template_id:
            try:
                template = self._registry.get(page.template_id)
                model = template_display_name(template, self._translator)
            except KeyError:
                # Unknown external template: retain its stable ID
                # as a technical fallback.
                model = page.template_id

        observation_parts: list[str] = []
        editorial_detail_key = self._editorial_detail_key(page)
        if editorial_detail_key is not None:
            observation_parts.append(self._translator.tr(editorial_detail_key))

        if page.unused_photo_slots:
            unused_count = page.unused_photo_slots
            observation_parts.append(
                self._translator.tr(
                    "plan.unused_slot" if unused_count == 1 else "plan.unused_slots",
                    count=unused_count,
                )
            )

        overflows = self._caption_overflows.get(page.number, [])
        if overflows:
            observation_parts.append(
                self._translator.tr(
                    "plan.caption_too_long" if len(overflows) == 1 else "plan.captions_too_long"
                )
            )

        observations = " — ".join(observation_parts)
        item = QTreeWidgetItem([
            self._translator.tr("plan.page_label", number=page.number, type=page_type),
            "", str(photo_count), "", model, observations,
        ])
        item.setData(0, Qt.ItemDataRole.UserRole, page)
        item.setSizeHint(0, QSize(0, 26))

        # The model name is green only when an automatic photo-page choice was
        # manually overridden. Observations retain the semantic warning colours.
        if editorial_detail_key == "plan.custom_template":
            item.setForeground(4, QColor("#2e7d32"))

        if overflows:
            item.setForeground(5, QColor("#c62828"))
        elif page.unused_photo_slots:
            item.setForeground(5, QColor("#ef6c00"))
        elif editorial_detail_key is not None:
            item.setForeground(5, QColor("#2e7d32"))
        return item

    def _editorial_detail_key(self, page) -> str | None:
        if page.kind == PlanItemKind.BODY_SPECIAL_PAGE:
            return "plan.special_page"

        settings = getattr(self, "_settings", None)
        if (
            settings is None
            or not settings.photo_pages.is_automatic
            or page.kind != PlanItemKind.PHOTO_GROUP
            or not page.photos
        ):
            return None

        first_identity = page.photos[0].identity
        if any(
            override.photo_identity == first_identity
            for override in settings.photo_page_overrides
        ):
            return "plan.custom_template"
        return None

    def _update_group_totals(self) -> None:
        for index in range(
            self._tree.topLevelItemCount()
        ):
            self._update_item_totals(
                self._tree.topLevelItem(index)
            )

    def _update_item_totals(
        self,
        item: QTreeWidgetItem,
    ) -> tuple[int, int]:
        if item.childCount() == 0:
            if item.data(0, Qt.ItemDataRole.UserRole) is not None:
                pages = 1
            else:
                try:
                    pages = int(item.text(1))
                except ValueError:
                    pages = 0

            try:
                photos = int(item.text(2))
            except ValueError:
                photos = 0

            return pages, photos

        page_count = 0
        photo_count = 0

        for index in range(item.childCount()):
            pages, photos = self._update_item_totals(
                item.child(index)
            )

            page_count += pages
            photo_count += photos

        item.setText(1, str(page_count))
        item.setText(2, str(photo_count))

        return page_count, photo_count
