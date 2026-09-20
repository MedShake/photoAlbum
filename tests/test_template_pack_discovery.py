def geometry(format_id, orientation):
    page = oriented_page_format(page_format_from_id(format_id), orientation)
    return page.width_mm, page.height_mm


from photoalbum.album import (
    CoverPosition,
    PageOrientation,
    TemplateKind,
    oriented_page_format,
    page_format_from_id,
)
from photoalbum.template_engine import (
    create_template_registry,
    discover_template_packs,
)


def test_msb_pack_is_discovered():
    packs = discover_template_packs()

    pack_ids = {
        pack.pack_id
        for pack in packs
    }

    assert "msb" in pack_ids
    assert "simplex" in pack_ids
    assert packs[0].name == "MSB"


def test_msb_templates_are_discovered():
    registry = create_template_registry()

    assert {
        template.template_id
        for template in registry.list_all()
    } == {
        "year-photo-scatter",
        "geographic-word-cloud",
        "calendar-index",
        "year-divider-classic",
        "month-divider-classic",
        "month-divider-simple",
        "photo-page-1",
        "photo-page-2",
        "photo-page-3",
        "photo-page-4",
        "dedication",
        "blank",
        "simplex-full-photo-cover",
    }


def test_msb_templates_have_pack_identity():
    registry = create_template_registry()

    msb_templates = [
        template
        for template in registry.list_all()
        if template.pack_id == "msb"
    ]

    assert msb_templates

    assert all(
        template.pack_name == "MSB"
        for template in msb_templates
    )

    simplex = registry.get(
        "simplex-full-photo-cover"
    )

    assert simplex is not None
    assert simplex.pack_id == "simplex"
    assert simplex.pack_name == "Simplex"


def test_msb_supports_a4_portrait_album():
    registry = create_template_registry()

    assert registry.album_page_available(*
        geometry(
            "a4",
            PageOrientation.PORTRAIT,
        )
    )


def test_msb_supports_us_letter_portrait_album():
    registry = create_template_registry()

    assert registry.album_page_available(*
        geometry(
            "us-letter",
            PageOrientation.PORTRAIT,
        )
    )


def test_templates_accept_a5():
    registry = create_template_registry()

    for orientation in PageOrientation:
        assert registry.album_page_available(*
            geometry(
                "a5",
                orientation,
            )
        )


def test_templates_accept_landscape_across_host_formats():
    registry = create_template_registry()

    assert registry.album_page_available(*
        geometry(
            "a4",
            PageOrientation.LANDSCAPE,
        )
    )

    for format_id in (
        "a5",
        "us-letter",
    ):
        assert registry.album_page_available(*
            geometry(
                format_id,
                PageOrientation.LANDSCAPE,
            )
        )


def test_msb_cover_templates_cover_all_positions():
    registry = create_template_registry()
    target = geometry(
        "a4",
        PageOrientation.PORTRAIT,
    )

    covers = registry.list_for_page(
        TemplateKind.COVER,
        *target,
    )

    for position in CoverPosition:
        assert any(
            template.supports_cover_position(
                position
            )
            for template in covers
        )


def test_msb_has_photo_page_for_supported_target():
    registry = create_template_registry()
    target = geometry(
        "a4",
        PageOrientation.PORTRAIT,
    )

    assert registry.list_for_page(
        TemplateKind.PHOTO_PAGE,
        *target,
    )

def test_third_party_pack_is_discovered_from_directory(
    tmp_path,
):
    pack_dir = tmp_path / "example"
    pack_dir.mkdir()

    (pack_dir / "manifest.json").write_text(
        """
{
    "schema_version": 1,
    "id": "example",
    "name": "Example",
    "version": "1.0",
    "authors": [
        {
            "name": "Example Author"
        }
    ],
    "description": "Example template pack.",
    "templates": []
}
""".strip(),
        encoding="utf-8",
    )

    packs = discover_template_packs(tmp_path)

    assert len(packs) == 1

    pack = packs[0]

    assert pack.pack_id == "example"
    assert pack.name == "Example"
    assert pack.version == "1.0"
    assert pack.authors == ("Example Author",)
    assert pack.description == "Example template pack."
    assert pack.templates == ()

def test_third_party_pack_is_discovered_from_directory(
    tmp_path,
):
    pack_dir = tmp_path / "example"
    pack_dir.mkdir()

    (pack_dir / "manifest.json").write_text(
        """
{
    "schema_version": 1,
    "id": "example",
    "name": "Example",
    "version": "1.0",
    "authors": [
        {
            "name": "Example Author"
        }
    ],
    "description": "Example template pack.",
    "templates": []
}
""".strip(),
        encoding="utf-8",
    )

    packs = discover_template_packs(tmp_path)

    assert len(packs) == 1

    pack = packs[0]

    assert pack.pack_id == "example"
    assert pack.name == "Example"
    assert pack.version == "1.0"
    assert pack.authors == ("Example Author",)
    assert pack.description == "Example template pack."
    assert pack.templates == ()

def test_msb_dedication_usage_contract():
    """Dedication is a special page and a restricted cover template."""
    registry = create_template_registry()
    target = geometry(
        "a4",
        PageOrientation.PORTRAIT,
    )

    dedication = registry.get("dedication")
    assert dedication is not None

    special_pages = registry.list_for_page(
        TemplateKind.SPECIAL_PAGE,
        *target,
    )
    assert dedication in special_pages

    covers = registry.list_for_page(
        TemplateKind.COVER,
        *target,
    )
    assert dedication in covers

    assert not dedication.supports_cover_position(
        CoverPosition.FRONT
    )
    assert dedication.supports_cover_position(
        CoverPosition.INSIDE_FRONT
    )
    assert dedication.supports_cover_position(
        CoverPosition.INSIDE_BACK
    )
    assert dedication.supports_cover_position(
        CoverPosition.BACK
    )


def test_msb_selected_templates_support_a4_landscape():
    registry = create_template_registry()
    target = geometry(
        "a4",
        PageOrientation.LANDSCAPE,
    )

    cover_ids = {
        template.template_id
        for template in registry.list_for_page(
            TemplateKind.COVER,
            *target,
        )
    }

    special_page_ids = {
        template.template_id
        for template in registry.list_for_page(
            TemplateKind.SPECIAL_PAGE,
            *target,
        )
    }

    photo_page_ids = {
        template.template_id
        for template in registry.list_for_page(
            TemplateKind.PHOTO_PAGE,
            *target,
        )
    }

    assert "year-photo-scatter" in cover_ids
    assert "geographic-word-cloud" in special_page_ids
    assert "photo-page-1" in photo_page_ids


def test_all_photo_pages_support_landscape():
    registry = create_template_registry()
    target = geometry(
        "a4",
        PageOrientation.LANDSCAPE,
    )

    photo_page_ids = {
        template.template_id
        for template in registry.list_for_page(
            TemplateKind.PHOTO_PAGE,
            *target,
        )
    }

    assert "photo-page-1" in photo_page_ids

    assert {
        "photo-page-2",
        "photo-page-3",
        "photo-page-4",
    } <= photo_page_ids
