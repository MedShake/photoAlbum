from __future__ import annotations


CATALOGS: dict[str, dict[str, str]] = {
    "en": {
        "tab.photos": "Photos",

        "photos.column.filename": "Filename",
        "photos.column.capture_date": "Capture date",
        "photos.column.date_source": "Date source",
        "photos.column.gps": "GPS",
        "photos.column.city": "City",
        "photos.column.location_source": "Location source",
        "photos.column.status": "Status",

        "photos.value.yes": "Yes",
        "photos.value.no": "No",
        "photos.value.ok": "OK",
        "photos.value.missing_date": "Missing date",

        "photos.date_source.exif": "EXIF",
        "photos.date_source.filename": "Filename",
        "photos.date_source.manual": "Manual",
        "photos.date_source.unknown": "Unknown",

        "photos.location_source.geocoding": "Geocoding",
        "photos.location_source.manual": "Manual",
        "photos.location_source.unknown": "Unknown",
        "tab.album": "Album",
        "tab.plan": "Plan",

        "main.file": "File",
        "main.new_project": "New Project...",
        "main.open_project": "Open Project...",
        "main.close_project": "Close Project",
        "main.quit": "Quit",

        "main.choose_source": "Choose Source Folder...",
        "main.source_folder": "Source folder:",
        "main.include_subdirectories": "Include subdirectories",
        "main.analyze_photos": "Analyze Photos",
        "main.photos": "Photos:",

        "main.no_analysis": "No analysis performed.",
        "main.analysis_running": "Analysis in progress...",
        "main.analysis_failed": "Analysis failed.",
        "main.analysis_completed": "Photo analysis completed.",
        "main.analyzing": "Analyzing photos...",

        "main.no_project": "No project open",
        "main.ready": "Ready",
        "main.project": "Project: {name}",

        "main.create_project_title": "Create Photo Album Project",
        "main.open_project_title": "Open Photo Album Project",
        "main.choose_source_title": "Choose Source Photo Folder",

        "main.scan_running_warning": (
            "A photo analysis is still running."
        ),
        "main.no_project_error": "No project is open.",
        "main.choose_source_error": (
            "Choose a source photo folder first."
        ),
        "main.source_missing_error": (
            "Source folder does not exist: {path}"
        ),
        "main.save_album_error": (
            "Could not save album settings: {error}"
        ),
        "main.build_plan_error": (
            "Could not build album plan: {error}"
        ),

        "main.discovered": "Discovered: {count}",
        "main.analyzed": "Analyzed: {count}",
        "main.reused": "Reused: {count}",
        "main.geocoded": "Geocoded: {count}",
        "main.date_anomalies": "Date anomalies: {count}",
        "main.errors": "Errors: {count}",

        "main.stored_photos": "Stored photos: {count}",
        "main.gps": "GPS: {count}",
        "main.located": "Located: {count}",

        "main.photos_requiring_date": (
            "Photos requiring a capture date:"
        ),

        "album.covers": "Covers",
        "album.front_cover": "Front cover:",
        "album.inside_front_cover": "Inside front cover:",
        "album.inside_back_cover": "Inside back cover:",
        "album.back_cover": "Back cover:",

        "album.dividers": "Dividers",
        "album.month_separators": "Month separators",
        "album.year_separators": "Year separators",

        "album.photo_pages": "Photo pages",
        "album.caption_datetime": "Show capture date and time",
        "album.caption_location": "Show location",
        "album.page_numbering": "Page numbering",
        "album.show_page_numbers": "Show page numbers",
        "album.template": "Template:",

        "album.front_matter": "Pages after inside front cover",
        "album.back_matter": "Pages before inside back cover",

        "album.add": "Add",
        "album.up": "Up",
        "album.down": "Down",
        "album.remove": "Remove",

        "album.placement.natural": "Natural flow",
        "album.placement.right": "Always on right page",
        "album.placement.right_blank": (
            "Right page with blank facing page"
        ),

        "album.years_detected": "{count} years detected.",
        "album.year_unavailable": (
            "Year separators are unavailable: "
            "all photos belong to {year}."
        ),
        "album.year_no_photos": (
            "Year separators are unavailable until "
            "dated photos are present."
        ),

        "template.year-photo-scatter": "Year photo scatter",
        "template.geographic-word-cloud": "Geographic word cloud",
        "template.calendar-index": "Calendar index",
        "template.year-divider-classic": "Classic year divider",
        "template.month-divider-classic": "Classic month divider",
        "template.photo-page-1": "One photo",
        "template.photo-page-2": "Two photos",
        "template.photo-page-3": "Three photos",
        "template.photo-page-4": "Four photos",
        "template.dedication": "Dedication",
        "template.blank": "Blank page",

        "plan.summary": "Summary",
        "plan.optimizations": "Possible optimizations",
        "plan.structure": "Document structure",

        "plan.no_plan": "No album plan available.",
        "plan.no_optimization": "No optimization available.",
        "plan.no_unused_capacity": (
            "No unused photo capacity detected "
            "at the end of a month."
        ),

        "plan.photos": "Photos",
        "plan.pages": "Pages",
        "plan.photo_pages": "Photo pages",
        "plan.dividers": "Dividers",
        "plan.special_pages": "Special pages",
        "plan.technical_blanks": "Technical blanks",
        "plan.editorial_blanks": "Editorial blanks",

        "plan.print_disabled": (
            "Print diagnostic: no page-count constraint enabled."
        ),
        "plan.print_compatible": (
            "Print diagnostic: {pages} pages — compatible "
            "with a multiple of {multiple}."
        ),
        "plan.print_incompatible": (
            "Print diagnostic: {pages} pages — not a multiple "
            "of {multiple}. {additional} additional page(s) "
            "would be required."
        ),

        "plan.suggestion": (
            "{month} {year}: up to {slots} additional photo(s) "
            "can be added without increasing the number of pages "
            "before the next period."
        ),

        "plan.other_pages": "Other pages",
        "plan.page": "Page",
        "plan.photos_page": "Photos",
        "plan.month_divider": "Month divider",
        "plan.year_divider": "Year divider",
        "plan.special_page": "Special page",
        "plan.technical_blank": "Technical blank",
        "plan.editorial_blank": "Editorial blank",
        "plan.unused_slots": "{count} unused slot(s)",

        "month.1": "January",
        "month.2": "February",
        "month.3": "March",
        "month.4": "April",
        "month.5": "May",
        "month.6": "June",
        "month.7": "July",
        "month.8": "August",
        "month.9": "September",
        "month.10": "October",
        "month.11": "November",
        "month.12": "December",
    },

    "fr": {
        "tab.photos": "Photos",

        "photos.column.filename": "Nom du fichier",
        "photos.column.capture_date": "Date de prise de vue",
        "photos.column.date_source": "Source de la date",
        "photos.column.gps": "GPS",
        "photos.column.city": "Ville",
        "photos.column.location_source": "Source de localisation",
        "photos.column.status": "Statut",

        "photos.value.yes": "Oui",
        "photos.value.no": "Non",
        "photos.value.ok": "OK",
        "photos.value.missing_date": "Date manquante",

        "photos.date_source.exif": "EXIF",
        "photos.date_source.filename": "Nom de fichier",
        "photos.date_source.manual": "Manuelle",
        "photos.date_source.unknown": "Inconnue",

        "photos.location_source.geocoding": "Géocodage",
        "photos.location_source.manual": "Manuelle",
        "photos.location_source.unknown": "Inconnue",
        "tab.album": "Album",
        "tab.plan": "Plan",

        "main.file": "Fichier",
        "main.new_project": "Nouveau projet...",
        "main.open_project": "Ouvrir un projet...",
        "main.close_project": "Fermer le projet",
        "main.quit": "Quitter",

        "main.choose_source": "Choisir le dossier source...",
        "main.source_folder": "Dossier source :",
        "main.include_subdirectories": "Inclure les sous-dossiers",
        "main.analyze_photos": "Analyser les photos",
        "main.photos": "Photos :",

        "main.no_analysis": "Aucune analyse effectuée.",
        "main.analysis_running": "Analyse en cours...",
        "main.analysis_failed": "Échec de l’analyse.",
        "main.analysis_completed": "Analyse des photos terminée.",
        "main.analyzing": "Analyse des photos en cours...",

        "main.no_project": "Aucun projet ouvert",
        "main.ready": "Prêt",
        "main.project": "Projet : {name}",

        "main.create_project_title": "Créer un projet Photo Album",
        "main.open_project_title": "Ouvrir un projet Photo Album",
        "main.choose_source_title": "Choisir le dossier des photos",

        "main.scan_running_warning": (
            "Une analyse des photos est encore en cours."
        ),
        "main.no_project_error": "Aucun projet n’est ouvert.",
        "main.choose_source_error": (
            "Choisissez d’abord un dossier source."
        ),
        "main.source_missing_error": (
            "Le dossier source n’existe pas : {path}"
        ),
        "main.save_album_error": (
            "Impossible d’enregistrer les réglages de l’album : {error}"
        ),
        "main.build_plan_error": (
            "Impossible de construire le plan de l’album : {error}"
        ),

        "main.discovered": "Détectées : {count}",
        "main.analyzed": "Analysées : {count}",
        "main.reused": "Réutilisées : {count}",
        "main.geocoded": "Géolocalisées : {count}",
        "main.date_anomalies": "Anomalies de date : {count}",
        "main.errors": "Erreurs : {count}",

        "main.stored_photos": "Photos enregistrées : {count}",
        "main.gps": "GPS : {count}",
        "main.located": "Localisées : {count}",

        "main.photos_requiring_date": (
            "Photos nécessitant une date de prise de vue :"
        ),

        "album.covers": "Couvertures",
        "album.front_cover": "1re de couverture :",
        "album.inside_front_cover": "2e de couverture :",
        "album.inside_back_cover": "3e de couverture :",
        "album.back_cover": "4e de couverture :",

        "album.dividers": "Séparateurs",
        "album.month_separators": "Séparateurs de mois",
        "album.year_separators": "Séparateurs d’année",

        "album.photo_pages": "Pages photo",
        "album.caption_datetime": "Afficher la date et l’heure",
        "album.caption_location": "Afficher le lieu",
        "album.page_numbering": "Numérotation",
        "album.show_page_numbers": "Afficher les numéros de page",
        "album.template": "Modèle :",

        "album.front_matter": "Pages après la 2e de couverture",
        "album.back_matter": "Pages avant la 3e de couverture",

        "album.add": "Ajouter",
        "album.up": "Monter",
        "album.down": "Descendre",
        "album.remove": "Supprimer",

        "album.placement.natural": "Placement naturel",
        "album.placement.right": "Toujours sur une page droite",
        "album.placement.right_blank": (
            "Page droite avec page gauche laissée blanche"
        ),

        "album.years_detected": "{count} années détectées.",
        "album.year_unavailable": (
            "Séparateurs d’année indisponibles : "
            "toutes les photos appartiennent à {year}."
        ),
        "album.year_no_photos": (
            "Séparateurs d’année indisponibles tant qu’aucune "
            "photo datée n’est présente."
        ),

        "template.year-photo-scatter": "Pêle-mêle annuel",
        "template.geographic-word-cloud": "Nuage géographique",
        "template.calendar-index": "Calendrier / index",
        "template.year-divider-classic": "Séparateur d’année classique",
        "template.month-divider-classic": "Séparateur de mois classique",
        "template.photo-page-1": "Une photo",
        "template.photo-page-2": "Deux photos",
        "template.photo-page-3": "Trois photos",
        "template.photo-page-4": "Quatre photos",
        "template.dedication": "Dédicace",
        "template.blank": "Page blanche",


        "plan.summary": "Résumé",
        "plan.optimizations": "Optimisations possibles",
        "plan.structure": "Structure du document",

        "plan.no_plan": "Aucun plan d’album disponible.",
        "plan.no_optimization": "Aucune optimisation disponible.",
        "plan.no_unused_capacity": (
            "Aucune capacité photo inutilisée détectée "
            "en fin de mois."
        ),

        "plan.photos": "Photos",
        "plan.pages": "Pages",
        "plan.photo_pages": "Pages photo",
        "plan.dividers": "Séparateurs",
        "plan.special_pages": "Pages spéciales",
        "plan.technical_blanks": "Pages blanches techniques",
        "plan.editorial_blanks": "Pages blanches éditoriales",

        "plan.print_disabled": (
            "Diagnostic d’impression : aucune contrainte "
            "de nombre de pages activée."
        ),
        "plan.print_compatible": (
            "Diagnostic d’impression : {pages} pages — compatible "
            "avec un multiple de {multiple}."
        ),
        "plan.print_incompatible": (
            "Diagnostic d’impression : {pages} pages — ce nombre "
            "n’est pas un multiple de {multiple}. "
            "{additional} page(s) supplémentaire(s) seraient "
            "nécessaires."
        ),

        "plan.suggestion": (
            "{month} {year} : jusqu’à {slots} photo(s) "
            "supplémentaire(s) peuvent être ajoutées sans augmenter "
            "le nombre de pages avant la période suivante."
        ),

        "plan.other_pages": "Autres pages",
        "plan.page": "Page",
        "plan.photos_page": "Photos",
        "plan.month_divider": "Séparateur de mois",
        "plan.year_divider": "Séparateur d’année",
        "plan.special_page": "Page spéciale",
        "plan.technical_blank": "Page blanche technique",
        "plan.editorial_blank": "Page blanche éditoriale",
        "plan.unused_slots": "{count} emplacement(s) inutilisé(s)",

        "month.1": "janvier",
        "month.2": "février",
        "month.3": "mars",
        "month.4": "avril",
        "month.5": "mai",
        "month.6": "juin",
        "month.7": "juillet",
        "month.8": "août",
        "month.9": "septembre",
        "month.10": "octobre",
        "month.11": "novembre",
        "month.12": "décembre",
    },
}


class Translator:
    def __init__(
        self,
        language: str = "en",
    ) -> None:
        self._language = language

    @property
    def language(self) -> str:
        return self._language

    def set_language(
        self,
        language: str,
    ) -> None:
        if language not in CATALOGS:
            raise ValueError(
                f"Unsupported language: {language}"
            )

        self._language = language

    def tr(
        self,
        key: str,
        **values,
    ) -> str:
        catalog = CATALOGS.get(
            self._language,
            CATALOGS["en"],
        )

        text = catalog.get(
            key,
            CATALOGS["en"].get(key, key),
        )

        return text.format(**values)

    def month_name(
        self,
        month: int,
    ) -> str:
        if not 1 <= month <= 12:
            raise ValueError(
                f"Invalid month: {month}"
            )

        return self.tr(f"month.{month}")

