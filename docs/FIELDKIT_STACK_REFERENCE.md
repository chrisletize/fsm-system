# FieldKit — Stack Reference & Debugging Playbook

**Purpose:** Give any future session (human or AI assistant) a fast mental map of how FieldKit is built, where each piece lives, and how to diagnose common classes of failure. Written April 21, 2026 after a six-hour debugging session that turned out to be a gunicorn stale-worker issue — not a code bug.

**Audience:** Chris (returning to the project), future Claude/Sonnet sessions picking up mid-build, Mike or other stakeholders wanting context.

---

## 1. The request flow, end to end

When someone visits `fieldkit.cletize.com/getagrip/customers/1167/edit`, here is every hop their request makes. Each tool does one job. Knowing where each one ends and the next begins is the entire key to debugging this system.

```
Browser
   ↓ HTTPS
Cloudflare              ← hides home IP, handles TLS, DDoS protection
   ↓
OPNsense (LetizeGate)   ← NAT, VLAN routing, firewall rules
   ↓
NPM (ubuntu-services)   ← hostname → backend port mapping, wildcard SSL cert
   ↓
Docker (ubuntu-business)← container runtime, isolates the app
   ↓
Gunicorn                ← Python web server; workers hold compiled code in RAM
   ↓
Flask                   ← URL → route function
   ↓
psycopg2 → PostgreSQL   ← SQL driver talks to the database container
   ↓
Jinja2                  ← combines template + data into final HTML
   ↓
(response flows back up the same stack)
```

Total round trip: under 100ms. Each hop is its own potential failure point.

---

## 2. What each tool is responsible for

### Cloudflare
DNS + proxy. Public DNS records for `*.cletize.com` resolve to Cloudflare's IPs, not Chris's actual home IP. Cloudflare receives the request, terminates TLS, then forwards to the home WAN IP. Also provides DDoS protection and a dashboard for DNS records.

**When it's the problem:** DNS not resolving, SSL cert errors at the browser, proxy (orange cloud) misconfigured.

### OPNsense (LetizeGate)
Router and firewall. Receives the inbound connection on WAN port 443, uses a NAT port-forward rule to send it to NPM on VLAN30. Also enforces VLAN isolation (VLAN70 DMZ can't reach VLAN20 trusted, etc.) and routes most traffic through AirVPN.

**When it's the problem:** Traffic doesn't reach NPM, firewall rules block a VLAN hop, NAT rule broken, AirVPN tunnel down.

### Nginx Proxy Manager (NPM)
Runs on ubuntu-services (10.83.30.10). One central reverse proxy for the whole homelab. Looks at the `Host:` header (e.g. `fieldkit.cletize.com`) and forwards to the configured backend (10.83.70.10:3000 for Phase 0, :3100 for Phase 1). Handles the wildcard SSL cert for `*.cletize.com` so individual apps don't need their own.

**When it's the problem:** Proxy host missing or misconfigured, SSL cert renewal failed, backend unreachable from NPM (cross-VLAN rule issue).

### Docker
Runs on ubuntu-business (10.83.70.10, VLAN70). The container runtime. Each app is a "stack" defined by a `docker-compose.yml` file. Current stacks:

- `~/docker/fieldkit-prod` — Phase 0 statement generator, port 3000
- `~/docker/fieldkit-staging` — Phase 0 staging, port 3001
- `~/docker/fieldkit-phase1` — Phase 1 (auth + customer module), port 3100

Each stack runs one or more containers. `fieldkit-phase1` has two: `app` (Flask + gunicorn) and `db` (PostgreSQL).

**When it's the problem:** Container not running (`docker ps`), container keeps crashing (`docker compose logs`), volume mount wrong (host file not reaching container), network config wrong.

### Gunicorn
Python WSGI server running inside the app container. Receives HTTP from the outside, hands it to Flask. Runs multiple "worker processes" in parallel for concurrency.

**Critical behavior: workers hold code and templates in memory from the moment they boot.** They do NOT re-read files from disk on each request. Edits to `.py` files or `.html` templates have no effect until workers are restarted.

**When it's the problem:** Workers crashing on boot (SyntaxError in logs), stale code being served after edits (the bug we hit today), worker count too low for load.

### Flask
The Python web framework. Decorators on functions define URL routes (e.g. `@app.route('/<company_key>/customers/<int:customer_id>/edit')`). The function opens a DB connection, runs queries, calls `render_template(...)` with the data, returns the result.

**When it's the problem:** Route not matching URL (404), exception inside the route function (500, see `docker compose logs`), wrong variable passed to template.

### psycopg2 + PostgreSQL
psycopg2 is the Python library that talks to PostgreSQL. PostgreSQL runs in its own container (`fieldkit-phase1-db-1`) with four databases: `fieldkit_getagrip`, `fieldkit_kleanit_charlotte`, `fieldkit_cts`, `fieldkit_kleanit_sf`. Each company is isolated in its own database.

Raw SQL is written directly (no ORM) — chosen deliberately so cash-basis tax compliance logic matches the exact SQL being executed.

**When it's the problem:** Missing table or column (schema migration not applied), wrong database name in connection, permission denied, data missing because migration wasn't run in the right database.

### Jinja2
Flask's templating engine. Templates live in `phase1/fieldkit_backend/templates/`. Syntax:
- `{{ variable }}` — insert a value
- `{% if ... %}` `{% endif %}` — conditional
- `{% for x in list %}` `{% endfor %}` — loop
- `{% extends "base.html" %}` — inherit from base template
- `{% block name %}` — define or override a content block

Templates are compiled to bytecode when the worker boots. Edits don't apply until worker restart (see Gunicorn above).

**When it's the problem:** Variable undefined (`'foo' is undefined` exception), syntax error in `{% %}` block (usually raises an exception), template not found (wrong path or filename).

---

## 3. Where code lives, and which is the source of truth

```
GitHub (chrisletize/fsm-system)
   ↓ git pull
Host filesystem on ubuntu-business
   (~/docker/fieldkit-phase1/fsm-system/)
   ↓ volume mount in docker-compose.yml
Container filesystem
   (/app/)
   ↓ loaded by gunicorn at worker boot
In-memory running code
```

**GitHub is the source of truth.** The host checkout should match GitHub. The container should match the host (via volume mount). The running workers should match the container (via restart).

Any link in this chain can break:
- Git out of sync with host → `git pull` or `git push`
- Host out of sync with container → check volume mounts in `docker-compose.yml`, or `docker cp` to rescue
- Container out of sync with running workers → `docker compose restart app`

**Drift check** — run this whenever debugging feels off, to verify all copies of critical files match:

```bash
cd ~/docker/fieldkit-phase1/fsm-system
for f in phase1/fieldkit_backend/app.py \
         phase1/fieldkit_backend/templates/home.html \
         phase1/fieldkit_backend/templates/customers.html \
         phase1/fieldkit_backend/templates/customer_detail.html \
         phase1/fieldkit_backend/templates/customer_form.html \
         phase1/fieldkit_backend/templates/field_settings.html \
         phase1/fieldkit_backend/templates/base.html \
         phase1/fieldkit_backend/templates/dashboard.html; do
  container_hash=$(docker exec fieldkit-phase1-app-1 md5sum /app/$(echo $f | sed 's|phase1/fieldkit_backend/||') 2>/dev/null | awk '{print $1}')
  host_hash=$(md5sum $f 2>/dev/null | awk '{print $1}')
  if [ "$container_hash" != "$host_hash" ]; then
    echo "DRIFT: $f"
    echo "   container: $container_hash"
    echo "   host:      $host_hash"
  else
    echo "OK:    $f"
  fi
done
```

If any file shows DRIFT, decide which version is correct (usually the container's, if that's where edits were being made), copy it to the other location, commit to git.

---

## 4. Which layer does my edit live at, and what does it take to refresh?

This is the single most useful table in this document. When an edit doesn't appear to take effect, find the row for what you edited and check whether you've taken the action in the "Refresh needed" column.

| Edit type | Where it lives | Refresh needed to take effect |
|-----------|---------------|-------------------------------|
| Database row (INSERT/UPDATE) | PostgreSQL | None — immediately visible |
| Database schema (migration) | PostgreSQL | Run the migration SQL; no app restart needed |
| Python code (`app.py`, `*.py`) | Host → container via mount | **`docker compose restart app`** |
| Jinja template (`*.html`) | Host → container via mount | **`docker compose restart app`** (templates are compiled at worker boot) |
| Static asset (CSS, images in `/static/`) | Host → container via mount | Hard browser refresh (Ctrl+Shift+R), sometimes container restart |
| `docker-compose.yml` | Host | `docker compose up -d` (recreates containers as needed) |
| `Dockerfile` | Host | `docker compose build && docker compose up -d` (rebuilds image) |
| `.env` secrets | Host | `docker compose up -d` (env vars are read at container start) |
| Environment variables in `docker-compose.yml` | Host | `docker compose up -d` (recreate container) |
| NPM proxy host config | NPM UI (ubuntu-services:81) | Save in NPM UI; takes effect immediately |
| OPNsense firewall rule | OPNsense UI | Apply changes button in OPNsense |
| Cloudflare DNS record | Cloudflare dashboard | Propagates in seconds |
| Pi-hole local DNS record | Pi-hole UI | Takes effect immediately, but clients may have cached the old value |

**The key intuition:** every tool has its own notion of "when to reload." Persistent state (databases) updates immediately. Running processes (gunicorn workers) hold state in memory until restarted. Containers hold images until rebuilt. Browsers cache assets until forced to refresh.

---

## 5. Debugging decision tree

When something doesn't work, run this tree. Start at the top. Don't skip steps.

```
1. What exactly is broken?
   ├─ Can't reach the site at all  → Section 5A
   ├─ Page loads but shows 500     → Section 5B
   ├─ Page loads but content wrong → Section 5C
   └─ Data wrong in database       → Section 5D
```

### 5A. Site unreachable

```
curl -I https://fieldkit.cletize.com
```

- **DNS error** → Cloudflare DNS record missing or wrong. Check Cloudflare dashboard.
- **Connection timeout** → Home WAN unreachable (ISP, router), or Cloudflare proxy misconfigured.
- **502 Bad Gateway from Cloudflare** → Traffic reaches Cloudflare but NPM or backend is down.
- **502 from NPM** → NPM can't reach backend. Check:
  - `docker ps` on ubuntu-business — is the container running?
  - VLAN30 → VLAN70 firewall rule open for the app's port?
  - Backend responds to `curl http://10.83.70.10:3100` from ubuntu-services?

### 5B. 500 Internal Server Error

This is almost always a Python exception. Check the logs:

```bash
docker compose -f ~/docker/fieldkit-phase1/docker-compose.yml logs app --tail=100
```

Look for Python tracebacks. Common causes:
- **Database error** (missing column, wrong table) → migration not applied to this database. Run the migration SQL.
- **Template error** (`UndefinedError`, `TemplateSyntaxError`) → variable missing, Jinja syntax wrong.
- **ImportError** → missing Python package, fix `requirements.txt` and rebuild image.
- **SyntaxError** on worker boot → you broke `app.py`. Fix it, restart.

### 5C. Page loads but content wrong

This is where today's bug lived. Decision path:

**First — verify the running code matches disk.** Don't assume.

```bash
# When was the file last edited?
docker exec fieldkit-phase1-app-1 stat -c '%y' /app/templates/customer_form.html

# When did workers last start?
docker compose -f ~/docker/fieldkit-phase1/docker-compose.yml logs app 2>&1 | grep "Starting gunicorn" | tail -3
```

If the file mtime is **after** the last worker start → **restart the stack.** Edits aren't being served.

```bash
docker compose -f ~/docker/fieldkit-phase1/docker-compose.yml restart app
```

**Second — run the drift check** (Section 3). If the container and host disagree, you've been editing in the wrong place. Rescue with `docker cp` or re-deploy from git.

**Third — verify the route is passing what the template expects.** Add a debug print to the route:
```python
print(f"DEBUG: management_companies = {management_companies}")
```
Reload the page, check logs.

**Fourth — verify the template is referencing the right variable name.** Typos happen.

**Fifth — only now** suspect a Jinja bug or syntax issue in the template itself.

### 5D. Data wrong in database

- Query directly with `docker exec fieldkit-phase1-db-1 psql -U fieldkit -d <dbname> -c "SELECT ..."`
- Check which database the app is actually connected to (can be wrong if company_key mapping is off)
- Check whether schema migrations ran on all four databases, not just one

---

## 6. The April 21, 2026 incident — case study

Written so future sessions can recognize the pattern instantly.

**Symptom:** Management Company dropdown on the customer edit form showed no options. "-- None --" was there, but none of the 5 management companies appeared.

**Time lost chasing wrong theories:** ~5 hours across two AI sessions.

**Wrong theories (all ruled out):**
1. "Em-dash character broke Jinja parsing" — false. File contained valid UTF-8 em dashes in many places; they render fine.
2. "Management companies table is empty" — false. 5 rows, all active.
3. "Invisible Unicode character in the `{% for %}` tag" — false. Byte-level scan showed clean ASCII throughout the block.
4. "Template file is missing the block" — false. `grep` confirmed the block was present in the file on disk.

**Actual cause:** The template had been edited directly inside the running container via `docker exec`. The edit was correct. But gunicorn workers had booted at 22:29:38 with the pre-edit template compiled into memory, and nothing restarted them after the edit at 23:09:34. Workers cheerfully served the stale pre-edit version for 40 minutes while we debugged.

**Fix:** `docker compose restart app`. One second.

**Secondary issue:** The container filesystem held the new version. The host filesystem still had the old version. Git still had the old version. If the container had been rebuilt, the fix would have been lost. Rescued with `docker cp <container>:/app/templates/customer_form.html <host-path>` and committed as `198f1be`.

**Diagnostic signals we should have checked first:**
- File mtime vs. gunicorn last-start time (40-minute gap was the smoking gun)
- md5sum of the file in the container vs. on the host (they differed)

**Why we didn't:** Both AI sessions went directly to code theories because the code is what's visible and the deployment state is not. The lesson is to check deployment state BEFORE code, not after.

**Prevention going forward:**
- Edit files on the host, let the volume mount propagate to the container. Don't `docker exec` + edit.
- Run the drift check at the end of any significant session.
- When an edit "doesn't take effect," first question is always: "is the running process actually running my new code?"

---

## 7. Useful commands quick reference

```bash
# === Observability ===

# What containers are running?
docker ps

# Logs for the Phase 1 app
docker compose -f ~/docker/fieldkit-phase1/docker-compose.yml logs app --tail=50

# Follow logs in real time
docker compose -f ~/docker/fieldkit-phase1/docker-compose.yml logs -f app

# When did gunicorn last start?
docker compose -f ~/docker/fieldkit-phase1/docker-compose.yml logs app 2>&1 | grep "Starting gunicorn" | tail -3

# File mtime in container
docker exec fieldkit-phase1-app-1 stat -c '%y' /app/path/to/file

# === Restart / reload ===

# Restart the app container (picks up code/template edits)
docker compose -f ~/docker/fieldkit-phase1/docker-compose.yml restart app

# Full stack restart
docker compose -f ~/docker/fieldkit-phase1/docker-compose.yml restart

# Rebuild the image after Dockerfile/requirements.txt changes
docker compose -f ~/docker/fieldkit-phase1/docker-compose.yml up -d --build

# === Database ===

# Connect to a specific database
docker exec -it fieldkit-phase1-db-1 psql -U fieldkit -d fieldkit_getagrip

# One-off query
docker exec fieldkit-phase1-db-1 psql -U fieldkit -d fieldkit_getagrip -c "SELECT COUNT(*) FROM customers WHERE deleted_at IS NULL;"

# List all databases
docker exec fieldkit-phase1-db-1 psql -U fieldkit -d postgres -c "\l"

# === File rescue ===

# Copy file from container back to host (when edits landed in the wrong place)
docker cp fieldkit-phase1-app-1:/app/templates/file.html \
  ~/docker/fieldkit-phase1/fsm-system/phase1/fieldkit_backend/templates/file.html

# === Hash comparison ===

# Does the container copy match the host copy?
docker exec fieldkit-phase1-app-1 md5sum /app/templates/customer_form.html
md5sum ~/docker/fieldkit-phase1/fsm-system/phase1/fieldkit_backend/templates/customer_form.html
```

---

## 8. Conventions and gotchas specific to this project

- **VLAN70 isolation:** ubuntu-business (where FieldKit runs) cannot reach any RFC1918 address by design. Cross-VM operations (NAS backups, database dumps) must be orchestrated from ubuntu-services (VLAN30) pushing TO ubuntu-business, never the other way around.
- **Four databases, not one:** Each company has its own PostgreSQL database. The company_key in the URL (`/getagrip/...`) determines which database the route connects to. A migration applied to only one database will cause partial failures — always apply to all four.
- **Kleanit FL split:** Kleanit Charlotte and Kleanit SF share one ServiceFusion account. Customers with `*FL*` in their names get routed to `fieldkit_kleanit_sf` on import. Asterisks in names also cause issues with Windows ZIP extraction and SQL ILIKE patterns — sanitize filenames.
- **Cash-basis tax compliance:** NC tax reporting is based on payment collection date, not invoice date. The `tax_processor.py` matches Tax Reports + Transaction Reports by Job# to get the payment date. Don't "simplify" this.
- **Wildcard SSL scope:** The `*.cletize.com` wildcard cert does NOT cover two levels deep. `staging.fieldkit.cletize.com` or `app.fieldkit.cletize.com` need their own Cloudflare DNS challenge certs in NPM.
- **Company branding:** CSS variables swap per company to prevent cross-company operational mistakes. Michele uses separate browser tabs per company; visual distinction matters.
- **Chris's preferences:** Complete files over snippets, sequential steps over parallel delivery, reasoning shown before code. Don't assume file paths or DB names — check actual source.

---

## 9. When to escalate to Opus

Sonnet handles most development well. Escalate to Opus when:
- A bug has resisted multiple rounds of theory-and-fix — likely means the real cause is at a layer nobody is looking at
- Architecture decisions with long-term consequences (database design, tenant isolation, auth model)
- Debugging that requires holding many disconnected pieces of context simultaneously
- Chris explicitly mentions wanting "the smart one"

For routine feature work, template edits, and straightforward Flask routes, Sonnet is fine and faster.

---

*Last updated: April 21, 2026*
*Canonical path in repo: `docs/PROJECT-KNOWLEDGE/STACK-REFERENCE.md` (suggested)*
