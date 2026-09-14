# CLAUDE.md

FieldKit is a custom Field Service Management (FSM) platform replacing ServiceFusion
for four service companies. This file orients any Claude session working in this repo.
Deeper reference material lives in `docs/` — see the pointer table at the bottom.

## Architecture: one database per company, no `company_id` column

Each company gets a fully separate PostgreSQL database. There is no shared `customers`
table filtered by `company_id` — cross-company data contamination is structurally
impossible because there's no shared table to contaminate.

    fieldkit_getagrip           Get a Grip Charlotte
    fieldkit_kleanit_charlotte  Kleanit Charlotte
    fieldkit_cts                CTS of Raleigh
    fieldkit_kleanit_sf         Kleanit South Florida

The `company_key` segment in the URL (`/getagrip/...`, `/kleanit_charlotte/...`)
selects which database the route connects to (`DB_CONFIG` in
`phase1/fieldkit_backend/app.py`). A schema migration must be applied to all four
databases — applying it to one and forgetting the rest is the most common source of
"works for one company, 500s for another" bugs. Never add a `company_id` column as a
shortcut; if you find yourself wanting one, you're probably solving the wrong problem.

## Docker: bind-mount vs baked-in — check before you restart or rebuild

This repo's backend (`phase1/fieldkit_backend`, deployed via
`/home/letize/docker/fieldkit-prod/docker-compose.yml`) bind-mounts its code:

    volumes:
      - ./fsm-system/phase1/fieldkit_backend:/app

Host edits to `.py`/`.html` are visible inside the container immediately, but
gunicorn compiles Python/Jinja into memory at worker boot and won't re-read disk
mid-request. So for this repo:

    docker compose restart app        # .py / .html edits — sufficient
    docker compose up -d --build app  # only after Dockerfile / requirements.txt changes

**The sibling `statements` project (`~/docker/statements/`) is the opposite.** Its
Dockerfile does `COPY fsm-system/ .` at build time and mounts only `/tmp` upload
dirs — no code bind-mount. A bare restart there silently keeps serving the last
built image. For statements, always:

    docker compose up -d --build app

Don't assume one project's rule applies to the other — check the target
`docker-compose.yml` for a code bind-mount before choosing restart vs. rebuild.

## Drift-check before trusting "it should be fixed"

Code has three copies that can silently diverge: git, the host filesystem, and the
running container. Before spending time debugging "why doesn't my fix show up,"
verify the chain is intact instead of guessing:

- Is the host checkout current with git? (`git status`, `git log`)
- Does the container's file match the host's? (`md5sum` both, or `docker exec ... md5sum`)
- Did the container actually restart/rebuild after the last edit? (worker start time vs. file mtime)

Full drift-check script and the debugging decision tree (unreachable site / 500 error /
wrong content / wrong data) are in `docs/FIELDKIT_STACK_REFERENCE.md` sections 3 and 5.

## Route decorator order

Every company-scoped route stacks decorators in this exact order:

    @app.route('/<company_key>/customers/<int:customer_id>/edit', methods=['GET', 'POST'])
    @login_required
    @company_access_required
    @with_branding
    def customer_edit(company_key, customer_id, branding, all_companies, company_access):
        ...

- `login_required` — must have a session (`user_id` in `session`), else redirect to `/login`.
- `company_access_required` — `company_key` must be a real key (else 404) and must be
  in the logged-in user's `session['company_access']` list (else 403).
- `with_branding` — injects `branding`, `all_companies`, `company_access` kwargs for
  templates (colors, logo, company switcher). Only needed on routes that render a
  full page: API/JSON endpoints (e.g. `customers_search`, `add_note`) skip it.

All three are defined together in `phase1/fieldkit_backend/app.py`. Keep the order —
branding depends on `company_key` having already been validated.

## Database naming and connections

Company key → database name mapping (`DB_CONFIG` in `app.py`):

    'getagrip':           'fieldkit_getagrip'
    'kleanit_charlotte':  'fieldkit_kleanit_charlotte'
    'cts':                'fieldkit_cts'
    'kleanit_sf':         'fieldkit_kleanit_sf'

`get_db_connection(company_key)` opens a fresh `psycopg2` connection per call — no
ORM, no connection pool, raw SQL throughout. This is deliberate: cash-basis tax
compliance logic needs to match the exact SQL being executed, not whatever an ORM
generates. Don't introduce an ORM.

Note: the `users` table (auth) lives only in the `fieldkit_getagrip` database — it's
the de facto shared/admin database for login, not per-company.

## Soft delete, everywhere

No table does a hard `DELETE`. Every table carries the same audit + soft-delete
columns (see `docs/DATABASE-SCHEMA.md`):

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(100),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_by VARCHAR(100),
    deleted_at TIMESTAMP NULL,   -- NULL = active, timestamp = soft-deleted
    deleted_by VARCHAR(100)

Every `SELECT` that lists rows for the UI must filter `WHERE deleted_at IS NULL`.
"Deleting" a row means setting `deleted_at`/`deleted_by`, never removing it.

## Where the real docs live

This file is a map, not the territory. For anything deeper:

| Topic | File |
|---|---|
| Infra request flow, debugging decision tree, drift-check script, incident case study | `docs/FIELDKIT_STACK_REFERENCE.md` |
| Full architecture rationale (why 4 DBs, auth, roles, sales system) | `docs/ARCHITECTURE.md` |
| Complete table-by-table schema | `docs/DATABASE-SCHEMA.md` |
| Infra inventory, company list, people, current-as-of snapshot | `docs/FIELDKIT_PROJECT_REFERENCE.md` |
| Day-to-day working process (read-before-edit, curl-before-frontend, nano for multi-line edits) | `docs/DEVELOPMENT_WORKFLOW.md` |
| Sales CRM / prospect pipeline design | `docs/SALES-SYSTEM.md` |
| Design addenda (catalog/equipment, worksite/double-booking, duration/rating, mobile after-hours extraction, reconciliation framework) | `docs/FIELDKIT_DESIGN_ADDENDUM_*.md` |
| Full v2 system design | `docs/FIELDKIT_COMPLETE_SYSTEM_DESIGN_v2.md` |
| Session-by-session history | `docs/FIELDKIT_SESSION_*.md`, `docs/SESSION_NOTES_*.md`, `docs/PROJECT-KNOWLEDGE/` |
| Reusable patterns extracted from past sessions | `docs/FIELDKIT_REUSABLE_BRICKS.md` |
