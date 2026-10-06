from photoalbum.gui.widgets.photo_actions_delegate import _photo_action_icon


def test_photo_action_outline_icons_are_packaged_and_loadable():
    filenames = (
        "photo-open.svg",
        "photo-date.svg",
        "photo-date-missing.svg",
        "photo-location.svg",
        "photo-location-missing.svg",
        "photo-usage-body.svg",
        "photo-usage-template-only.svg",
        "photo-usage-off.svg",
    )

    for filename in filenames:
        assert not _photo_action_icon(filename).isNull(), filename


def test_photo_action_icons_are_cached():
    assert _photo_action_icon("photo-open.svg") is _photo_action_icon("photo-open.svg")
