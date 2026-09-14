from __future__ import annotations

from dataclasses import dataclass

from photoalbum.models import Photo

from .pagination import PaginationEngine, PaginationResult
from .planning import AlbumPlan, AlbumPlanner
from .print_diagnostics import (
    PrintConstraints,
    PrintDiagnostic,
    PrintDiagnostics,
)
from .settings import AlbumStructureSettings
from .templates import TemplateRegistry
from .validation import AlbumSettingsValidator


@dataclass(frozen=True)
class AlbumBuildResult:
    plan: AlbumPlan
    pagination: PaginationResult
    print_diagnostic: PrintDiagnostic


class AlbumBuilder:
    def __init__(
        self,
        registry: TemplateRegistry,
    ) -> None:
        self._registry = registry

    def build(
        self,
        photos: list[Photo],
        settings: AlbumStructureSettings,
        *,
        print_constraints: PrintConstraints | None = None,
    ) -> AlbumBuildResult:
        AlbumSettingsValidator(
            self._registry
        ).validate(settings)

        plan = AlbumPlanner().plan(
            photos,
            settings,
        )

        pagination = PaginationEngine(
            self._registry
        ).paginate(
            plan,
            settings,
        )

        print_diagnostic = PrintDiagnostics().analyze(
            pagination,
            print_constraints,
        )

        return AlbumBuildResult(
            plan=plan,
            pagination=pagination,
            print_diagnostic=print_diagnostic,
        )

