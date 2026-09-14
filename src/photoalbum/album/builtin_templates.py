from __future__ import annotations

from .templates import (
    TemplateDefinition,
    TemplateKind,
    TemplateRegistry,
)


def create_builtin_template_registry() -> TemplateRegistry:
    templates = [
        # Covers / reusable special pages
        TemplateDefinition(
            template_id="year-photo-scatter",
            name="Year photo scatter",
            allowed_kinds=frozenset(
                {
                    TemplateKind.COVER,
                    TemplateKind.SPECIAL_PAGE,
                }
            ),
        ),
        TemplateDefinition(
            template_id="geographic-word-cloud",
            name="Geographic word cloud",
            allowed_kinds=frozenset(
                {
                    TemplateKind.COVER,
                    TemplateKind.SPECIAL_PAGE,
                }
            ),
        ),
        TemplateDefinition(
            template_id="calendar-index",
            name="Calendar index",
            allowed_kinds=frozenset(
                {
                    TemplateKind.COVER,
                    TemplateKind.SPECIAL_PAGE,
                }
            ),
        ),

        # Dividers
        TemplateDefinition(
            template_id="year-divider-classic",
            name="Classic year divider",
            allowed_kinds=frozenset(
                {
                    TemplateKind.YEAR_DIVIDER,
                }
            ),
        ),
        TemplateDefinition(
            template_id="month-divider-classic",
            name="Classic month divider",
            allowed_kinds=frozenset(
                {
                    TemplateKind.MONTH_DIVIDER,
                }
            ),
        ),

        # Photo pages
        TemplateDefinition(
            template_id="photo-page-1",
            name="One photo",
            allowed_kinds=frozenset(
                {
                    TemplateKind.PHOTO_PAGE,
                }
            ),
            photo_capacity=1,
        ),
        TemplateDefinition(
            template_id="photo-page-2",
            name="Two photos",
            allowed_kinds=frozenset(
                {
                    TemplateKind.PHOTO_PAGE,
                }
            ),
            photo_capacity=2,
        ),
        TemplateDefinition(
            template_id="photo-page-4",
            name="Four photos",
            allowed_kinds=frozenset(
                {
                    TemplateKind.PHOTO_PAGE,
                }
            ),
            photo_capacity=4,
        ),

        # Special pages
        TemplateDefinition(
            template_id="dedication",
            name="Dedication",
            allowed_kinds=frozenset(
                {
                    TemplateKind.SPECIAL_PAGE,
                }
            ),
        ),
        TemplateDefinition(
            template_id="blank",
            name="Blank page",
            allowed_kinds=frozenset(
                {
                    TemplateKind.SPECIAL_PAGE,
                }
            ),
        ),
    ]

    return TemplateRegistry(templates)

