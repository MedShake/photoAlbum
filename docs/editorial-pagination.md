# Editorial pagination

Album Settings retains one default photo-page template. Plan owns exceptions
and body special pages; widgets emit new settings and MainWindow persists and
rebuilds the shared result immediately.

## Stable content boundaries

- `PhotoPageOverride(photo_identity, page)` forces a page start before that photo.
  Its `PageInstance` applies to exactly one page, with its template capacity and
  occurrence settings. Following pages revert to the default until another override.
  Plan's Modify dialog can select any photo currently on the page as the anchor.
- `BodyPageInsertion(anchor, page, enabled)` inserts after a stable photo identity
  or semantic year/month/day divider. A photo anchor forces the end of a photo
  page; later photos cannot cross it. Multiple insertions share an anchor and use
  their persistent list order. No directive stores physical page numbers.
- The shared pagination engine composes natural and forced boundaries, then
  assigns page numbers and sides, including technical/editorial blanks. Inline
  pages carry their anchor's temporal context and use the ordinary renderer.
- End-of-month capacity comes from the last photo page of the actual month and
  eligible trailing technical blanks, not arbitrary non-photo boundaries. Earlier
  intentional cuts and inline pages never masquerade as month ends.

Disabled insertions stay visible in Plan, with no physical number and actions to
edit, enable or delete them. Absent/disabled-source/OFF/TEMPLATE_ONLY photo anchors
are dormant: their saved directives are retained. Incompatible inline templates
are omitted with a warning; incompatible photo overrides fall back to the default
while preserving their boundary, all body photos, and the saved preference.

The new opt-in `body_special_page` role is independent of `special_page`. Only
MSB `dedication`, MSB `blank`, and Simplex `simplex-full-photo-cover` opt in among
built-ins. Plan filters this role and physical compatibility. Occurrence settings
use the existing `PageInstanceDialog`, including shared pack/theme settings.

## Persistence and rendering

Album settings JSON schema 3 serializes `photo_page_overrides` and
`body_insertions`, including anchors, enabled state, occurrence IDs and settings.
Schema 2 loads with empty collections and unchanged historical pagination.
SQLite migration is independent (see [photo sources](photo-sources.md)).

`AlbumBuildResult.template_photos` carries BODY and TEMPLATE_ONLY, excluding OFF.
Preview, PDF and asset preparation consume this canonical pool. `photo_scope="album"`
templates can use it even when a photo does not occur in the chronological body.
All configurable effective pages are discoverable in `pagination.pages`, including
inline pages absent from `plan.items`; render prewarming traverses that pagination.

## Vérification utilisateur

Dans Photos, ajouter plusieurs sources, désactiver/réactiver l’une d’elles et
modifier l’utilisation d’une photo depuis Actions. Dans Plan, choisir Modifier
sur une page A/B, ancrer une exception sur B, puis ajouter une page spéciale après
une autre page. Modifier ensuite le modèle par défaut : les frontières restent
attachées au contenu. Les insertions désactivées restent administrables avec « — ».
Comparer le Plan, l’Aperçu et le nombre de pages du PDF. Les sélecteurs des modèles
doivent toujours proposer les photos hors corps, jamais les photos désactivées.
