#!/usr/bin/env bash
# FieldKit nightly backup -- runs ON ubuntu-business (VLAN70 DMZ) from cron.
#
# Writes a self-contained, verified snapshot to $DEST_ROOT/daily/<UTC stamp>/:
#   <db>.dump            pg_dump custom format, one per company DB (pg_restore-able)
#   globals.sql          roles (pg_dumpall --globals-only)
#   uploads.tar.gz       ~/docker/fieldkit-prod/uploads (release forms, card photos)
#   server-config.tar.gz docker-compose.yml, Dockerfile, init/  (NOT .env -- secrets)
#   MANIFEST             git commit, sizes, table counts per DB
#   SHA256SUMS           checksums of everything above
#
# The snapshot is built in .incomplete-<stamp>/ and only renamed into daily/
# once every dump has passed `pg_restore --list`, so anything under daily/ is
# complete. The DMZ can't reach the LAN, so off-box copies are PULLED from the
# homelab side (rsync over a read-only rrsync key) -- see
# docs/DEPLOYMENT/backups.md. Keeps the newest $KEEP snapshots locally.

set -euo pipefail
umask 077

DEPLOY=/home/letize/docker/fieldkit-prod
DEST_ROOT=${FIELDKIT_BACKUP_ROOT:-/home/letize/backups/fieldkit}
KEEP=${FIELDKIT_BACKUP_KEEP:-14}
DBS=(fieldkit_getagrip fieldkit_kleanit_charlotte fieldkit_cts fieldkit_kleanit_sf)

STAMP=$(date -u +%Y-%m-%dT%H%MZ)
WORK="$DEST_ROOT/.incomplete-$STAMP"
FINAL="$DEST_ROOT/daily/$STAMP"

log() { echo "[$(date -u +%FT%TZ)] $*"; }

on_error() {
    log "FAILED (line $1) -- snapshot left at $WORK for inspection"
    date -u +%FT%TZ > "$DEST_ROOT/last-failure"
}
trap 'on_error $LINENO' ERR

mkdir -p "$WORK" "$DEST_ROOT/daily"
cd "$DEPLOY"

dc() { docker compose exec -T db "$@"; }

log "backup $STAMP starting -> $WORK"

for db in "${DBS[@]}"; do
    dc pg_dump -U fieldkit -Fc -d "$db" > "$WORK/$db.dump"
    # A truncated or corrupt custom-format dump fails --list, so this is the
    # cheap "can this actually be restored" check on every run.
    dc pg_restore --list < "$WORK/$db.dump" > /dev/null
    log "  $db: $(du -h "$WORK/$db.dump" | cut -f1), verified"
done

dc pg_dumpall -U fieldkit --globals-only > "$WORK/globals.sql"
tar -C "$DEPLOY" -czf "$WORK/uploads.tar.gz" uploads
tar -C "$DEPLOY" -czf "$WORK/server-config.tar.gz" docker-compose.yml Dockerfile init

{
    echo "snapshot:   $STAMP"
    echo "host:       $(hostname)"
    echo "git commit: $(git -C "$DEPLOY/fsm-system" rev-parse HEAD)"
    echo "uploads:    $(find "$DEPLOY/uploads" -type f | wc -l) files"
    for db in "${DBS[@]}"; do
        echo "$db: $(dc psql -U fieldkit -d "$db" -Atc \
            "select count(*) from information_schema.tables where table_schema='public'") tables"
    done
} > "$WORK/MANIFEST"

(cd "$WORK" && sha256sum -- *.dump globals.sql uploads.tar.gz server-config.tar.gz MANIFEST > SHA256SUMS)

mv "$WORK" "$FINAL"
ln -sfn "daily/$STAMP" "$DEST_ROOT/latest"
date -u +%FT%TZ > "$DEST_ROOT/last-success"
log "snapshot complete: $FINAL ($(du -sh "$FINAL" | cut -f1))"

# Retention: keep the newest $KEEP snapshots. Names are UTC stamps, so a
# plain sort is chronological. Only touches names matching the stamp format.
mapfile -t old < <(find "$DEST_ROOT/daily" -mindepth 1 -maxdepth 1 -type d \
    -regextype posix-extended -regex '.*/[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{4}Z' \
    -printf '%f\n' | sort | head -n -"$KEEP")
for d in "${old[@]}"; do
    rm -rf -- "${DEST_ROOT:?}/daily/$d"
    log "  pruned $d"
done

# Stale .incomplete dirs from earlier failed runs (older than 2 days).
find "$DEST_ROOT" -mindepth 1 -maxdepth 1 -type d -name '.incomplete-*' -mtime +2 \
    -exec rm -rf -- {} +

log "done"
