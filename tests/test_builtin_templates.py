from photoalbum.album import (
    TemplateKind,
    create_builtin_template_registry,
)


def test_builtin_registry_contains_photo_templates():
    registry = create_builtin_template_registry()

    templates = registry.list_by_kind(
        TemplateKind.PHOTO_PAGE
    )

    ids = {
        template.template_id
        for template in templates
    }

    assert ids == {
        "photo-page-1",
        "photo-page-2",
        "photo-page-3",
        "photo-page-4",
    }


def test_builtin_photo_templates_have_expected_capacities():
    registry = create_builtin_template_registry()

    assert registry.get(
        "photo-page-1"
    ).photo_capacity == 1

    assert registry.get(
        "photo-page-2"
    ).photo_capacity == 2

    assert registry.get(
        "photo-page-4"
    ).photo_capacity == 4


def test_builtin_registry_contains_dividers():
    registry = create_builtin_template_registry()

    month_templates = registry.list_by_kind(
        TemplateKind.MONTH_DIVIDER
    )
    year_templates = registry.list_by_kind(
        TemplateKind.YEAR_DIVIDER
    )

    assert {
        template.template_id
        for template in month_templates
    } == {
        "month-divider-classic",
    }

    assert {
        template.template_id
        for template in year_templates
    } == {
        "year-divider-classic",
    }


def test_geographic_word_cloud_is_reusable():
    registry = create_builtin_template_registry()

    template = registry.get(
        "geographic-word-cloud"
    )

    assert template.supports(
        TemplateKind.COVER
    )
    assert template.supports(
        TemplateKind.SPECIAL_PAGE
    )


def test_calendar_index_is_reusable():
    registry = create_builtin_template_registry()

    template = registry.get(
        "calendar-index"
    )

    assert template.supports(
        TemplateKind.COVER
    )
    assert template.supports(
        TemplateKind.SPECIAL_PAGE
    )


def test_dedication_is_special_page_only():
    registry = create_builtin_template_registry()

    template = registry.get(
        "dedication"
    )

    assert template.supports(
        TemplateKind.SPECIAL_PAGE
    )
    assert not template.supports(
        TemplateKind.COVER
    )


def test_builtin_template_ids_are_unique():
    registry = create_builtin_template_registry()

    templates = registry.list_all()

    ids = [
        template.template_id
        for template in templates
    ]

    assert len(ids) == len(set(ids))

