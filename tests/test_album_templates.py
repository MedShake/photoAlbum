import pytest

from photoalbum.album import (
    TemplateDefinition,
    TemplateKind,
    TemplateRegistry,
)


def test_photo_template_exposes_capacity():
    template = TemplateDefinition(
        template_id="photo-classic-2",
        name="Classic - 2 photos",
        kind=TemplateKind.PHOTO_PAGE,
        photo_capacity=2,
    )

    assert template.photo_capacity == 2


def test_photo_template_can_have_different_capacity():
    template = TemplateDefinition(
        template_id="photo-grid-4",
        name="Grid - 4 photos",
        kind=TemplateKind.PHOTO_PAGE,
        photo_capacity=4,
    )

    assert template.photo_capacity == 4


def test_photo_template_requires_at_least_one_slot():
    with pytest.raises(ValueError):
        TemplateDefinition(
            template_id="invalid",
            name="Invalid",
            kind=TemplateKind.PHOTO_PAGE,
        )


def test_non_photo_template_has_no_photo_capacity():
    template = TemplateDefinition(
        template_id="month-classic",
        name="Classic month",
        kind=TemplateKind.MONTH_DIVIDER,
    )

    assert template.photo_capacity == 0


def test_non_photo_template_cannot_expose_photo_slots():
    with pytest.raises(ValueError):
        TemplateDefinition(
            template_id="month-invalid",
            name="Invalid month",
            kind=TemplateKind.MONTH_DIVIDER,
            photo_capacity=2,
        )


def test_negative_photo_capacity_is_rejected():
    with pytest.raises(ValueError):
        TemplateDefinition(
            template_id="invalid",
            name="Invalid",
            kind=TemplateKind.PHOTO_PAGE,
            photo_capacity=-1,
        )


def test_empty_template_id_is_rejected():
    with pytest.raises(ValueError):
        TemplateDefinition(
            template_id="",
            name="Template",
            kind=TemplateKind.SPECIAL_PAGE,
        )


def test_registry_returns_registered_template():
    template = TemplateDefinition(
        template_id="photo-classic-2",
        name="Classic - 2 photos",
        kind=TemplateKind.PHOTO_PAGE,
        photo_capacity=2,
    )

    registry = TemplateRegistry([template])

    assert registry.get("photo-classic-2") == template


def test_registry_rejects_duplicate_ids():
    template = TemplateDefinition(
        template_id="index",
        name="Index",
        kind=TemplateKind.SPECIAL_PAGE,
    )

    registry = TemplateRegistry([template])

    with pytest.raises(ValueError):
        registry.register(template)


def test_registry_rejects_unknown_template():
    registry = TemplateRegistry()

    with pytest.raises(KeyError):
        registry.get("does-not-exist")


def test_registry_filters_templates_by_kind():
    photo_2 = TemplateDefinition(
        template_id="photo-2",
        name="Two photos",
        kind=TemplateKind.PHOTO_PAGE,
        photo_capacity=2,
    )
    photo_4 = TemplateDefinition(
        template_id="photo-4",
        name="Four photos",
        kind=TemplateKind.PHOTO_PAGE,
        photo_capacity=4,
    )
    index = TemplateDefinition(
        template_id="index",
        name="Index",
        kind=TemplateKind.SPECIAL_PAGE,
    )

    registry = TemplateRegistry(
        [photo_2, index, photo_4]
    )

    assert registry.list_by_kind(
        TemplateKind.PHOTO_PAGE
    ) == [
        photo_2,
        photo_4,
    ]

