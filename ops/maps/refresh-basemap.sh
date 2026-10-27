#!/usr/bin/env bash
# Refresh the self-hosted basemap for the sales map (D-118). Runs on
# ubuntu-business; cron runs it quarterly so new roads appear.
#
# Produces, in $MAP_ROOT (default ~/docker/fieldkit-prod/maps, mounted into
# the app container at /data/maps):
#   overview.pmtiles   SE US, zoom 0-9 (what you see zoomed out)
#   detail.pmtiles     ops/maps/regions.geojson at full street detail (zoom 0-15)
#   assets/fonts/...   label fonts      } from protomaps/basemaps-assets,
#   assets/sprites/... map icons        } only fetched if missing
#   VERSION            which planet build these came from
#
# Source: the daily Protomaps planet build (OpenStreetMap data, ODbL). The
# pmtiles tool reads only the byte ranges our area needs, never the ~140 GB
# planet. New files are built under .incoming/ and moved into place only when
# both extracts succeed, so the live map never sees a half-written file.

set -euo pipefail

REPO=/home/letize/docker/fieldkit-prod/fsm-system
MAP_ROOT=${MAP_ROOT:-/home/letize/docker/fieldkit-prod/maps}
REGIONS=$REPO/ops/maps/regions.geojson
PMTILES_VERSION=1.31.2
# sha256 of go-pmtiles_${PMTILES_VERSION}_Linux_x86_64.tar.gz, from GitHub's asset digest
PMTILES_SHA256=3ed7dbf4ec2e6dfe5e25b6f70d1ffc932729f93c86db353bf514dd71010a312f
OVERVIEW_BBOX="-92.0,24.0,-75.0,37.5"
OVERVIEW_MAXZOOM=9

log() { echo "[$(date -u +%FT%TZ)] $*"; }

mkdir -p "$MAP_ROOT/bin" "$MAP_ROOT/.incoming" "$MAP_ROOT/assets"
PMTILES=$MAP_ROOT/bin/pmtiles

if [ ! -x "$PMTILES" ] || ! "$PMTILES" version 2>/dev/null | grep -q "$PMTILES_VERSION"; then
    log "installing pmtiles $PMTILES_VERSION"
    tmp=$(mktemp -d)
    curl -sSL --max-time 300 -o "$tmp/p.tgz" \
        "https://github.com/protomaps/go-pmtiles/releases/download/v$PMTILES_VERSION/go-pmtiles_${PMTILES_VERSION}_Linux_x86_64.tar.gz"
    echo "$PMTILES_SHA256  $tmp/p.tgz" | sha256sum -c --quiet
    tar -xzf "$tmp/p.tgz" -C "$tmp" pmtiles
    install -m 0755 "$tmp/pmtiles" "$PMTILES"
    rm -rf "$tmp"
fi

BUILD=$(curl -sSf --max-time 60 https://build-metadata.protomaps.dev/builds.json \
        | python3 -c "import sys,json; print(sorted(b['key'] for b in json.load(sys.stdin))[-1])")
SRC="https://build.protomaps.com/$BUILD"
log "planet build: $BUILD"

"$PMTILES" extract "$SRC" "$MAP_ROOT/.incoming/overview.pmtiles" \
    --bbox="$OVERVIEW_BBOX" --maxzoom=$OVERVIEW_MAXZOOM --quiet
log "overview: $(du -h "$MAP_ROOT/.incoming/overview.pmtiles" | cut -f1)"

"$PMTILES" extract "$SRC" "$MAP_ROOT/.incoming/detail.pmtiles" --region="$REGIONS" --quiet
log "detail: $(du -h "$MAP_ROOT/.incoming/detail.pmtiles" | cut -f1)"

"$PMTILES" verify "$MAP_ROOT/.incoming/overview.pmtiles"
"$PMTILES" verify "$MAP_ROOT/.incoming/detail.pmtiles"
mv -f "$MAP_ROOT/.incoming/overview.pmtiles" "$MAP_ROOT/overview.pmtiles"
mv -f "$MAP_ROOT/.incoming/detail.pmtiles" "$MAP_ROOT/detail.pmtiles"
echo "$BUILD" > "$MAP_ROOT/VERSION"
# The app reads the coverage boxes from here (ops/ is outside its bind mount).
cp "$REGIONS" "$MAP_ROOT/regions.geojson"

# Fonts and icons rarely change; fetch once (delete assets/ to force a refresh).
if [ ! -d "$MAP_ROOT/assets/fonts" ] || [ ! -d "$MAP_ROOT/assets/sprites" ]; then
    log "fetching fonts and sprites"
    tmp=$(mktemp -d)
    curl -sSL --max-time 300 -o "$tmp/a.tgz" https://github.com/protomaps/basemaps-assets/archive/refs/heads/main.tar.gz
    tar -xzf "$tmp/a.tgz" -C "$tmp"
    src=$(find "$tmp" -maxdepth 1 -type d -name 'basemaps-assets-*' | head -1)
    mkdir -p "$MAP_ROOT/assets/fonts" "$MAP_ROOT/assets/sprites"
    for f in "Noto Sans Regular" "Noto Sans Medium" "Noto Sans Italic"; do
        cp -r "$src/fonts/$f" "$MAP_ROOT/assets/fonts/"
    done
    cp -r "$src/sprites/v4" "$MAP_ROOT/assets/sprites/"
    rm -rf "$tmp"
fi

log "done: $(du -sh "$MAP_ROOT" | cut -f1) total in $MAP_ROOT"
