"""Application policy and pack-declared initial album roles."""
from dataclasses import dataclass

DEFAULT_TEMPLATE_PACK = "msb"


@dataclass(frozen=True)
class AlbumTemplateDefaults:
    front_cover: str
    inside_front_cover: str
    inside_back_cover: str
    back_cover: str
    photo_page: str
    year_divider: str
    month_divider: str
    day_divider: str


def default_template_choices(registry) -> AlbumTemplateDefaults:
    choices = registry.pack_defaults.get(DEFAULT_TEMPLATE_PACK)
    if choices is None:
        raise ValueError(f"Default template pack {DEFAULT_TEMPLATE_PACK!r} is missing.")
    try:
        return AlbumTemplateDefaults(**choices)
    except TypeError as exc:
        raise ValueError(
            f"Default template pack {DEFAULT_TEMPLATE_PACK!r} must declare all album roles."
        ) from exc
