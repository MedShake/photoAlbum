# Geographic Map coordinates and rendering

Photos keep canonical GPS coordinates. Composition ignores missing, non-finite
or out-of-range coordinates, filters by year and deduplicates photo paths just
like the preview backend. The normalized marker x/y fields are retained for
compatibility; the painter projects longitude/latitude itself.

Natural Earth components are unwrapped once and cached together with their
continuous bounds. Adjacent vertices stay in the same continuous plane. The
explicit pole edge closing Antarctica is preserved. Point containment uses
that same plane. A photo contributes its containing component, not every
territory of its country; unmatched coastal or ocean points contribute their
coordinates. This intentionally gives country context even for local photos.
The enclosing circular arc is computed from occupied component intervals,
not independent vertices: a cut must not pass through a component's interior.
Padding is limited to one world.

Rendering selects every overlapping 360-degree copy of each whole component.
It clips polygons at the chosen world's longitude seam before projecting them.
The mathematical projection receives longitude relative to the viewport's
central meridian and never wraps individual vertices. Independent markers alone
choose their nearest world copy. Equal Earth and Robinson therefore retain the
same geometry when the map is centered on the Pacific. A single uniform scale
fits projected bounds to the page; QPainter clips to the page and preserves any
existing caller clip. No long-edge filtering is used.

`minimal_longitude_interval` applies to independent points; `continuous_ring`
applies to connected geometry. `unwrap_longitude` expresses a coordinate in a
specified 360-degree interval, whereas `longitude_near_reference` selects the
nearest equivalent coordinate. Neither belongs inside polygon projection.

Both the preview worker and final vector renderer use `rendering.py` for all
options, monthly theme colors, legend and empty state, then the same painter.
Preview jobs snapshot photos and perform composition/Natural Earth loading in
the worker. Geometry and projected extents are cached independently of styling.
Projection IDs (`web_mercator`, `equal_earth`, `robinson`) and stored settings
remain compatible; an unknown projection renders as Web Mercator.

The bundled Natural Earth data is 1:50m: it is contextual cartography, not a
precise coastline or local boundary source. Robinson retains the existing
linear interpolation of its five-degree table. Tests cover real Russian
geometry through the paint path, seam handling, world rotation, component
closure, fitting, invalid data, UI/persistence/cache and preview/final equality.

Module boundaries: `geography.py` owns continuous geographic geometry;
`composition.py` selects photos and provides geographic markers; `painter.py`
projects and draws them. `rendering.py` shares styling and the empty state
between the preview worker and vector renderer. `defaults.py` contains the
persisted option defaults without importing the settings UI. `settings.py`
re-exports those constants for compatibility and owns the editor.

The painter's `_visible_rings` is the single production path for component
selection, placement and seam clipping. Continuity tests exercise
`geography.continuous_ring`; intersection regressions exercise `_visible_rings`
instead of maintaining alternate private helpers only for tests. The public
geographic utilities (`unwrap_longitude`, `minimal_longitude_interval`,
`bounds_for_rings`) remain useful independently and retain their tested API.
See [data provenance](../assets/geographic_map/README.md) for the dataset source
and license; this document describes the implementation, not the dataset.
