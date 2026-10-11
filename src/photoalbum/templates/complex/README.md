# Complex 1.4.0 for Photo Album 0.4.1

An independent photo-page template pack (no runtime dependency on MSB), one template for each capacity 1–5 and a single greedy `complex-auto-1-5` selector.

- **Four-photo Reportage is unchanged geometrically:** 4 portrait, 4 landscape, 2 square variants.
- **Five-photo Mosaïque:** 6 portrait / 6 landscape / 12 square variants.
- **Five-photo Séquence:** 3 portrait / 2 landscape variants; none for square.
- Total **29 five-photo variants**; the settings drop-down exposes those appropriate to the selected page family.
- All photo slot lists are in chronological order and are also the source of automatic orientation signatures. Original image ratios are preserved by `ImageFit.CONTAIN` (no cropping). Caption reservations remain enabled.
- When several options match, choose in declaration order with **round-robin per page format and P/L signature**. Manual page overrides never increase counts, counts reset at each pagination, and regeneration is reproducible.

**Important:** Photo Album 0.4.1 needs a *small backwards-compatible host integration* to pass per-pagination counters to the selector. The complete installation ZIP includes both the pack and the two modified host files (`album/templates.py`, `album/pagination.py`); the pack-only ZIP works but uses the first compatible variant until the host integration is installed.

See [README.fr.md](README.fr.md) for all installation instructions and tests.
