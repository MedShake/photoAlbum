"""Create and validate template instances without interpreting their settings."""
from copy import deepcopy

from photoalbum.album.settings import PageInstance
from photoalbum.template_engine.extensions import template_extension_registry


def create_template_instance(template_id: str) -> PageInstance:
    extension = template_extension_registry.get(template_id)
    settings = (
        extension.settings_defaults()
        if extension is not None and extension.settings_defaults is not None
        else {}
    )
    if not isinstance(settings, dict):
        raise ValueError(f"Template {template_id!r} settings defaults must be an object.")
    instance = PageInstance(template_id=template_id, settings=deepcopy(settings))
    validate_template_instance(instance)
    return instance


def validate_template_instance(instance: PageInstance) -> None:
    extension = template_extension_registry.get(instance.template_id)
    if extension is not None and extension.validate_settings is not None:
        extension.validate_settings(deepcopy(instance.settings))
