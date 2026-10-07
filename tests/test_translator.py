from photoalbum.i18n import Translator


def test_english_translation():
    translator = Translator("en")

    assert translator.tr("plan.summary") == "Summary"


def test_french_translation():
    translator = Translator("fr")

    assert translator.tr("plan.summary") == "Résumé"


def test_translation_formats_values():
    translator = Translator("fr")

    assert translator.tr(
        "plan.unused_slots",
        count=3,
    ) == "3 emplacements inutilisés"


def test_month_name_is_controlled_by_application_language():
    assert Translator("en").month_name(3) == "March"
    assert Translator("fr").month_name(3) == "mars"


def test_unknown_key_returns_key():
    translator = Translator("fr")

    assert translator.tr("unknown.key") == "unknown.key"


def test_print_diagnostic_uses_real_singular_and_plural():
    en = Translator("en")
    fr = Translator("fr")

    assert en.tr(
        "plan.print_incompatible_one",
        pages=5,
        multiple=4,
        additional=1,
    ).endswith(
        "1 additional page would be required."
    )

    assert en.tr(
        "plan.print_incompatible_many",
        pages=6,
        multiple=4,
        additional=2,
    ).endswith(
        "2 additional pages would be required."
    )

    assert fr.tr(
        "plan.print_incompatible_one",
        pages=5,
        multiple=4,
        additional=1,
    ).endswith(
        "1 page supplémentaire serait nécessaire."
    )

    assert fr.tr(
        "plan.print_incompatible_many",
        pages=6,
        multiple=4,
        additional=2,
    ).endswith(
        "2 pages supplémentaires seraient nécessaires."
    )


def test_french_caption_overflow_wording():
    fr = Translator("fr")

    text = fr.tr(
        "plan.caption_overflow",
        page=12,
        photo="photo.jpg",
        required=4,
        available=2,
    )

    assert (
        "mais ce modèle n’en affiche au maximum que 2"
        in text
    )


def test_source_reconnect_messages_are_translated():
    en = Translator("en")
    fr = Translator("fr")

    assert en.tr(
        "source.export.reconnect_required",
        filename="photo.jpg",
    ) == "Reconnect the source containing ‘photo.jpg’ before generating the PDF."

    assert fr.tr(
        "source.export.reconnect_required",
        filename="photo.jpg",
    ) == "Reconnectez la source contenant « photo.jpg » avant de générer le PDF."

    assert fr.tr(
        "source.asset.reconnect_required",
        filename="photo.jpg",
    ) == "Reconnectez la source contenant « photo.jpg » pour récupérer cette photo."


def test_user_facing_operation_errors_do_not_expose_raw_exception_text():
    raw = "database is locked / provider exploded"

    for language in ("en", "fr"):
        translator = Translator(language)
        messages = (
            translator.tr("source.synology.connection_error", error=raw),
            translator.tr("photos.gps.geocoding_failed", error=raw),
            translator.tr("processing.event.geocoding_error", error=raw),
            translator.tr("render.generate_error", error=raw),
            translator.tr("main.save_album_error", error=raw),
            translator.tr("main.build_plan_error", error=raw),
        )
        assert all(raw not in message for message in messages)


def test_operation_error_messages_are_translated_in_french():
    fr = Translator("fr")

    assert fr.tr("main.create_project_error") == "Impossible de créer le projet."
    assert fr.tr("main.open_project_error") == "Impossible d’ouvrir le projet."
    assert fr.tr("source.scan.failed") == "Impossible d’analyser les sources de photos."
    assert fr.tr("source.metadata.failed") == "Impossible de mettre à jour les métadonnées des photos."
    assert fr.tr(
        "sources.refresh.file_failed",
        source="Vacances",
        filename="photo.jpg",
    ) == "Source Vacances : impossible d’analyser photo.jpg."


def test_source_refresh_and_reconnect_labels_are_user_facing():
    en = Translator("en")
    fr = Translator("fr")

    assert en.tr("sources.analyze") == "Refresh photos"
    assert en.tr("sources.synchronize") == "Synchronize remote sources"
    assert en.tr("sources.reconnect") == "Reconnect…"
    assert en.tr("sources.connection.reconnect_required") == "Reconnection required"

    assert fr.tr("sources.analyze") == "Actualiser les photos"
    assert fr.tr("sources.synchronize") == "Synchroniser les sources distantes"
    assert fr.tr("sources.reconnect") == "Reconnecter…"
    assert fr.tr("sources.connection.reconnect_required") == "Reconnexion requise"


def test_source_card_sync_and_journal_labels_are_localized():
    en = Translator("en")
    fr = Translator("fr")
    assert en.tr("sources.synchronize_one") == "Synchronize"
    assert fr.tr("sources.synchronize_one") == "Synchroniser"
    assert "Album" in en.tr("sources.sync.started", source="Album")
    assert "Album" in fr.tr("sources.sync.completed", source="Album")
