from __future__ import annotations

from photoalbum.i18n import Translator
from photoalbum.album.composition import PageComposer

from photoalbum.gui.template_labels import template_display_name

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QHeaderView,
    QGroupBox,
    QScrollArea,
    QLabel,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
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


class AlbumPlanWidget(QWidget):
    def __init__(
        self,
        registry: TemplateRegistry,
        translator: Translator | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self._registry = registry
        self._translator = translator or Translator()
        self._summary_builder = AlbumSummaryBuilder()
        self._caption_overflows = {}

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
        self._warnings_group = QGroupBox(
            self._translator.tr("plan.warnings")
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

        self._warnings_scroll = QScrollArea()
        self._warnings_scroll.setWidgetResizable(True)
        self._warnings_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._warnings_scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self._warnings_scroll.setMaximumHeight(90)
        self._warnings_scroll.setWidget(
            self._warnings_label
        )

        warnings_layout.addWidget(
            self._warnings_scroll
        )

        layout.addWidget(self._warnings_group)

        # Optimizations are useful information even when there is
        # currently nothing to optimize, so this panel always remains.
        self._optimizations_group = QGroupBox(
            self._translator.tr("plan.optimizations")
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

        self._suggestions_scroll = QScrollArea()
        self._suggestions_scroll.setWidgetResizable(True)
        self._suggestions_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._suggestions_scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
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
        self._tree.setHeaderLabels(
            [
                self._translator.tr("plan.section"),
                self._translator.tr("plan.pages"),
                self._translator.tr("plan.photos"),
                self._translator.tr("plan.details"),
            ]
        )

        header = self._tree.header()

        # La hiérarchie du document se trouve dans cette colonne.
        header.setSectionResizeMode(
            0,
            QHeaderView.ResizeMode.Stretch,
        )

        header.setSectionResizeMode(
            1,
            QHeaderView.ResizeMode.ResizeToContents,
        )

        header.setSectionResizeMode(
            2,
            QHeaderView.ResizeMode.ResizeToContents,
        )

        header.setSectionResizeMode(
            3,
            QHeaderView.ResizeMode.Interactive,
        )

        self._tree.setColumnWidth(
            3,
            240,
        )


        structure_layout.addWidget(self._tree)

        layout.addWidget(structure_group, 1)

    def clear(self) -> None:
        self._summary_label.setText(
            self._translator.tr("plan.no_plan")
        )
        self._warnings_label.clear()
        self._warnings_group.setVisible(False)
        self._suggestions_label.setText(
            self._translator.tr("plan.no_optimization")
        )
        self._tree.clear()

    def set_result(
        self,
        result: AlbumBuildResult,
        settings: AlbumStructureSettings | None = None,
    ) -> None:
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
            month_name = self._translator.month_name(
                suggestion.month
            )

            # A month starts the sentence here, so capitalize it even
            # in locales whose normal month names are lowercase.
            if month_name:
                month_name = (
                    month_name[0].upper()
                    + month_name[1:]
                )

            slots = suggestion.available_photo_slots

            optimization_lines.append(
                self._translator.tr(
                    (
                        "plan.suggestion_one"
                        if slots == 1
                        else "plan.suggestion_many"
                    ),
                    month=month_name,
                    year=suggestion.year,
                    slots=slots,
                )
            )

        if not optimization_lines:
            optimization_lines.append(
                self._translator.tr(
                    "plan.no_optimization"
                )
            )

        self._suggestions_label.setText(
            "\n".join(optimization_lines)
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
        self._tree.clear()

        year_items: dict[
            int,
            QTreeWidgetItem,
        ] = {}

        month_items: dict[
            tuple[int, int],
            QTreeWidgetItem,
        ] = {}

        other_root = QTreeWidgetItem(
            [
                self._translator.tr(
                    "plan.other_pages"
                ),
                "",
                "",
                "",
            ]
        )

        has_other_pages = False

        for page in result.pagination.pages:
            parent = None

            if page.year is not None:
                parent = year_items.get(
                    page.year
                )

                if parent is None:
                    parent = QTreeWidgetItem(
                        [
                            str(page.year),
                            "",
                            "",
                            "",
                        ]
                    )

                    self._tree.addTopLevelItem(
                        parent
                    )

                    year_items[
                        page.year
                    ] = parent

            if (
                page.year is not None
                and page.month is not None
            ):
                key = (
                    page.year,
                    page.month,
                )

                month_item = (
                    month_items.get(
                        key
                    )
                )

                if month_item is None:
                    month_name = (
                        self._translator.month_name(
                            page.month
                        )
                    )

                    if month_name:
                        month_name = (
                            month_name[0].upper()
                            + month_name[1:]
                        )

                    month_item = QTreeWidgetItem(
                        [
                            month_name,
                            "",
                            "",
                            "",
                        ]
                    )

                    assert parent is not None

                    parent.addChild(
                        month_item
                    )

                    month_items[
                        key
                    ] = month_item

                parent = month_item

            if parent is None:
                parent = other_root
                has_other_pages = True

            parent.addChild(
                self._page_item(
                    page
                )
            )

        if has_other_pages:
            self._tree.addTopLevelItem(
                other_root
            )

        self._update_group_totals()
        self._tree.collapseAll()

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

        self._tree.clear()

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

        year_items: dict[
            int,
            QTreeWidgetItem,
        ] = {}

        month_items: dict[
            tuple[int, int],
            QTreeWidgetItem,
        ] = {}

        other_body_root = QTreeWidgetItem(
            [
                self._translator.tr(
                    "plan.other_pages"
                ),
                "",
                "",
                "",
            ]
        )

        has_body = False
        has_other_body = False

        for page in body_pages:
            has_body = True

            parent: QTreeWidgetItem | None = None

            if page.year is not None:
                parent = year_items.get(
                    page.year
                )

                if parent is None:
                    parent = QTreeWidgetItem(
                        [
                            str(page.year),
                            "",
                            "",
                            "",
                        ]
                    )

                    body_root.addChild(
                        parent
                    )

                    year_items[
                        page.year
                    ] = parent

            if (
                page.year is not None
                and page.month is not None
            ):
                key = (
                    page.year,
                    page.month,
                )

                month_item = (
                    month_items.get(
                        key
                    )
                )

                if month_item is None:
                    month_name = (
                        self._translator.month_name(
                            page.month
                        )
                    )

                    # Month separators use a capitalized month
                    # name in the rest of the application.
                    if month_name:
                        month_name = (
                            month_name[0].upper()
                            + month_name[1:]
                        )

                    month_item = QTreeWidgetItem(
                        [
                            month_name,
                            "",
                            "",
                            "",
                        ]
                    )

                    assert parent is not None

                    parent.addChild(
                        month_item
                    )

                    month_items[
                        key
                    ] = month_item

                parent = month_item

            if parent is None:
                parent = other_body_root
                has_other_body = True

            parent.addChild(
                self._page_item(
                    page
                )
            )

        if has_other_body:
            body_root.addChild(
                other_body_root
            )

        if has_body:
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

        return QTreeWidgetItem(
            [
                self._translator.tr(
                    label_key
                ),
                "—",
                "—",
                self._template_name(
                    cover.template_id
                ),
            ]
        )

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

        elif page.kind == PlanItemKind.MONTH_DIVIDER:
            page_type = self._translator.tr("plan.month_divider")

        elif page.kind == PlanItemKind.YEAR_DIVIDER:
            page_type = self._translator.tr("plan.year_divider")

        elif page.kind == PlanItemKind.SPECIAL_PAGE:
            page_type = self._translator.tr("plan.special_page")

        else:
            page_type = (
                page.kind.value
                if page.kind is not None
                else "Page"
            )

        photo_count = len(page.photos)

        details = ""

        if page.template_id:
            try:
                template = self._registry.get(
                    page.template_id
                )

                details = template_display_name(
                    template,
                    self._translator,
                )
            except KeyError:
                # Unknown external template: retain its stable ID
                # as a technical fallback.
                details = page.template_id

        if page.unused_photo_slots:
            unused_count = page.unused_photo_slots
            unused_slots = self._translator.tr(
                (
                    "plan.unused_slot"
                    if unused_count == 1
                    else "plan.unused_slots"
                ),
                count=unused_count,
            )

            details = (
                f"{details} — {unused_slots}"
            )

        overflows = self._caption_overflows.get(page.number, [])
        if overflows:
            overflow_details = self._translator.tr(
                (
                    "plan.caption_too_long"
                    if len(overflows) == 1
                    else "plan.captions_too_long"
                )
            )
            details = (
                f"{details} — {overflow_details}"
                if details
                else overflow_details
            )

        item = QTreeWidgetItem([
            self._translator.tr("plan.page_label", number=page.number, type=page_type),
            "1", str(photo_count), details,
        ])
        if overflows:
            item.setForeground(3, QColor("#c62828"))
        elif page.unused_photo_slots:
            item.setForeground(3, QColor("#ef6c00"))
        return item

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
