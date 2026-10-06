from photoalbum.gui.icon_resources import resource_icon


def test_outline_icons_are_packaged_and_loadable():
    filenames = (
        "photo-open.svg",
        "photo-date.svg",
        "photo-date-missing.svg",
        "photo-location.svg",
        "photo-location-missing.svg",
        "photo-usage-body.svg",
        "photo-usage-template-only.svg",
        "photo-usage-off.svg",
        "plan-add-special.svg",
        "plan-delete.svg",
        "plan-disable.svg",
        "plan-edit.svg",
        "plan-enable.svg",
    )

    for filename in filenames:
        assert not resource_icon(filename).isNull(), filename


def test_outline_icons_are_cached():
    assert resource_icon("photo-open.svg") is resource_icon("photo-open.svg")
