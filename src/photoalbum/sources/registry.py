from __future__ import annotations

from collections.abc import Callable

from .base import PhotoSource


SourceFactory = Callable[..., PhotoSource]


class SourceProviderRegistry:
    """Small provider registry; no provider or GUI dependency leaks outward."""

    def __init__(self) -> None:
        self._factories: dict[str, SourceFactory] = {}

    def register(self, kind: str, factory: SourceFactory) -> None:
        if not kind or kind in self._factories:
            raise ValueError(f"Source provider already registered: {kind}")
        self._factories[kind] = factory

    def create(self, kind: str, **kwargs) -> PhotoSource:
        try:
            factory = self._factories[kind]
        except KeyError as exc:
            raise KeyError(f"Unknown source provider: {kind}") from exc
        return factory(**kwargs)

    @property
    def kinds(self) -> tuple[str, ...]:
        return tuple(sorted(self._factories))
