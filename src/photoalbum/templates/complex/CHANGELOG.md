## 1.4.0 — Mosaïque / Séquence 5-photo variants and round-robin selection

- Reportage 4-photo geometry and manual IDs unchanged from 1.3.0.
- Portrait Mosaïque: six column configurations (2+3 / 3+2, three portrait positions in the triple column).
- Landscape Mosaïque: all six column permutations PP / P / LL, preserving column-wise chronological reading.
- Square Mosaïque: twelve variants (3+2 or 2+3 photos by row, original ratio-correct P/L slots and row-major reading).
- Portrait Séquence: hero at chronological photo 1, 3 or 5.
- Landscape Séquence: two large photos above or below three small ones; center removed per agreed design.
- Exactly 29 five-photo variants, and all 10 four-photo variants retained.
- One greedy 1–5 automatic selector derives its signatures directly from the actual layouts.
- Round-robin for ambiguous signatures, independently by page format/signature, with non-consuming manual overrides and per-pagination reset. A two-file backward-compatible host integration passes the ephemeral state to the pack.
- Full ratio, caption safety, priority, regeneration and manual-interleaving regression tests.

## 1.3.0 — Reportage 4-photo geometry and chronology

- Four portrait / four landscape / two square Reportage geometries.
- Format-specific chronological slots.
- Local self-contained captions and ratio-correct placement.
