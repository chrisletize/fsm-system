# Vendored front-end libraries

Copied in from npm so pages don't depend on a third-party CDN at runtime. Each
tarball was checked against the npm registry's `dist.integrity` (sha512) before
the files were copied. Upgrade by replacing the folder (keep the version in the
folder name) and updating the `<script>`/`import` paths that reference it.

| Folder | Package | Version | Published | License | Used by |
|---|---|---|---|---|---|
| `maplibre-gl-6.12.0/` | `maplibre-gl` (dist: `.mjs` + shared + worker + css) | 6.12.0 | 2026-10-03 | BSD-3-Clause (`LICENSE.txt`) | Sales map (D-118) |
| `pmtiles-4.5.0/` | `pmtiles` (`dist/pmtiles.js`, IIFE global `pmtiles`) | 4.5.0 | 2026-08-10 | BSD-3-Clause | Sales map |
| `protomaps-basemaps-5.7.2/` | `@protomaps/basemaps` (`dist/basemaps.js`, IIFE global `basemaps`) | 5.7.2 | 2026-03-10 | BSD-3-Clause | Sales map |

The three maplibre `.mjs` files must stay together in one folder:
`maplibre-gl.mjs` imports `./maplibre-gl-shared.mjs` and starts its web worker
from `./maplibre-gl-worker.mjs`, resolved relative to its own URL.

Map data itself (tiles, fonts, icons) is **not** in the repo. It's built on the
server by `ops/maps/refresh-basemap.sh` into `~/docker/fieldkit-prod/maps/`.
