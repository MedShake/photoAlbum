from __future__ import annotations


CATALOGS: dict[str, dict[str, str]] = {
    "en": {
        "tab.photos": "Photos",
        "tab.album": "Album",
        "tab.plan": "Plan",

        "album.covers": "Covers",
        "album.front_cover": "Front cover:",
        "album.inside_front_cover": "Inside front cover:",
        "album.inside_back_cover": "Inside back cover:",
        "album.back_cover": "Back cover:",

        "album.dividers": "Dividers",
        "album.month_separators": "Month separators",
        "album.year_separators": "Year separators",

        "album.photo_pages": "Photo pages",
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
        "tab.album": "Album",
        "tab.plan": "Plan",

        "album.covers": "Couvertures",
        "album.front_cover": "1re de couverture :",
        "album.inside_front_cover": "2e de couverture :",
        "album.inside_back_cover": "3e de couverture :",
        "album.back_cover": "4e de couverture :",

        "album.dividers": "Séparateurs",
        "album.month_separators": "Séparateurs de mois",
        "album.year_separators": "Séparateurs d’année",

        "album.photo_pages": "Pages photo",
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

