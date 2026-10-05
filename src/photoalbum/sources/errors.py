from __future__ import annotations


class SourceReconnectRequiredError(RuntimeError):
    """Raised when a remote photo source must be reconnected to fetch an asset."""

    def __init__(
        self,
        *,
        filename: str,
        source_id: str | None = None,
        operation: str = "retrieve",
    ) -> None:
        self.filename = filename
        self.source_id = source_id
        self.operation = operation
        super().__init__(filename)
