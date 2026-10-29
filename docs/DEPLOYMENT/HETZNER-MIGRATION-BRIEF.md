# Brief for Fable: plan FieldKit's move to Hetzner

*Written 2026-10-29 by the Claude Code session working on FieldKit, after a long
discussion with Chris. Everything below was checked against the live server that day
unless marked otherwise.*

---

## Your job

Write a **step-by-step migration plan** that a Claude Code session can carry out,
moving FieldKit production off Chris's homelab onto a Hetzner Cloud server. **Plan
only; don't run anything.**

Chris is paying for your judgment, not your typing. What he wants most:

- **Order-of-operations traps.** Steps that break something if done in the wrong
  order, things that silently stop working (cron, email links, backups, sessions,
  geocoding), and anything that only fails days later.
- **Plan changes, if needed.** If a decision below is wrong or risky, say so plainly
  and propose the alternative. Don't quietly work around it.
- **Clear ownership.** Steps only Chris can do (Hetzner console, payment, Cloudflare
  dashboard, NPM on the homelab, anything needing his password) are marked as his.
  The rest belong to the Claude session.

### What the plan must look like

- Phases, each with numbered steps. For every step:
  - **where** it runs: the build VM, the Hetzner server, ubuntu-services, or Chris
    in a web console;
  - **what** to do, with exact commands where possible;
  - **how to verify** it worked;
  - **how to undo** it if needed.
- **Checkpoints** where the session stops and waits for Chris's OK. At minimum: before
  spending money, before the rehearsal restore, before cutover, and before
  decommissioning anything at home.
- A **rehearsal** (full restore onto Hetzner and test) well before the real cutover.
- A **cutover runbook** for the night itself: short, numbered, with a time estimate
  and a go/no-go point.
- A **rollback plan:** how to go back to the homelab within minutes if cutover goes
  wrong, and the point after which rollback means losing new data.
- **Post-cutover cleanup:** turning ubuntu-business into the build VM, repointing
  backups, and updating docs.
- At the end, the **questions you need Chris to answer**, and the **risks you see**
  ranked by how much they'd hurt.

### Also read: the homelab side

Chris will give you `HOMELAB-CONTEXT-FOR-FIELDKIT-MIGRATION.md`, written by the homelab
project's Claude session. It covers Cloudflare, NPM, OPNsense, Tailscale ACLs, the NAS
pull, Proxmox, Pushover and his existing Hetzner footprint. Where it and this brief
disagree about the homelab, trust that file. If you don't have it, ask for it before
planning any step that touches the homelab.

### Read these first (all in the `chrisletize/fsm-system` repo)

| File | Why |
|---|---|
| `CLAUDE.md` | how the code is laid out, and the rules for working in it |
| `docs/PROJECT-KNOWLEDGE/CURRENT-STATUS.md` | what's built, open items, "Decisions 2026-10-29" |
| `docs/DEPLOYMENT/fieldkit-prod-server.md` | every server-only file: compose, Dockerfile, `.env` keys, uploads, maps |
| `docs/DEPLOYMENT/backups.md` and `ops/backup/fieldkit-backup.sh` | backups as they work today |
| `docs/DEPLOYMENT/cron-jobs.md` | scheduled jobs |
| `docs/FIELDKIT_STACK_REFERENCE.md` | how a request travels today, and debugging notes |
| `ops/maps/refresh-basemap.sh` | how the sales-map basemap is built |
| `docs/MOBILE-APP-PLAN.md` §4 | server needs coming soon (API, photos, push) |
| `docs/FIELDKIT_DESIGN_ADDENDUM_ai-assistant.md` §3 | a home AI machine that will connect to production |

---

## What FieldKit is, and how much it matters right now

FieldKit is a custom Flask/PostgreSQL field-service app replacing ServiceFusion for
four companies run by the same owners: Get a Grip Charlotte, Kleanit Charlotte, CTS of
Raleigh and Kleanit South Florida.

- **Not fully live yet:** the office still runs on ServiceFusion.
- **Real data already in it:**
  - **Sales:** the salesman (Chris O) has logged real prospects and visits daily since
    2026-09-30, mostly from a tablet in the field;
  - **Invoices:** 268 real open invoices ($179,521.14) imported for Get a Grip;
  - **Customers:** about 5,300 across the four companies;
  - **Uploads:** signed release forms and business-card photos.
- **Speed matters most** (Chris's words: smooth running is always the number one
  goal). But until office go-live, short downtime is tolerable, and sales use doesn't
  need to be instant.
- **Why move now:** a home power outage this week would have taken FieldKit down. The
  homelab chain (ISP → OPNsense → NPM → VM) has four single points of failure.

## How it runs today (verified 2026-10-29)

**Request path:** browser → Cloudflare (proxied DNS, TLS) → home WAN → OPNsense NAT →
Nginx Proxy Manager on ubuntu-services (10.83.30.10, VLAN30) → **ubuntu-business**
(10.83.70.10, VLAN70 DMZ) port 3000 → Docker.

**ubuntu-business:** Proxmox VM, Ubuntu, 4 vCPU, 7.7 GB RAM (about 1 GB used), 53 GB
disk (13 GB used), timezone UTC. Runs Tailscale (`100.86.23.68`, named
`ubuntu-business`). Because it's in the DMZ, **it can't reach any LAN address**. The
homelab reaches into it, never the other way round.

**Production stack:** `~/docker/fieldkit-prod/`, user `letize`.

- **`docker-compose.yml`:**
  - `db`: `postgres:16`, named volume `pgdata`, healthcheck, superuser **`fieldkit`**
    (not `postgres`), first-boot scripts from `./init/`.
  - `app`: built from `./Dockerfile` (python:3.11-slim, gunicorn, 2 workers, port
    5001), published as **3000:5001**.
- **The code is bind-mounted**, not copied into the image:
  `./fsm-system/phase1/fieldkit_backend:/app`. `./fsm-system` is the git checkout.
  Editing `.py`/`.html` needs `docker compose restart app`, because gunicorn keeps
  code in memory. A rebuild is only needed when the Dockerfile or `requirements.txt`
  changes.
- **Other mounts:** `./uploads:/data/uploads` (real customer documents, 7 MB, outside
  git on purpose) and `./maps:/data/maps:ro` (sales-map basemap, 570 MB, can be
  regenerated).
- **`.env`** holds `DB_PASSWORD`, `FLASK_SECRET_KEY`, `RESEND_API_KEY`,
  `RESEND_FROM_EMAIL` (an `@cletize.com` address) and `APP_BASE_URL`
  (`https://fieldkit.cletize.com`).
- **Four databases**, one per company, all in the one Postgres:
  `fieldkit_getagrip` 23 MB, `fieldkit_kleanit_charlotte` 21 MB, `fieldkit_cts` 14 MB,
  `fieldkit_kleanit_sf` 15 MB. **Logins are read only from `fieldkit_getagrip.users`.**
- **Python packages:** Flask 3.0, psycopg2-binary, bcrypt, gunicorn 21.2, resend,
  reportlab, openpyxl, python-dotenv.

**Cron** (the `letize` user's crontab, UTC). Everything except the backup and the
basemap runs as `cd ~/docker/fieldkit-prod && docker compose exec -T app python jobs.py <job>`:

| When (UTC) | Job |
|---|---|
| 01:00 daily | `nightly` (customer flags, extraction day counts, ratings) |
| every 15 min | `uninvoiced` |
| 17:00 Mon–Fri | `eod_escalation` |
| 08:00 Mon | `weekly_sales_report` |
| 06:30 daily | `geocode` (calls the **US Census geocoder** at `geocoding.geo.census.gov`) |
| 07:15 daily | `ops/backup/fieldkit-backup.sh` |
| 05:10 on 1 Jan/Apr/Jul/Oct | `ops/maps/refresh-basemap.sh` (downloads from the internet) |

All job logs go to `~/logs/`. The **scheduled email alerts are switched off** for all
four companies (`company_settings.scheduled_alerts_enabled`). The jobs still compute,
they just don't email anyone.

**Email:** sent through Resend (live API key). Links in emails are built from
`APP_BASE_URL`. **The Resend key is real and the databases hold real customer email
addresses. Any environment holding that key can email real customers.**

**Backups today:**

- **Local snapshot:** `fieldkit-backup.sh` runs at 07:15 UTC and writes a verified
  snapshot to `~/backups/fieldkit/daily/<stamp>/`, keeping the newest 14 (about 9 MB
  each). Contents:
  - a `pg_dump -Fc` of each company database, checked with `pg_restore --list`;
  - `globals.sql`;
  - `uploads.tar.gz`;
  - `server-config.tar.gz`;
  - `MANIFEST` and `SHA256SUMS`;
  - a `last-success` stamp file.

  `.env` is left out on purpose.
- **NAS copy:** ubuntu-services pulls the snapshot at 07:45 UTC using a key restricted
  by `rrsync -ro` to that one folder. It writes to the NAS, checks the checksums,
  refuses snapshots older than 36 hours, and sends a Pushover alert on failure.
- **Whole-VM backup:** Proxmox backs up the VM to the NAS weekly.
- **No off-site copy:** the off-site machine (LetizeRemote) is powered off.

**The statements site** ("Phase 0"): `~/docker/statements/`, port 3100, its own
Postgres (`fsm_prod`). Michele uses it daily for statements and tax work. **It stays on
the homelab**; don't migrate it. One known link to FieldKit:
`phase1/fieldkit_phase1/import_job_dates.py` reads the statements database by
attaching the FieldKit container to the `statements_default` Docker network. That
import is on hold. Once production is on Hetzner it would need another route, such as
running against a dump.

**Development so far:** Claude Code sessions have edited production directly on
ubuntu-business. That ends with this move.

## Decisions already made (2026-10-29)

1. **Hetzner Cloud, at most €30/month.** Chris has used Hetzner for a small monitoring
   VM and likes the company. He assumed Hetzner was Europe-only. Hetzner Cloud also
   has **US locations (Ashburn VA, Hillsboro OR)**, and Ashburn is closest to the
   users in NC and FL. **Verify the current US server types, included traffic and
   prices yourself, and recommend a size.** The present load is tiny.
2. **Cloudflare Tunnel** in front of production, with no inbound ports open. SSH only
   over **Tailscale**, which Chris already runs everywhere.
3. **Keep the Docker Compose stack as it is:** Postgres 16 in a container, the same
   layout. Hetzner has no managed Postgres, and HA/failover would be overkill at this
   size.
4. **Cutover:** rehearse first, then on the night stop the app, take a final backup,
   restore on Hetzner and switch traffic. Minutes of downtime, late at night.
5. **ubuntu-business becomes the "build" VM.** Development continues there. Production
   is deployed **through git**, and **Chris confirms every production deploy** (Claude
   prepares and tests, Chris says "deploy"). No more editing production in place.
6. **A dev/test environment on the build VM** with its own address, running a copy of
   production data. **It must not be able to send email.** Use no real Resend key (or
   a send-blocking stub) and consider rewriting customer emails to `.invalid`.
   - **Cloudflare limit:** Cloudflare's free certificate only covers one level of
     subdomain (`*.cletize.com`), so `dev.fieldkit.cletize.com` won't work.
   - **Leading option:** keep dev private to Tailscale (e.g. `tailscale serve` on the
     build VM, which also gives HTTPS), with nothing public.
   - **Fallback:** a one-level name like `fieldkit-dev.cletize.com` behind Cloudflare
     Access, if non-Tailscale users ever need it. Recommend one.
7. **Backups after the move.** The production server makes the nightly snapshot
   (reuse `fieldkit-backup.sh`), and there must be:
   - **an off-site copy at Hetzner:** Storage Box or object storage, ideally a
     different location from the server;
   - **a copy on the homelab NAS,** with the homelab pulling, in keeping with
     "nothing reaches into the house". Work out how ubuntu-services reaches the
     Hetzner server (Tailscale is the obvious path) and keep the restricted
     `rrsync -ro` key pattern;
   - **the same Pushover staleness alerting.**

   Also say whether Hetzner's own server backups (snapshot add-on) are worth it.
8. **Monitoring that doesn't exist yet:**
   - an **uptime check** on the public URL;
   - a **"backup is stale" alert**;
   - a **disk-usage alert when the server reaches 60–75% full**, so storage gets
     upgraded ahead of time.

   Chris already uses Pushover. Something small and free is preferred.
9. **Photos will grow.** The mobile app (not built yet) will add thousands of job
   photos a year. **They're kept 26 months, then deleted** (24-month warranty plus
   margin). Size the disk and backups, and say when the server needs a volume upgrade.
10. **ServiceFusion imports** for the other three companies happen **after** the move.
    Card payments are on hold. **The statements site stays home.**
11. **Coming later; don't block it:** a JSON API and push notifications for a mobile
    app, built from a Mac mini on Tailscale (`get-a-grip-mac`, 100.105.68.75), and a
    **home AI machine** that connects *out* to production over Tailscale and keeps a
    **read-only Postgres replica** of the four databases. The new server's networking
    and Postgres setup should leave room for both.

## Traps we already know about (check them, and find the ones we missed)

- **`FLASK_SECRET_KEY` must move unchanged.** A new key logs everyone out and breaks
  any outstanding password-reset links.
- **Dev must never hold the real `RESEND_API_KEY`.** Check that every email path
  (invoice send, statements, scheduled alerts, sales emails, password reset, the
  manager-confirmation emails) is dead on dev.
- **Rehearsal restore:** keep Resend disabled on Hetzner until cutover too, or a
  test click could email a customer from the restored copy.
- **During the rehearsal, cron mustn't run on two production servers at once.**
  Duplicate `uninvoiced`/`nightly` runs write duplicate rows and, once alerts are
  switched on, would send duplicate emails.
- **After cutover the old production stack must be stopped for good** (not just left
  running unreachable), so nobody writes to the stale copy. That includes Chris O's
  tablet, which may be caching the old route.
- **Cutover traffic:** the existing NPM proxy entry and Cloudflare DNS record for
  `fieldkit.cletize.com` have to be replaced by the tunnel. Plan the order so there's
  no window where the hostname points nowhere, or at the wrong server.
- **Hard-coded paths:** `/home/letize/...` appears in cron, the backup script and the
  docs. Either keep the same user and paths on Hetzner, or list every place to change.
- **Basemap:** `maps/` (570 MB) isn't in backups. It's rebuilt by
  `refresh-basemap.sh` on the new server, so check that it runs there.
- **Geocoding:** the Census geocoder must be reachable from the new server.
- **Uploads:** must keep their ownership and permissions so the container can write
  there.
- **Postgres version:** the dumps are from Postgres 16. Restore into the same major
  version.
- **Roles:** `globals.sql` holds the roles, including the `fieldkit` superuser and
  its password. Make sure it matches the new `.env`.
- **Timezone:** the jobs assume the host is on UTC. The cron times are in UTC on
  purpose, while the business runs on US Eastern time.
- **Mobile users and sessions:** sales uses the app from phones and tablets on
  cellular. Plan the cutover for a time Chris O isn't working, and expect to ask him
  to log in again if anything about the session cookie changes.
- **Auto-mode safety check:** Claude Code's automatic safety check blocks production
  actions (restarts, deploys) on this VM unless Chris approves them. Plan for Chris
  running those steps himself or approving them as they come.
- **Tidy up at the end:**
  - retire the NAS pull from ubuntu-business, but keep pulling the build VM's own
    files if useful;
  - update the Proxmox VM backup scope;
  - remove the old NPM entry;
  - update `FIELDKIT_STACK_REFERENCE.md`, `fieldkit-prod-server.md`, `backups.md`,
    `cron-jobs.md`, `CLAUDE.md` and `CURRENT-STATUS.md`.
- **Deploy mechanism:** recommend a specific design. Some questions to answer:
  - Does production keep bind-mounting a git checkout and run `git pull` plus
    restart?
  - Or does it build images?
  - How are migrations, which are hand-applied SQL files run against all four
    databases, part of a deploy?
  - What's the rollback for a bad deploy?
  - How does the build VM reach production? Over Tailscale only, and with what key?
- **Dev data refresh:** how dev gets a fresh copy of production data, scrubbed of
  anything that could email or charge anyone.

## People and access

- **Chris (admin):** owns everything. He does anything that needs a password, a
  payment or a dashboard.
- **Users:** about 8 so far. Roles are one per user and apply to every company the
  user can access. Michele, Chris and others are admins or managers across all four.
- **Approval:** Chris approves each checkpoint. The executing session never spends
  money, changes DNS or touches the homelab without his explicit OK at that step.
