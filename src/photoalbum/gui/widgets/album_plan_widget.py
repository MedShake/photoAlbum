from __future__ import annotations

from photoalbum.i18n import Translator
from photoalbum.gui.template_labels import template_display_name

from PySide6.QtWidgets import (
    QGroupBox,
    QLabel,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from photoalbum.album import (
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

        self._print_label = QLabel()
        self._print_label.setWordWrap(True)

        summary_layout.addWidget(self._summary_label)
        summary_layout.addWidget(self._print_label)

        layout.addWidget(summary_group)

        suggestions_group = QGroupBox(
            self._translator.tr("plan.optimizations")
        )
        suggestions_layout = QVBoxLayout(
            suggestions_group
        )

        self._suggestions_label = QLabel()
        self._suggestions_label.setWordWrap(True)

        suggestions_layout.addWidget(
            self._suggestions_label
        )

        layout.addWidget(suggestions_group)

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

        structure_layout.addWidget(self._tree)

        layout.addWidget(structure_group, 1)

    def clear(self) -> None:
        self._summary_label.setText(
            self._translator.tr("plan.no_plan")
        )
        self._print_label.clear()
        self._suggestions_label.setText(
            self._translator.tr("plan.no_optimization")
        )
        self._tree.clear()

    def set_result(
        self,
        result: AlbumBuildResult,
    ) -> None:
        summary = self._summary_builder.build(result)

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

        if summary.print_page_multiple is None:
            self._print_label.setText(
                self._translator.tr(
                    "plan.print_disabled"
                )
            )

        elif summary.print_compatible:
            self._print_label.setText(
                self._translator.tr(
                    "plan.print_compatible",
                    pages=summary.total_pages,
                    multiple=summary.print_page_multiple,
                )
            )

        else:
            self._print_label.setText(
                self._translator.tr(
                    "plan.print_incompatible",
                    pages=summary.total_pages,
                    multiple=summary.print_page_multiple,
                    additional=summary.print_pages_to_add,
                )
            )

        self._set_suggestions(summary)
        self._set_structure(result)

    def _set_suggestions(self, summary) -> None:
        suggestions = summary.period_fill_suggestions

        if not suggestions:
            self._suggestions_label.setText(
                self._translator.tr(
                    "plan.no_unused_capacity"
                )
            )
            return

        lines = []

        for suggestion in suggestions:
            month_name = self._translator.month_name(
                suggestion.month
            )

            slots = suggestion.available_photo_slots

            lines.append(
                self._translator.tr(
                    "plan.suggestion",
                    month=month_name,
                    year=suggestion.year,
                    slots=slots,
                )
            )

        self._suggestions_label.setText(
            "\n".join(lines)
        )

    def _set_structure(
        self,
        result: AlbumBuildResult,
    ) -> None:
        self._tree.clear()

        year_items: dict[int, QTreeWidgetItem] = {}
        month_items: dict[
            tuple[int, int],
            QTreeWidgetItem,
        ] = {}

        other_root = QTreeWidgetItem(
            [
                self._translator.tr("plan.other_pages"),
                "",
                "",
                "",
            ]
        )

        has_other_pages = False

        for page in result.pagination.pages:
            parent = None

            if page.year is not None:
                parent = year_items.get(page.year)

                if parent is None:
                    parent = QTreeWidgetItem(
                        [
                            str(page.year),
                            "",
                            "",
                            "",
                        ]
                    )

                    self._tree.addTopLevelItem(parent)
                    year_items[page.year] = parent

            if (
                page.year is not None
                and page.month is not None
            ):
                key = (page.year, page.month)

                month_item = month_items.get(key)

                if month_item is None:
                    month_item = QTreeWidgetItem(
                        [
                            self._translator.month_name(
                                page.month
                            ),
                            "",
                            "",
                            "",
                        ]
                    )

                    parent.addChild(month_item)
                    month_items[key] = month_item

                parent = month_item

            if parent is None:
                parent = other_root
                has_other_pages = True

            parent.addChild(
                self._page_item(page)
            )

        if has_other_pages:
            self._tree.addTopLevelItem(other_root)

        self._update_group_totals()

        self._tree.collapseAll()

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
            unused_slots = self._translator.tr(
                "plan.unused_slots",
                count=page.unused_photo_slots,
            )

            details = (
                f"{details} — {unused_slots}"
            )

        return QTreeWidgetItem(
            [
                self._translator.tr(
                    "plan.page_label",
                    number=page.number,
                    type=page_type,
                ),
                "1",
                str(photo_count),
                details,
            ]
        )

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

