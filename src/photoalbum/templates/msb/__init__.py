"""MSB template pack.

This package is discovered from manifest.json.  No central
application registry should know the individual MSB templates.
"""


def edit_settings(settings, *, translator, parent=None):
    """Edit the shared MSB theme; return None when cancelled."""
    from .theme import msb_theme_from_pack_settings, pack_settings_with_msb_theme
    from .theme_dialog import MsbThemeDialog

    dialog = MsbThemeDialog(
        msb_theme_from_pack_settings(settings),
        translator=translator,
        parent=parent,
    )
    if not dialog.exec():
        return None
    return pack_settings_with_msb_theme(settings, dialog.theme())
