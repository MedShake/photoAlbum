"""Public authoring API for template packs.

These are re-exports of host primitives, not pack implementations. Importing this
module does not discover/activate packs or create widgets or preview services.
"""
from photoalbum.album import (
    A4, CoverPosition, PageFormat, PageInstance, PageNumberSettings,
    PageSide, PlannedPage, PlanItemKind, TemplateKind,
)
from photoalbum.album.composition import (
    HorizontalAlignment, ImageFit, NormalizedRect, PageComposer, PageComposition,
    PageNumberComposition, PhotoSlotComposition, TemplateLayout, TemplateLayoutRegistry,
    compose_page_number, fit_contained_rect,
)
from photoalbum.gui.template_settings import PageTemplateSettingsWidget
from photoalbum.models import Photo
from photoalbum.template_engine import (
    PageTemplateExtension, create_template_instance, register_template_extension,
    validate_template_instance,
)
from photoalbum.template_engine.preview_backend import PreviewJob, TemplatePreviewBackend

__all__ = [
    "A4", "CoverPosition", "HorizontalAlignment", "ImageFit", "NormalizedRect",
    "PageComposer", "PageComposition", "PageFormat", "PageInstance",
    "PageNumberComposition", "PageNumberSettings", "PageSide",
    "PageTemplateExtension", "PageTemplateSettingsWidget", "Photo", "PhotoSlotComposition",
    "PlannedPage", "PlanItemKind", "PreviewJob", "TemplateKind", "TemplateLayout",
    "TemplateLayoutRegistry", "TemplatePreviewBackend", "compose_page_number",
    "create_template_instance", "fit_contained_rect", "register_template_extension",
    "validate_template_instance",
]
