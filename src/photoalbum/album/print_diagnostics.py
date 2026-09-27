from __future__ import annotations

from dataclasses import dataclass

from .pagination import PaginationResult


@dataclass(frozen=True)
class PrintConstraints:
    page_multiple: int | None = None

    def __post_init__(self) -> None:
        if (
            self.page_multiple is not None
            and self.page_multiple < 1
        ):
            raise ValueError(
                "page_multiple must be greater than zero."
            )


@dataclass(frozen=True)
class PrintDiagnostic:
    compatible: bool
    pages_to_add: int = 0
    page_multiple: int | None = None


class PrintDiagnostics:
    def analyze(
        self,
        pagination: PaginationResult,
        constraints: PrintConstraints | None,
    ) -> PrintDiagnostic:
        page_count = len(pagination.pages)

        if (
            constraints is None
            or constraints.page_multiple is None
        ):
            return PrintDiagnostic(
                compatible=True,
            )

        multiple = constraints.page_multiple
        remainder = page_count % multiple

        if remainder == 0:
            return PrintDiagnostic(
                compatible=True,
                page_multiple=multiple,
            )

        return PrintDiagnostic(
            compatible=False,
            pages_to_add=multiple - remainder,
            page_multiple=multiple,
        )

