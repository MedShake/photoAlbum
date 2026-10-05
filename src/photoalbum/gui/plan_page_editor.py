"""Plan-specific choices; occurrence settings use the shared host dialog."""
from dataclasses import replace

from PySide6.QtWidgets import QDialog, QVBoxLayout, QComboBox, QLabel, QDialogButtonBox

from photoalbum.album import TemplateKind, PlanItemKind
from photoalbum.gui.page_instance_dialog import PageInstanceDialog
from photoalbum.gui.template_labels import template_display_name
from photoalbum.template_engine.instances import create_template_instance


def choose_page(parent, registry, settings, result, translator, *, page=None,
                instance=None, photo_override=False):
    dialog = QDialog(parent)
    dialog.setWindowTitle(translator.tr("plan.modify" if photo_override else "plan.insert_special"))
    layout = QVBoxLayout(dialog)
    anchor_combo = QComboBox()
    if photo_override:
        layout.addWidget(QLabel(translator.tr("plan.start_photo")))
        for photo in page.photos:
            anchor_combo.addItem(photo.filename, photo.identity)
        layout.addWidget(anchor_combo)
    templates = QComboBox()
    if photo_override:
        templates.addItem(translator.tr("plan.use_default"), None)
    geometry = settings.effective_page_format()
    kind = TemplateKind.PHOTO_PAGE if photo_override else TemplateKind.BODY_SPECIAL_PAGE
    for template in registry.list_for_page(kind, geometry.width_mm, geometry.height_mm):
        templates.addItem(template_display_name(template, translator), template.template_id)
    if instance is not None:
        templates.setCurrentIndex(max(0, templates.findData(instance.template_id)))
    elif photo_override and page is not None:
        templates.setCurrentIndex(max(0, templates.findData(page.template_id)))
    layout.addWidget(templates)
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
    buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(templates.count() > 0)
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    layout.addWidget(buttons)
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return None
    identity = anchor_combo.currentData() if photo_override else None
    template_id = templates.currentData()
    if template_id is None:
        return identity, None, settings.template_pack_settings
    if photo_override and identity != page.photos[0].identity:
        # A new content anchor is a new occurrence, even if it starts inside
        # another exceptional page. Never share its instance ID/settings.
        instance = next((item.page for item in settings.photo_page_overrides
                         if item.photo_identity == identity), None)
    if instance is None or instance.template_id != template_id:
        created = create_template_instance(template_id)
        instance = replace(created, instance_id=instance.instance_id) if instance else created
    context_page = None
    if page is not None:
        capacity = registry.get(template_id).photo_capacity
        photos = ()
        if photo_override:
            start = next(i for i, photo in enumerate(page.photos) if photo.identity == identity)
            photos = page.photos[start:start + capacity]
        context_page = replace(page, template_id=template_id, page_instance=instance,
                               kind=PlanItemKind.PHOTO_GROUP if photo_override else PlanItemKind.BODY_SPECIAL_PAGE,
                               photos=photos, photo_capacity=capacity)
        if not photo_override and page.photos:
            date = page.photos[-1].capture_datetime
            if date is not None:
                context_page = replace(context_page, year=date.year, month=date.month, day=date.day)
    pack_settings = settings.template_pack_settings
    while True:
        if context_page is not None:
            context_page = replace(context_page, page_instance=instance)
        editor = PageInstanceDialog(
            instance, result.template_photos, translator=translator,
            page_format=geometry, template_pack_settings=pack_settings,
            usage=kind.value, preview_page=context_page, album_pages=result.pagination.pages,
            temporal_context=tuple(key for key in ("year", "month", "day") if context_page is not None and getattr(context_page, key) is not None),
            parent=parent,
        )
        response = editor.exec()
        if not response:
            return None
        instance, pack_settings = editor.instance(), editor.template_pack_settings()
        if response != PageInstanceDialog.THEME_REQUESTED:
            return identity, instance, pack_settings
        from photoalbum.template_engine.discovery import pack_settings_editor
        pack_id = registry.get(template_id).pack_id
        edit_theme = pack_settings_editor(pack_id) if pack_id else None
        if edit_theme is not None:
            updated = edit_theme(pack_settings, translator=translator, parent=parent)
            if updated is not None:
                pack_settings = updated
