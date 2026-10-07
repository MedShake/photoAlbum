from dataclasses import dataclass


@dataclass(frozen=True)
class SourceOperationResult:
    source_id: str
    status: str  # success, partial, cancelled, failed
    issue: str | None = None  # access, authentication, geocoding, metadata
    detail: str = ""
