# FieldKit production — files that live on the server, not in git

*Written 2026-10-19 during the documentation audit (D-112). The git checkout is
`~/docker/fieldkit-prod/fsm-system/`; everything below sits in or around its
parent, `~/docker/fieldkit-prod/`, on ubuntu-business and is **not** under version
control. If you change one of these, update this doc (and the mirror noted below)
in the same sitting.*

## Layout

```
~/docker/fieldkit-prod/
├── docker-compose.yml   live compose file — mirrored at phase1/fieldkit_backend/docker-compose.yml
├── Dockerfile           build file for the app image (contents below)
├── .env                 secrets — NEVER copy into the repo
├── init/                postgres first-boot scripts (01_create_databases.sql, 02_apply_schema.sh, schema/)
├── uploads/             customer documents written by the app (see "Uploads" below)
├── maps/                sales-map basemap (tiles, fonts, icons); see "Maps" below
└── fsm-system/          this git checkout (bind-mounted into the app container)
```

## docker-compose.yml

Mirrored verbatim (plus a header comment) at
`phase1/fieldkit_backend/docker-compose.yml`. Until 2026-10-19 that mirror was
stale — it still showed port 3100 and lacked the uploads mount added for migration
030 on 2026-10-01. Key facts:

- `app` publishes **3000 → 5001**; `db` is `postgres:16`, internal only.
- Code is bind-mounted (`./fsm-system/phase1/fieldkit_backend:/app`), so
  `docker compose restart app` picks up `.py`/`.html` edits; rebuild only after
  Dockerfile/requirements changes (CLAUDE.md).
- `UPLOAD_DIR=/data/uploads`, mounted from `./uploads`.
- The DB superuser is **`fieldkit`**, not `postgres`:
  `docker compose exec -T db psql -U fieldkit -d fieldkit_getagrip`.

## Dockerfile

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY fsm-system/phase1/fieldkit_backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY fsm-system/phase1/fieldkit_backend/ .
RUN mkdir -p static/img
EXPOSE 5001
CMD ["python", "-m", "gunicorn", "--bind", "0.0.0.0:5001", "--workers", "2", "app:app"]
```

## .env (key names only)

`DB_PASSWORD`, `FLASK_SECRET_KEY`, `RESEND_API_KEY`, `RESEND_FROM_EMAIL`,
`APP_BASE_URL`. Values stay on the server.

## Uploads

```
uploads/<company_key>/wo<id>_<random>.pdf          signed occupied-release forms (migration 030)
uploads/<company_key>/sales/visit<id>_<random>.jpg  business-card photos (migrations 032/037)
```

The DB holds metadata only; file names are always app-generated. "Removing" a form
or photo is a soft delete that leaves the file on disk, by design. As of
2026-10-19: 3 files, 6.8 MB, all Get a Grip — real customer documents.

Included in the nightly backup since 2026-10-19 (see below).

## Maps

`maps/` holds the self-hosted basemap for the sales map (D-118), mounted read-only
into the app at `/data/maps` (`MAP_DIR`). It's built from OpenStreetMap by
`fsm-system/ops/maps/refresh-basemap.sh`: `overview.pmtiles` (SE US, zoom 0–9),
`detail.pmtiles` (the regions in `ops/maps/regions.geojson`, full street detail),
`assets/` (label fonts and icons), `regions.geojson` (copied for the app),
`VERSION` (the planet build date) and `bin/pmtiles` (the cutting tool, checksum-pinned).
About 570 MB. Cron refreshes it quarterly (log: `~/logs/fieldkit-basemap.log`).
**Not backed up**: it's entirely regenerable by re-running the script (about a
minute). To change coverage, edit `regions.geojson` and re-run.

## Backups

Nightly since 2026-10-19: all four DBs, uploads and server config go to
`~/backups/fieldkit/` at 07:15 UTC. **Full detail, restore steps and the homelab
pull setup are in `backups.md`.** The off-box copy (the NAS pull) isn't set up yet.
The older manual dumps under `~/db-backups/` are left as they are.

## Cron

Four `jobs.py` entries under the `letize` user's crontab, logging to
`~/logs/fieldkit-jobs.log`; full detail in `cron-jobs.md`. A fifth entry
(07:15 UTC) runs the nightly backup, logging to `~/logs/fieldkit-backup.log`.
Two more (D-118): `jobs.py geocode` nightly at 06:30 UTC, placing map pins for new
or edited addresses (log: `fieldkit-jobs.log`), and the basemap refresh at 05:10
UTC on the 1st of January, April, July and October.
