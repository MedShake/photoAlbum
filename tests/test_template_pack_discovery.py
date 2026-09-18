from photoalbum.album import (
    CoverPosition,
    PageOrientation,
    TemplateKind,
    TemplateTarget,
)
from photoalbum.template_engine import (
    create_template_registry,
    discover_template_packs,
)


def test_msb_pack_is_discovered():
    packs = discover_template_packs()

    assert [pack.pack_id for pack in packs] == [
        "msb"
    ]
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
    }


def test_msb_templates_have_pack_identity():
    registry = create_template_registry()

    assert all(
        template.pack_id == "msb"
        and template.pack_name == "MSB"
        for template in registry.list_all()
    )


def test_msb_supports_a4_portrait_album():
    registry = create_template_registry()

    assert registry.album_target_available(
        TemplateTarget(
            "a4",
            PageOrientation.PORTRAIT,
        )
    )


def test_msb_supports_us_letter_portrait_album():
    registry = create_template_registry()

    assert registry.album_target_available(
        TemplateTarget(
            "us-letter",
            PageOrientation.PORTRAIT,
        )
    )


def test_msb_does_not_claim_a5():
    registry = create_template_registry()

    for orientation in PageOrientation:
        assert not registry.album_target_available(
            TemplateTarget(
                "a5",
                orientation,
            )
        )


def test_msb_does_not_claim_landscape():
    registry = create_template_registry()

    for format_id in (
        "a4",
        "a5",
        "us-letter",
    ):
        assert not registry.album_target_available(
            TemplateTarget(
                format_id,
                PageOrientation.LANDSCAPE,
            )
        )


def test_msb_cover_templates_cover_all_positions():
    registry = create_template_registry()
    target = TemplateTarget(
        "a4",
        PageOrientation.PORTRAIT,
    )

    covers = registry.list_for_target(
        TemplateKind.COVER,
        target,
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
    target = TemplateTarget(
        "a4",
        PageOrientation.PORTRAIT,
    )

    assert registry.list_for_target(
        TemplateKind.PHOTO_PAGE,
        target,
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