from __future__ import annotations

from photoalbum.template_engine import (
    PageTemplateExtension,
    register_template_extension,
)

from .settings import (
    SimplexFullPhotoCoverSettingsWidget,
)
from .widget_renderer import renderer


TEMPLATE_ID = "simplex-full-photo-cover"


def register() -> None:
    """
    Register the executable behaviour owned by the Simplex
    full-page photo cover.
    """
    register_template_extension(
        PageTemplateExtension(
            template_id=TEMPLATE_ID,
            settings_editor_type=(
                SimplexFullPhotoCoverSettingsWidget
            ),
            widget_renderer=renderer,
        )
    )
