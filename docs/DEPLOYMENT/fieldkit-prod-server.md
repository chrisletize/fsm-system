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

**This folder is not backed up by anything**, and neither is the database on a
schedule (see below).

## Backups

Manual, ad hoc, under `~/db-backups/<date-reason>/`, taken before risky changes.
The latest is `2026-09-23-clear-catalog-descriptions`. **No backup has been taken
since then**, although migrations 029–038 have been applied to production and the
Sales CRM is now in real daily use (50 prospects / 48 visits at Get a Grip). There
is no scheduled `pg_dump` in cron. Open item — see CURRENT-STATUS.

## Cron

Four `jobs.py` entries under the `letize` user's crontab, logging to
`~/logs/fieldkit-jobs.log`. Full detail in `cron-jobs.md` (unchanged since
2026-09-19; still accurate as of 2026-10-19).
