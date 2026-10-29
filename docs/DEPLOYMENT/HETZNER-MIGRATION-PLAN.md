# FieldKit → Hetzner migration plan

*Written 2026-10-29 by Fable from `HETZNER-MIGRATION-BRIEF.md`, `HOMELAB-CONTEXT-FOR-FIELDKIT-MIGRATION.md`, and the `fsm-system` repo at HEAD (`CLAUDE.md`, `ops/backup/fieldkit-backup.sh`, `ops/maps/refresh-basemap.sh`, `docs/DEPLOYMENT/*`, `phase1/fieldkit_backend/app.py`, `docker-compose.yml` mirror, `MOBILE-APP-PLAN.md` §4, `..._ai-assistant.md` §3). Hetzner prices were checked against third-party price trackers on 2026-10-29; Chris confirms them in the console before ordering (Phase 1).*

*This is a plan for a Claude Code session to execute. Plan only: nothing here has been run.*

> **Revision 1, 2026-10-29 (Claude Code + Chris).** Fable's plan with Chris's decisions edited in. **This version
> is the one to execute.** Main changes:
> - **Server:** **CPX21** (not CPX11), sized for **30 users at go-live and up to 50**, mostly techs on the mobile app.
> - **Hetzner account:** a **new FieldKit-only account**, not a project in the homelab account.
> - **Backups add-on:** none.
> - **No extra volume:** job photos will go to object storage (R2), not the server.
> - **Locked practice site:** Cloudflare Access is **required** on `fieldkit-new`.
> - **Pinned `cloudflared`** version.
> - **Graceful reload** on deploys.
> - **Cutover on a Friday night.**
> - **Statements site backups** added.
> - **Answers** to all of Fable's questions are in §15.
> - **New §17:** work needed before office go-live that isn't part of the migration.
>
> Edited passages are marked **[R1]**.

**Owner key:** 🧑 **Chris** (console, dashboard, payment, secrets, homelab) · 🤖 **Claude** (the executing session) · 🧑🤖 Claude prepares, Chris runs or approves.

---

## 0. Read this first: five things that change the brief

### 0.1 The €30 budget no longer buys what it did (plan change)

Hetzner raised cloud prices on **15 June 2026**; the US locations rose the most (CPX roughly 2.5–3×). Orders placed before that date kept old prices, so `letizecloud` is almost certainly on the old price list. **Do not rescale, rebuild or re-create `letizecloud`** — a rescale re-prices it at the new rates.

Current US (Ashburn/Hillsboro) prices, monthly, excl. VAT, excl. IPv4:

| Type | vCPU | RAM | Disk | Traffic | €/mo |
|---|---|---|---|---|---|
| **CPX11** | 2 | 2 GB | 40 GB | 1 TB | **17.49** |
| CPX21 | 3 | 4 GB | 80 GB | 2 TB | 31.99 |
| CPX31 | 4 | 8 GB | 160 GB | 3 TB | 62.49 |
| CCX13 (dedicated) | 2 | 8 GB | 80 GB | 1 TB | 43.49 |

Add-ons: primary IPv4 ~€0.50; server backups add-on = 20% of server price; volumes €0.0572/GB; snapshots €0.0143/GB. The cheap CX/CAX lines **do not exist in the US**. In Germany/Finland, CX23 (2 vCPU, 4 GB, 40 GB) is about €5.49.

**[R1] Decided: CPX21, Ashburn.** Fable's original pick, a CPX11 at about €22.6 all-in, was sized for the 8 users in the
brief. Real numbers: **~30 users at office go-live, up to ~50 later**, most of them techs on the mobile app. 2 GB RAM is
too tight for that. Two more reasons to buy the right size now rather than resize later:
- **A Hetzner resize is billed as a new order**, at whatever the price is on that day.
- **The June 2026 increase spared running servers** (April's didn't).

The €14/mo extra before go-live is treated as insurance against another increase.

| Item | €/mo |
|---|---|
| **CPX21, Ashburn** (3 vCPU, 4 GB, 80 GB, 2 TB traffic) | 31.99 |
| Primary IPv4 (needed: Census geocoder, Resend, GitHub, Protomaps are not reliably reachable over IPv6 only; Hetzner has no NAT64) | ~0.50 |
| Server backups add-on | **not bought** (see 7C.6) |
| Extra volume | **not bought:** photos go to object storage, see §1.3 |
| Off-site backup copy: **Cloudflare R2** (free up to 10 GB; snapshots are ~9 MB) | 0 |
| **Total** | **~€32.5** |

The order goes in a **new Hetzner account used only for FieldKit**, so its invoices (and card charges) are separate from
the homelab's `letizecloud`. Costs are tracked in Chris's Firefly III under tag `fieldkit` until the LLC exists.

**[R1] Is CPX21 enough?** Yes, for go-live, provided two things are done (see §17):
- the app is tuned: more gunicorn workers/threads and a database connection pool;
- photos never live on the server.

Keep the 2 GB swap file as headroom. If RAM or CPU pressure shows once the mobile app is in full use (the disk-check
push also reports memory, 7C.3), resize to CPX31 (~€62), at the price on that day.

**[R1] Germany was considered and rejected.** A Falkenstein/Nuremberg CX23 costs ~€5.49. But a measured round trip
from Chris's house to his existing Hetzner Germany VM was **128 ms**, against ~15 ms for Ashburn, and that delay lands
on every click. Speed is the number one goal.

### 0.2 Off-site backup: Cloudflare R2 instead of a Hetzner Storage Box (plan change)

The brief asks for an off-site copy "at Hetzner". Two problems: Storage Boxes and Object Storage are in European locations only (fine for geography, but) they share the Hetzner account with the server — one compromised API token or one billing problem takes out server and backups together. Chris already has a Cloudflare account; **R2's free tier (10 GB storage, free egress) holds years of ~9 MB snapshots and the first ~5 GB of photo backups at zero cost**, on a different provider, with a scoped token that can only write one bucket. `rclone` talks to R2 natively. If Chris prefers to stay inside Hetzner, a Storage Box (BX11, 1 TB, ~€4/mo, Falkenstein/Helsinki) works identically via `rclone` over SFTP — swap the remote and nothing else changes.

**[R1] Decided: R2.** Job photos from the mobile app will also go to R2: a separate bucket and token, not part of
this migration. They'll go through an **S3-compatible storage layer**, so the provider can be changed later
(Backblaze B2, Wasabi, Hetzner Object Storage, AWS) with a configuration change plus a copy. See §17.

### 0.3 Monitoring: Uptime Kuma on `letizecloud` plus one check from the house (confirming the homelab doc's concern)

Uptime Kuma already exists on `letizecloud` with Pushover wired. Use it for: the public HTTP check, a **push monitor** for backup staleness (the backup script pings a Kuma URL on success; Kuma alerts if no ping within 30 h — that is the stale-backup alert for free), and a push monitor for disk usage. Because `letizecloud` and the new server share one provider, add a second, dumb HTTP check from ubuntu-services (a 10-line systemd timer that curls `https://fieldkit.cletize.com/login` and hits Pushover on failure). Two watchers, two providers, no new software.

### 0.4 Deploy and dev: a specific design (requested)

- **Deploy:** production keeps the bind-mounted git checkout (no image builds; same as today, least change). The build VM holds a **forced-command SSH key** that can do exactly one thing on production: run `deploy.sh <git sha>`. The script fetches, checks out the sha, applies any migration files not yet recorded in a new `schema_migrations` table in each of the four DBs, restarts the app, curls `/login`, and reverts to the previous sha if the health check fails. A pre-deploy backup snapshot makes migration rollback possible. Chris says "deploy"; the session runs it; Claude Code's safety check prompts Chris. Details in §5.
- **Dev:** private to Tailscale via `tailscale serve` on the build VM. No public hostname, no Cloudflare Access, no second-level-subdomain certificate problem. Plus a code-level kill switch (`FIELDKIT_ENV=dev` makes every email path raise) so the safety of dev doesn't depend on a `.env` file being right. Details in §6.

### 0.5 Things in the code that bite during a move (new findings)

- `app.py` line 33: `app.secret_key = os.environ.get('FLASK_SECRET_KEY', secrets.token_hex(32))`. If `.env` is missing or the key is misspelled, **each of the two gunicorn workers gets a different random key**: users are logged out at random on every other request, and nothing in the logs says why. Every restore and every deploy must assert the key is present (the plan does).
- `app.py` line 9064: the code's fallback `APP_BASE_URL` is `https://app.fieldkit.cletize.com` — a two-level subdomain Cloudflare's free cert can't serve. Same lesson: `.env` must be complete, and the plan checks it.
- No `ProxyFix` is configured. That is fine today and stays fine behind the tunnel: Flask builds absolute URLs from the request `Host` header, which Cloudflare passes through, and the only header the app reads is `X-Forwarded-For` (estimate-request rate limit), which Cloudflare sets to the real client IP.
- `/sales-map/tiles/<name>.pmtiles` is served with HTTP Range requests via `send_file(conditional=True)`. Cloudflare Tunnel passes Range requests through, but it must be tested in the rehearsal (§P6), not assumed.
- Cloudflare's proxy limits request bodies to **100 MB** on the free plan and closes idle origin connections after **100 s**. Neither matters for today's forms and PDFs; the mobile app's photo uploads must stay under 100 MB per request (they will).
- `fieldkit-backup.sh` tars **all of `uploads/`** into every nightly snapshot. At 7 MB that is nothing. With thousands of photos it becomes a 10 GB tarball × 14 copies. **This fails months after the move, not on the night.** Flagged in §9 with the fix (incremental sync of uploads; tar only the DB).
- `fieldkit-backup.sh` and `refresh-basemap.sh` hard-code `/home/letize/docker/fieldkit-prod`. The plan keeps user `letize` and identical paths on Hetzner so nothing needs editing.

---

## 1. Target state

### 1.1 Architecture

```
 Internet users (office, Chris O's tablet on cellular)
        │ https://fieldkit.cletize.com  (Cloudflare-proxied CNAME → tunnel)
        ▼
   Cloudflare edge ──(outbound tunnel from server)──▶ cloudflared container
                                                          │ http://app:5001
                                                          ▼
   Hetzner CPX21 "fieldkit-prod" (Ashburn)       app (gunicorn)  ◀─▶  db (postgres:16)
   - no inbound ports open (Hetzner firewall: deny all; optional UDP 41641 for Tailscale)
   - Tailscale node, tagged tag:prod, key expiry n/a (tagged), accept-routes=false
   - user letize, paths /home/letize/docker/fieldkit-prod/... identical to today
   - [R1] no extra volume: uploads/ and backups/ on the 80 GB root disk (photos go to R2, §17)
   - cron (UTC) unchanged; backup 07:15 UTC; rclone → R2 at 07:25 UTC
        ▲ SSH 22 over Tailscale only, from:
        │   ubuntu-services (restricted rrsync -ro key, NAS pull 07:45 UTC)
        │   ubuntu-business = build VM (forced-command deploy key)
        │   Chris's admin devices (full key)
        │   later: AI machine (Postgres replica, port 5432 over Tailscale), Mac mini (API dev)
```

Nothing on Hetzner initiates a connection to the house. The Tailscale ACL (§P3) enforces that; it is not a convention.

### 1.2 What stays home

- **Statements site** (`~/docker/statements/`, `fsm_prod`) on ubuntu-business, unchanged.
- **ubuntu-business** becomes the build VM: git work, tests, dev stack (§6), deploy trigger.
- **NAS copy** of FieldKit snapshots, pulled by ubuntu-services exactly as today, source changed.
- Proxmox weekly backup of VM 101 continues (it now protects the build VM + statements).

### 1.3 Disk and growth

**[R1]** The CPX21 has an 80 GB root disk. On it:
- Ubuntu + Docker + images ≈ 6 GB;
- basemap 0.6 GB;
- `pgdata` < 0.5 GB (growing slowly);
- logs and 2 GB swap;
- `uploads/` (release forms and business-card photos, ~7 MB) and 14 local snapshots (~9 MB each).

That's **~10 GB used**, ~13%.

**Photos:** Chris estimates **up to ~200 a day**. That's roughly 30–45 GB a year, or **~65–95 GB** held under the 26-month
retention rule. **They go straight to R2** (about $1–1.50/mo), never onto the server disk. So:
- the disk stays small;
- the nightly backup stays small, which makes the tarball trap (§0.5, T12) moot;
- retention is an R2 lifecycle rule.

The 70% disk alert (7C.3) is the backstop if anything else grows.

---

## 2. Phase 0 — Verify before planning on it 🧑🤖

Nothing in the homelab context doc was checked live. Everything below must be confirmed before Phase 1, because several cutover steps depend on the answers. Read-only commands are in Appendix A of `HOMELAB-CONTEXT-FOR-FIELDKIT-MIGRATION.md`; this list is what each answer feeds.

| # | Check | Where | Why it matters |
|---|---|---|---|
| 0.1 | `curl -sI https://fieldkit.cletize.com/login` from a phone on cellular shows FieldKit (not the statements site) | 🧑 phone | Resolves the hostname discrepancy. The brief (verified live) says FieldKit; the homelab notes (stale) say statements. The brief wins unless this says otherwise. |
| 0.2 | Cloudflare DNS → `fieldkit` record: A or CNAME, proxied? | 🧑 CF dashboard | Cutover step order (§P9). Must be proxied (it is, per brief) — then clients see no DNS change at all on the night. |
| 0.3 | OPNsense ddclient hostname list contains `fieldkit`? | 🧑 OPNsense | If yes, remove it in Phase 2 or ddclient will overwrite the tunnel CNAME. |
| 0.4 | Pi-hole local DNS records and OPNsense Unbound overrides for `fieldkit.cletize.com` | 🧑 Pi-hole/OPNsense | Split DNS would hide a broken cutover from LAN devices. |
| 0.5 | `systemctl cat fieldkit-pull.service fieldkit-pull.timer` on ubuntu-services; note the script path, source host, key path, staleness threshold, Pushover call | 🤖 homelab session | §P7 modifies a copy of this script. |
| 0.6 | `tailscale status` on ubuntu-business; `tailscale ping 10.83.184.15` from it | 🤖 | Tells us whether the DMZ box can already reach the LAN over Tailscale (if yes, the ACL in §P3 also fixes an existing hole). |
| 0.7 | Tailscale admin → Access Controls: is it the default allow-all policy? MagicDNS and HTTPS enabled? | 🧑 | §P3 ACL and §6 `tailscale serve`. |
| 0.8 | `letizecloud`: Hetzner project, location, server type, price shown in console | 🧑 Hetzner console | Confirms old-price lock and whether it's in Ashburn (Q3). |
| 0.9 | Uptime Kuma on letizecloud: reachable only over Tailscale? Which monitors exist for FieldKit? n8n workflows that reference FieldKit — by hostname or by IP? | 🧑🤖 | Anything checking `https://fieldkit.cletize.com` needs no change after cutover; anything hitting 10.83.70.10 or 100.86.23.68 does. |
| 0.10 | `crontab -l` on ubuntu-business matches `cron-jobs.md` and the brief's table | 🤖 | The new crontab is copied from the real one, not from docs. |
| 0.11 | `ls ~/docker/fieldkit-prod/init/` and read `02_apply_schema.sh` | 🤖 | §P6 restore has to coexist with first-boot scripts. |
| 0.12 | `.env` on ubuntu-business: all five keys present, `APP_BASE_URL=https://fieldkit.cletize.com` exactly | 🤖 (names only, not values) | §0.5. |
| 0.13 | "staging on 3001" in the homelab notes: does a second stack exist on ubuntu-business? | 🤖 `docker ps` | If yes, it must not hold the real Resend key, and it's the natural seed for the dev stack. |
| 0.14 | Resend dashboard: is there a sandbox/test mode or a second API key option? | 🧑 | Decides whether dev gets no key (plan default) or a test key. |
| 0.15 | Free space on the NAS `hdd/ubuntu_backups`; is anything pruning old FieldKit snapshots there? | 🤖 TrueNAS `zfs list` | Nothing is known to prune; NAS copy grows forever otherwise. |

**Checkpoint 0 — Chris answers the questions in §10 and the table above before anything is ordered.**

---

## 3. Phase 1 — Provision 🧑 (money is spent here)

**Checkpoint 1 — Chris confirms server type, location and add-ons before ordering.**

| # | Step | Where | Verify | Undo |
|---|---|---|---|---|
| 1.0 | **[R1]** Create a **new Hetzner account just for FieldKit** (not the homelab account that owns `letizecloud`), with 2FA on. Add the payment card. Note the account/customer number for the Firefly III rule (tag `fieldkit`). | 🧑 Hetzner | Account active, 2FA on | Close account |
| 1.1 | In that account, create a **project** `fieldkit-prod`. | 🧑 console | Project appears | Delete project |
| 1.2 | Generate a fresh ed25519 key pair for Chris's admin access (`ssh-keygen -t ed25519 -C fieldkit-prod-admin`); add the public key to the project's SSH keys. Store the private key in Vaultwarden. | 🧑 PC | Key listed | Remove key |
| 1.3 | **[R1]** Create server: **CPX21, Ashburn (`ash`), Ubuntu 24.04**, SSH key from 1.2, name `fieldkit-prod`, IPv4 + IPv6, **Backups add-on off**. Confirm the price shown in the console against §0.1 (~€31.99 + IPv4). If it differs materially, stop and tell the session. | 🧑 console | Server running, price as expected | Delete server (billed hourly) |
| 1.4 | **[R1] Removed:** no volume. | — | — | — |
| 1.5 | Create a **Cloud Firewall** `fieldkit-prod-fw`: inbound rules **none** except optionally `UDP 41641` from any (Tailscale direct path; without it Tailscale still works via DERP relays, slower). Outbound: allow all. Apply to the server. | 🧑 console | Firewall shows applied; `ssh root@<public-ip>` from outside **times out** | Remove firewall |
| 1.6 | Before the firewall blocks port 22: SSH in once as root from Chris's PC using the key, confirm it works, then **Phase 2 is done over this root SSH until Tailscale is up, then over Tailscale only**. Order: install Tailscale first (2.4), then apply the firewall (1.5). | 🧑 | `ssh root@<ip> uptime` | — |
| 1.7 | Record in Vaultwarden: server IP, root key, project name. **No Hetzner API token is needed by this plan.** | 🧑 | — | — |

---

## 4. Phase 2 — Base server build 🤖 (over SSH; root until 2.4, then `letize` over Tailscale)

Commands are for Ubuntu 24.04. Each step: verify before moving on.

| # | Step | Verify | Undo |
|---|---|---|---|
| 2.1 | `timedatectl set-timezone UTC` (Hetzner images default to UTC; confirm) | `date` shows UTC | — |
| 2.2 | `apt update && apt full-upgrade -y && apt install -y docker.io docker-compose-v2 rsync git curl ufw unattended-upgrades` — then check `rrsync` exists: `ls /usr/bin/rrsync \|\| ls /usr/share/doc/rsync/scripts/rrsync.gz` (on 24.04 it is `/usr/bin/rrsync`). | `docker compose version`, `rrsync` present | — |
| 2.3 | Create user: `adduser --disabled-password --gecos '' letize; usermod -aG docker,sudo letize; mkdir -p /home/letize/.ssh; cp /root/.ssh/authorized_keys /home/letize/.ssh/; chown -R letize:letize /home/letize/.ssh; chmod 700 /home/letize/.ssh`. Passwordless sudo for `letize` (`echo 'letize ALL=(ALL) NOPASSWD:ALL' > /etc/sudoers.d/letize`) — Chris chooses; the brief notes sudo was missing on ubuntu-business and it cost a cleaner cron location. | `ssh letize@<ip> sudo -n true` | `deluser --remove-home letize` |
| 2.4 | Install Tailscale: `curl -fsSL https://tailscale.com/install.sh \| sh`. Then **Chris** generates a one-off, **tagged** auth key in the admin console (Settings → Keys: reusable off, ephemeral off, tags `tag:prod`, pre-authorized). 🤖 runs `tailscale up --authkey <key> --accept-routes=false --advertise-tags=tag:prod --hostname fieldkit-prod`. **Tagged nodes have no key expiry**, which is the fix for the lock-out concern. Requires §P3's ACL to define `tag:prod` first — do P3 before this step. | `tailscale status` on fieldkit-prod shows tags; from Chris's PC `ssh letize@fieldkit-prod` works via MagicDNS | `tailscale logout`; delete node in admin console |
| 2.5 | Harden SSH: `/etc/ssh/sshd_config.d/hardening.conf`: `PasswordAuthentication no`, `PermitRootLogin no`, `ListenAddress 100.x.y.z` (the Tailscale IP) *after* confirming Tailscale SSH works. Restart sshd. Now apply the Hetzner firewall (1.5). | `ss -tlnp \| grep :22` shows only the Tailscale IP; public-IP SSH times out | Revert file, restart sshd |
| 2.6 | `ufw default deny incoming; ufw default allow outgoing; ufw allow in on tailscale0; ufw enable` (belt and braces with the cloud firewall) | `ufw status` | `ufw disable` |
| 2.7 | Swap: `fallocate -l 2G /swapfile; chmod 600 /swapfile; mkswap /swapfile; swapon /swapfile; echo '/swapfile none swap sw 0 0' >> /etc/fstab` | `free -h` | Remove line, `swapoff` |
| 2.8 | **[R1] Removed:** no volume to mount. | — | — |
| 2.9 | Docker daemon: `/etc/docker/daemon.json` with `{"log-driver":"json-file","log-opts":{"max-size":"20m","max-file":"5"}}` so container logs can't fill the disk; `systemctl restart docker` | `docker info \| grep -i log` | Delete file |
| 2.10 | `unattended-upgrades` with `Unattended-Upgrade::Automatic-Reboot "false"` (we don't want surprise reboots during the day; patch reboots are a manual, announced step) | `cat /etc/apt/apt.conf.d/50unattended-upgrades` | — |
| 2.11 | **[R1]** Directory skeleton as `letize`: `mkdir -p ~/docker/fieldkit-prod/uploads ~/logs ~/bin ~/backups/fieldkit`. Plain directories, no symlinks, the same paths as ubuntu-business. **`~/logs` must exist** or every cron line's `>> ~/logs/...` fails silently. | `ls -la ~/docker/fieldkit-prod ~/backups` | — |
| 2.12 | Sanity: outbound reachability the app needs: `curl -sI https://geocoding.geo.census.gov/ \| head -1`, `curl -sI https://api.resend.com \| head -1`, `curl -sI https://build-metadata.protomaps.dev/builds.json \| head -1`, `curl -sI https://github.com \| head -1` | All return HTTP status lines | — |

---

## 5. Phase 3 — Tailscale ACL 🧑 (do before 2.4)

Replace the default allow-all policy with one that preserves today's behaviour between Chris's own machines and gives the prod node **no outbound rights into the tailnet**. Tagged nodes are not `autogroup:member`, so they get nothing unless a rule names `tag:prod` as `src` — and none does.

```jsonc
{
  "tagOwners": { "tag:prod": ["autogroup:admin"] },
  "acls": [
    // everything Chris owns keeps talking to everything else, as today
    { "action": "accept", "src": ["autogroup:member"], "dst": ["autogroup:member:*"] },
    // who may reach production, and on what
    { "action": "accept",
      "src": ["100.76.150.28",   // ubuntu-services: NAS pull (rrsync key)
              "100.86.23.68",    // ubuntu-business = build VM: deploy key, cutover transfer
              "autogroup:admin"],// Chris's own devices
      "dst": ["tag:prod:22"] },
    // prod → letizecloud only for the Uptime Kuma push URL (see P7). Remove if Kuma is public.
    { "action": "accept", "src": ["tag:prod"], "dst": ["100.118.85.33:3001"] }
    // later: { "src": ["<ai-machine>"], "dst": ["tag:prod:5432"] } for the replica,
    //        { "src": ["100.105.68.75"], "dst": ["tag:prod:22"] } for the Mac mini
  ],
  "ssh": []  // not using Tailscale SSH; ordinary sshd on the Tailscale IP
}
```

Verify: after 2.4, from `fieldkit-prod` run `tailscale ping 10.83.184.15`, `tailscale ping ubuntu-services`, `nc -zv 100.76.150.28 22` — **all must fail**. From ubuntu-services `nc -zv fieldkit-prod 22` succeeds. Undo: restore the previous ACL (the admin console keeps history).

Note: the `autogroup:member → member` rule reproduces today's open policy inside the house, which also means ubuntu-business (DMZ) can reach LAN hosts over Tailscale if it could before (check 0.6). Tightening that is a separate, later job; it is not made worse by this plan.

---

## 6. Phase 4 — Install the stack (no cron, no email yet) 🤖 + 🧑 for secrets

| # | Step | Where | Verify | Undo |
|---|---|---|---|---|
| 4.1 | `cd ~/docker/fieldkit-prod && git clone https://github.com/chrisletize/fsm-system.git` (public repo, read-only HTTPS clone is fine — production never pushes) | prod | `git -C fsm-system log -1` | `rm -rf` |
| 4.2 | Copy `docker-compose.yml`, `Dockerfile`, `init/` from the newest NAS snapshot's `server-config.tar.gz` — **not** from the repo mirror (the mirror has drifted before). Route: ubuntu-services has the NAS mounted and may reach prod: `rsync -a /nas/hdd/ubuntu_backups/fieldkit/daily/<newest>/server-config.tar.gz letize@fieldkit-prod:~/` (push from the house outward is allowed). Then `tar -C ~/docker/fieldkit-prod -xzf ~/server-config.tar.gz`. | ubuntu-services → prod | Files match ubuntu-business (`md5sum` both sides) | — |
| 4.3 | **Edit `docker-compose.yml` on prod** (and then the repo mirror, same commit): (a) change `ports: - "3000:5001"` to **`"127.0.0.1:3000:5001"`** so the app is reachable only locally (for health checks) and through the tunnel; (b) add the tunnel service: ```cloudflared:\n  image: cloudflare/cloudflared:<pinned version, [R1] never :latest>\n  restart: unless-stopped\n  command: tunnel --no-autoupdate run\n  environment:\n    TUNNEL_TOKEN: ${TUNNEL_TOKEN}\n  depends_on: [app]```; (c) **[R1]** pin `cloudflared` to the current release tag (record it in `fieldkit-prod-server.md`; upgrade deliberately); (d) pin `postgres:16` to the exact minor currently running on ubuntu-business (`docker compose exec db postgres --version`) — same major is mandatory for the dumps, same minor avoids a surprise. | prod | `docker compose config` parses | Keep the original as `docker-compose.yml.orig` |
| 4.4 | **`.env`** — 🧑 Chris writes it himself over SSH (`nano ~/docker/fieldkit-prod/.env`), from Vaultwarden / from ubuntu-business: `DB_PASSWORD` (same as today — it must match the password inside `globals.sql`), **`FLASK_SECRET_KEY` identical to production** (sessions and reset links survive), `RESEND_FROM_EMAIL`, `APP_BASE_URL=https://fieldkit.cletize.com`, **`RESEND_API_KEY=`** (empty — stays empty until cutover step 9.14), `TUNNEL_TOKEN` (from P5). `chmod 600 .env`. | 🧑 prod | 🤖 checks names only: `grep -c . .env` = 6 lines, `grep -q '^FLASK_SECRET_KEY=.\{32,\}' .env`, `grep -q '^RESEND_API_KEY=$' .env`, `grep -q '^APP_BASE_URL=https://fieldkit.cletize.com$' .env` | — |
| 4.5 | First boot: `docker compose up -d --build`. The `init/` scripts run on the empty `pgdata` volume and create the four databases with schema. Watch `docker compose logs -f db` until `database system is ready`. | prod | `docker compose ps` all healthy; `curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:3000/login` → 200 | `docker compose down -v` (destroys `pgdata`, fine at this stage) |
| 4.6 | Basemap: `MAP_ROOT=~/docker/fieldkit-prod/maps bash fsm-system/ops/maps/refresh-basemap.sh` (≈1 min, ~570 MB, needs outbound to GitHub and protomaps). | prod | `ls -la maps/` shows both `.pmtiles`, `VERSION`, `assets/` | `rm -rf maps` |
| 4.7 | Geocoder smoke test from inside the container: `docker compose exec -T app python -c "import urllib.request;print(urllib.request.urlopen('https://geocoding.geo.census.gov/geocoder/locations/onelineaddress?address=1600+Pennsylvania+Ave+Washington+DC&benchmark=Public_AR_Current&format=json',timeout=20).status)"` | prod | prints 200 | — |
| 4.8 | Confirm **no cron** is installed for `letize` yet: `crontab -l` → empty. (Cron is installed at cutover, step 9.12, never before — see trap T4.) | prod | empty | — |

---

## 7. Phase 5 — Cloudflare Tunnel with a **temporary hostname** 🧑 + 🤖

The trick that makes the cutover small: bring the tunnel up on **`fieldkit-new.cletize.com`** (one level deep, so the free cert covers it) weeks ahead. The rehearsal is tested on it from the real internet. On the night, cutover becomes "add the real hostname to a tunnel that's already proven".

| # | Step | Where | Verify | Undo |
|---|---|---|---|---|
| 5.1 | Zero Trust → Networks → Tunnels → Create tunnel (Cloudflared) → name `fieldkit-prod`. Copy the **token** (it is a secret: it lets a machine serve as origin for whatever hostnames the tunnel routes). Store in Vaultwarden; paste into `.env` as `TUNNEL_TOKEN` (4.4). | 🧑 CF | Tunnel exists, status "Inactive" | Delete tunnel |
| 5.2 | Public hostname: `fieldkit-new.cletize.com` → service `http://app:5001` (the compose service name; cloudflared runs in the same compose network). Cloudflare creates the proxied CNAME automatically. | 🧑 CF | DNS tab shows `fieldkit-new` CNAME to `<id>.cfargotunnel.com`, proxied | Delete hostname + record |
| 5.3 | `docker compose up -d cloudflared` | 🤖 prod | Tunnel status "Healthy" in dashboard; `curl -sI https://fieldkit-new.cletize.com/login` from Chris's phone on cellular → 200 | `docker compose stop cloudflared` |
| 5.4 | If 0.3 said `fieldkit` is in ddclient: **remove it now** (and reboot ddclient or wait a cycle). Also check `fieldkit-new` isn't somehow matched by a wildcard entry. | 🧑 OPNsense | Cloudflare `fieldkit` A record unchanged after 24 h is irrelevant — the point is ddclient no longer *manages* it | Re-add |
| 5.5 | **[R1] Required:** Zero Trust → Access → add an Access policy on `fieldkit-new.cletize.com` allowing only Chris's email (one-time PIN). Must be in place **before** step 6.1 puts real data on the server. The rehearsal copy of production data is then not reachable by anyone who guesses the name. **Remove the policy before reusing the tunnel for the real hostname, or add it there only if everyone is comfortable with the extra login** (they won't be; mobile use). | 🧑 CF | Visiting prompts for email | Delete policy |
| 5.6 | Cloudflare SSL/TLS → Edge Certificates: confirm "Always Use HTTPS" on. SSL mode is irrelevant to tunnel origins (Cloudflare terminates TLS; the tunnel carries HTTP inside an encrypted channel). | 🧑 CF | — | — |

---

## 8. Phase 6 — Rehearsal: full restore and test 🤖 + 🧑

**Checkpoint 2 — Chris OKs restoring real production data onto Hetzner** (it holds real customer data; the Resend key is still empty, so nothing can email anyone).

| # | Step | Where | Verify | Undo |
|---|---|---|---|---|
| 6.1 | Pick the newest complete snapshot on the NAS; push it to prod: `rsync -a /nas/hdd/ubuntu_backups/fieldkit/daily/<stamp>/ letize@fieldkit-prod:~/restore/<stamp>/` | ubuntu-services | `(cd ~/restore/<stamp> && sha256sum -c SHA256SUMS)` on prod: all OK | `rm -rf ~/restore` |
| 6.2 | Stop the app so nothing touches the DBs: `docker compose stop app` | prod | `docker compose ps` | `start app` |
| 6.3 | Roles: `docker compose exec -T db psql -U fieldkit -d postgres < ~/restore/<stamp>/globals.sql` (idempotent-ish: `CREATE ROLE` for roles that exist errors harmlessly; **the `fieldkit` role's password line resets it to production's — which must equal `.env`'s `DB_PASSWORD`, see trap T5**) | prod | `psql -U fieldkit -d postgres -c '\du'` lists the same roles as production | — |
| 6.4 | For each of the four DBs: drop the init-created empty DB and restore from the dump: `docker compose exec -T db psql -U fieldkit -d postgres -c 'DROP DATABASE fieldkit_getagrip'` then `docker compose exec -T db pg_restore -U fieldkit -d postgres --create --exit-on-error < ~/restore/<stamp>/fieldkit_getagrip.dump` (repeat for `fieldkit_kleanit_charlotte`, `fieldkit_cts`, `fieldkit_kleanit_sf`). `--create` recreates the DB with its original owner from the dump, so the `--no-owner` dance in `backups.md` isn't needed on a fresh server. | prod | Row counts vs `MANIFEST`: `psql -d <db> -Atc "select count(*) from information_schema.tables where table_schema='public'"` equals MANIFEST's table count; `select count(*) from customers`, `work_orders`, `invoices`, `sales_visits`, `users` noted for comparison with ubuntu-business the same day | `DROP DATABASE` and rerun |
| 6.5 | Uploads: `tar -C ~/docker/fieldkit-prod -xzf ~/restore/<stamp>/uploads.tar.gz` → lands in `uploads/` [R1: a plain directory, no volume]. Ownership: the container runs as root (no `USER` in the Dockerfile), so any ownership works; keep `letize:letize` for tidiness. | prod | `find ~/docker/fieldkit-prod/uploads -type f \| wc -l` = MANIFEST's upload count | `rm -rf ~/docker/fieldkit-prod/uploads/*` |
| 6.6 | `docker compose start app`; **confirm the key is in effect**: `docker compose exec app python -c "import os;print(len(os.environ['FLASK_SECRET_KEY']))"` > 0 | prod | 200 on `/login` | — |
| 6.7 | **Functional test on `https://fieldkit-new.cletize.com` from Chris's phone on cellular and from the office PC.** Checklist: log in as Chris (same password works → users restored); switch companies (all four load); customer list + search; open a work order; **sales map loads tiles and zooms** (Range requests through the tunnel — trap T9); open a release-form PDF from uploads; generate an invoice PDF and an Excel export; `/settings/company` → Scheduled Jobs panel shows history. **Do not click any Send/Email button**: with no Resend key the app says "Email sending is not configured", which is itself a test — confirm that message appears on the invoice-send page and the statement page. | 🧑 + 🤖 | All pass; note load times vs today | — |
| 6.8 | Log out on the rehearsal site. **Do not run any `jobs.py` command** on prod during rehearsal (trap T4). | — | — | — |
| 6.9 | Run the backup script once by hand: `bash fsm-system/ops/backup/fieldkit-backup.sh` | prod | Snapshot in `~/backups/fieldkit/daily/`, `last-success` written | `rm -rf ~/backups/fieldkit/daily/*` |
| 6.10 | **Restore-time measurement:** note wall-clock for 6.1–6.6. Expected: under 5 minutes. This number feeds the cutover estimate. | — | — | — |
| 6.11 | Leave the restored data in place. It gets replaced wholesale on cutover night (step 9.7 drops and restores again). | — | — | — |

If anything in 6.7 fails: fix it on the **build VM**, commit, `git pull` on prod, restart, re-test. This is also the first use of the deploy path.

---

## 9. Phase 7 — Backups, NAS pull and monitoring (build in parallel, before cutover) 🤖 + 🧑

Everything here runs against the rehearsal copy, so cutover night contains no configuration work.

### 7A. Off-site to R2 (or Storage Box) 🧑 + 🤖

| # | Step | Where | Verify | Undo |
|---|---|---|---|---|
| 7A.1 | Cloudflare → R2 → create bucket `fieldkit-backups` (location hint: North America). Create an **API token scoped to this bucket, Object Read & Write**. Store in Vaultwarden. | 🧑 CF | Bucket exists | Delete |
| 7A.2 | `apt install rclone`; as `letize`: `rclone config` → remote `r2` type `s3`, provider `Cloudflare`, keys, endpoint `https://<account-id>.r2.cloudflarestorage.com`. `chmod 600 ~/.config/rclone/rclone.conf`. | 🤖 prod (Chris pastes keys) | `rclone lsd r2:` | — |
| 7A.3 | Add to the repo `ops/backup/fieldkit-offsite.sh`: `rclone copy --immutable ~/backups/fieldkit/daily r2:fieldkit-backups/daily` then `rclone copyto ~/backups/fieldkit/last-success r2:fieldkit-backups/last-success`. On the 1st of the month also `rclone copy ~/backups/fieldkit/latest/ r2:fieldkit-backups/monthly/$(date -u +%Y-%m)/`. No `--delete`: R2 keeps what prod prunes. | 🤖 | Manual run; `rclone ls r2:fieldkit-backups` shows the snapshot | — |
| 7A.4 | R2 lifecycle rule: delete objects under `daily/` after 90 days. `monthly/` kept indefinitely (≈ 9 MB × 12/yr). | 🧑 CF | Rule listed | — |
| 7A.5 | Cron line (installed at cutover with the rest): `25 7 * * * ~/docker/fieldkit-prod/fsm-system/ops/backup/fieldkit-offsite.sh >> ~/logs/fieldkit-offsite.log 2>&1` (10 min after the 07:15 snapshot; the snapshot takes seconds). | — | — | — |
| 7A.6 | **Restore test from R2**, once: `rclone copy r2:fieldkit-backups/daily/<stamp> ~/restore/r2test/ && (cd ~/restore/r2test && sha256sum -c SHA256SUMS)` | 🤖 | all OK | — |

### 7B. NAS pull from Hetzner 🤖 (prototype on ubuntu-test first, per Chris's rule)

| # | Step | Where | Verify | Undo |
|---|---|---|---|---|
| 7B.1 | On prod, authorize the **existing** `fieldkit-backup-pull` public key (from ubuntu-services `~/.ssh/fieldkit_backup_pull.pub`) in `~/.ssh/authorized_keys` with the same restriction: `command="/usr/bin/rrsync -ro /home/letize/backups/fieldkit",restrict ssh-ed25519 AAAA... fieldkit-backup-pull`. Same key, new host: nothing to generate. | 🤖 prod | `ssh -i ~/.ssh/fieldkit_backup_pull letize@fieldkit-prod` from ubuntu-services prints the rrsync usage error (shell denied) | Remove line |
| 7B.2 | Copy the pull script found in 0.5 to ubuntu-test as `fieldkit-pull-hetzner.sh`; change the source host `10.83.70.10` → `fieldkit-prod` (MagicDNS) or `100.x.y.z`; change the destination to a **scratch** dir; keep the 36 h staleness check, the checksum verify, the Pushover call. | 🤖 ubuntu-test | Dry run pulls the rehearsal snapshot into scratch, checksums OK, Pushover silent | — |
| 7B.3 | Install the real unit on ubuntu-services as a **second** timer `fieldkit-pull-hetzner.timer`, destination `/nas/hdd/ubuntu_backups/fieldkit-hetzner/` (separate folder for the parallel window), 07:45 UTC. Add `known_hosts` entry for `fieldkit-prod`. | 🤖 ubuntu-services | `systemctl list-timers` shows both; next morning both ran | `systemctl disable --now` |
| 7B.4 | After cutover + 7 clean days (§P10): retire `fieldkit-pull.timer` (the ubuntu-business one), and either merge the folders or just keep pulling into `fieldkit-hetzner/` and leave the old folder as the pre-migration archive. | — | — | — |
| 7B.5 | NAS retention: nothing prunes today (0.15). Add a TrueNAS cron or a line in the pull script: keep 90 dailies + everything under a `monthly/` copy. Low priority, but cheap. | 🤖 | — | — |

### 7C. Monitoring 🧑🤖

| # | Step | Where | Verify | Undo |
|---|---|---|---|---|
| 7C.1 | Uptime Kuma (letizecloud): **HTTP(s) monitor** on `https://fieldkit-new.cletize.com/login` now; change the URL to `https://fieldkit.cletize.com/login` at cutover step 9.11. Keyword check for the string `Sign in` (or whatever the login page shows) so a 200 from the wrong app still alerts. Interval 60 s, retries 3, Pushover notification. | 🧑 Kuma | Pause/unpause test fires Pushover | Delete monitor |
| 7C.2 | Kuma **push monitor** `fieldkit-backup`: heartbeat interval 86400 s, retry/grace 21600 s → alerts if no push within **30 h** (tolerates one late pull, not two missed days). Append to `fieldkit-backup.sh`'s success path (new commit): `curl -fsS -m 10 "${BACKUP_PUSH_URL:-}" >/dev/null \|\| true` with `BACKUP_PUSH_URL` in the `letize` crontab environment or `~/.config/fieldkit/backup.env` sourced by the script. The push URL targets letizecloud; if Kuma is only on Tailscale, the ACL rule in §P3 allows prod → `100.118.85.33:3001`; if Kuma is public, drop that rule. | 🧑🤖 | Manual backup run turns the monitor green | — |
| 7C.3 | Kuma **push monitor** `fieldkit-disk`: a 15-line `~/bin/disk-check.sh` on prod, systemd timer every 6 h: **[R1]** `df --output=pcent /`; if ≥ **70 %**, push with `?status=down&msg=root 71%`; else `?status=up`. Include memory use (`free -m`) in the `msg` either way, and treat sustained swap use as the signal to plan a resize. Kuma alerts via Pushover. (Threshold 70 % within the brief's 60–75 %.) | 🤖 prod | Temporarily set the threshold to 5 % → Pushover fires → restore | — |
| 7C.4 | Second opinion from a different provider: on ubuntu-services, systemd timer every 5 min: `curl -fsS -m 15 -o /dev/null https://fieldkit.cletize.com/login \|\| pushover "FieldKit public check failed from home"` with a 3-strike counter so a blip doesn't page. Uses the same Pushover tokens the pull script uses. (Installed pointing at `fieldkit-new` now; URL switched at 9.11.) | 🤖 ubuntu-services | Point it at a bad URL briefly → alert | disable timer |
| 7C.5 | n8n FieldKit health checks on letizecloud (0.9): if they use the public hostname, **no change**; if they use an IP, retarget at 9.11 or retire in favour of Kuma. **Pause them during the cutover window** so the maintenance stop doesn't page Chris. | 🧑 n8n | — | — |
| 7C.6 | **[R1] Hetzner backups add-on not bought** (would be ~€6.40/mo on a CPX21). The data is covered three times: local pg_dumps, R2 and the NAS. All the add-on buys is a faster whole-OS rebuild, and this plan *is* the rebuild runbook. Optionally take a free-to-create, cheap-to-keep manual **snapshot** after Phase 2 (base build done) as a rebuild shortcut. | — | — | — |

### 7D. Deploy mechanism 🤖 (see §5 for the design; build and test it against the rehearsal copy)

| # | Step | Where | Verify | Undo |
|---|---|---|---|---|
| 7D.1 | New in repo: `ops/deploy/deploy.sh` (runs on prod), `ops/deploy/migrate.sh` (applies `phase1/fieldkit_phase1/database/migrations/NNN_*.sql` not yet in `schema_migrations`, to all four DBs, in a transaction per file per DB), migration `0NN_schema_migrations.sql` creating that table and seeding it with every migration number already applied to production (get the list by diffing `information_schema` as CLAUDE.md suggests, or simply seed all existing files, since production has them all). | 🤖 build VM | Unit-tested on the dev stack (§6) | — |
| 7D.2 | On the build VM: `ssh-keygen -t ed25519 -f ~/.ssh/fieldkit_deploy -N '' -C fieldkit-deploy`. On prod `authorized_keys`: `command="/home/letize/bin/deploy-entry.sh",restrict ssh-ed25519 AAAA... fieldkit-deploy`. `deploy-entry.sh` reads `$SSH_ORIGINAL_COMMAND`, accepts only `deploy <40-hex-sha>` or `status`, and execs `deploy.sh`. The build VM can therefore trigger deploys and nothing else. | 🤖 both | `ssh -i ~/.ssh/fieldkit_deploy letize@fieldkit-prod status` prints the running sha; `ssh ... ls` is refused | Remove key line |
| 7D.3 | `deploy.sh <sha>`: (1) `fieldkit-backup.sh` (pre-deploy snapshot, tagged `pre-deploy-<sha>`); (2) `git -C fsm-system fetch && git checkout <sha>`; (3) `migrate.sh`; (4) if `requirements.txt` or `Dockerfile` changed since the previous sha → `docker compose up -d --build app`, else **[R1] a graceful reload: `docker compose kill -s HUP app`**. Gunicorn swaps workers without dropping requests, so a mid-day deploy gives users no errors. Keep `restart` as the fallback if the HUP doesn't pick up the change; (5) wait for `curl -fsS http://127.0.0.1:3000/login`, 10 tries; (6) on failure: `git checkout <previous sha>` + restart, exit 1 with a loud message. **Migrations are not auto-reverted**; the pre-deploy snapshot is the way back (document that). Write the sha to `~/.fieldkit-deployed`. | 🤖 | Deploy a no-op commit to the rehearsal copy; then deploy a deliberately broken commit and watch it revert | — |
| 7D.4 | Chris's approval is a human step: the session says "ready to deploy `<sha>`: <summary of commits, migrations included>", Chris says "deploy", the session runs the ssh command (Claude Code's safety check will prompt; Chris approves it). | 🧑🤖 | — | — |

---

## 10. Phase 8 — Cutover 🧑🤖

### Pre-flight (the day before)

- [ ] Rehearsal passed (§P6) and the deploy path works (7D.3 tested).
- [ ] Chris O confirmed not working during the window; office users told "FieldKit will be down ~30 min at 11 pm". **[R1] Window: Friday 23:00–00:00 ET** (Saturday 03:00–04:00 UTC: after the 01:00 UTC `nightly`, well before 06:30 geocode / 07:15 backup). Chris chose Friday so he has the weekend to fix anything. The first unattended jobs on the new box (Saturday geocode, backup, R2 copy, NAS pull) then run while he's around to watch.
- [ ] `fieldkit` removed from ddclient (5.4) — confirmed days ago.
- [ ] Pi-hole / Unbound overrides for `fieldkit.cletize.com` removed if any (0.4). Chris's own devices must see the real path.
- [ ] Kuma and the home check still pointed at `fieldkit-new` (they switch at 9.11). n8n FieldKit checks paused (7C.5).
- [ ] Cutover crontab prepared on prod as `~/crontab.prod` (copied from ubuntu-business `crontab -l`, plus 7A.5's line; paths unchanged) — **not installed**.
- [ ] Real `RESEND_API_KEY` in Chris's clipboard/Vaultwarden, ready to paste (9.14).
- [ ] Rollback steps (§P8b) open in another window.

### Runbook (estimated 35 min; stop-the-clock points marked)

| # | Step | Where | Time | Verify |
|---|---|---|---|---|
| 9.1 | **Go/no-go #1 (Chris):** rehearsal green, nobody logged in (`select count(*) from user_sessions where ... recent` or just ask), Hetzner + tunnel healthy (`curl https://fieldkit-new.cletize.com/login` → 200). | 🧑 | T+0 | — |
| 9.2 | On ubuntu-business: **disable cron** so nothing writes mid-copy: `crontab -l > ~/crontab.backup-$(date +%F) && crontab -r`. | 🤖 old | T+1 | `crontab -l` → "no crontab" |
| 9.3 | On ubuntu-business: **stop the app** (db stays up): `cd ~/docker/fieldkit-prod && docker compose stop app`. Users now see Cloudflare 502. (Downtime starts.) | 🧑🤖 old | T+2 | `docker compose ps` |
| 9.4 | On ubuntu-business: **final snapshot**: `bash fsm-system/ops/backup/fieldkit-backup.sh`; note the stamp `FINAL`. | 🤖 old | T+3 | `cat ~/backups/fieldkit/last-success` is now; `ls daily/` |
| 9.5 | Push it to prod (DMZ → Tailscale → prod, allowed by ACL): `rsync -a ~/backups/fieldkit/daily/$FINAL/ letize@fieldkit-prod:~/restore/$FINAL/` | 🤖 old | T+4 | On prod: `sha256sum -c SHA256SUMS` all OK |
| 9.6 | On prod: `docker compose stop app` (rehearsal copy stops). | 🤖 prod | T+5 | — |
| 9.7 | On prod: restore exactly as 6.3–6.5 (globals, drop + `pg_restore --create` × 4, untar uploads **after `rm -rf ~/docker/fieldkit-prod/uploads/*`** so rehearsal-era files can't linger). | 🤖 prod | T+6 → T+11 | Row counts equal the old server's (run the same five counts on ubuntu-business's db container, which is still up) |
| 9.8 | On prod: `docker compose start app`; `curl -fsS http://127.0.0.1:3000/login`. | 🤖 prod | T+12 | 200 |
| 9.9 | **Go/no-go #2 (Chris):** log in on `https://fieldkit-new.cletize.com` from the phone; see today's latest sales visit / work order (proves the FINAL snapshot, not the rehearsal one). | 🧑 | T+14 | If not → **rollback A** |
| 9.10 | **DNS switch** (Chris, Zero Trust → Tunnels → `fieldkit-prod` → Public hostnames → Add `fieldkit.cletize.com` → `http://app:5001`). Cloudflare will refuse because an A record exists: first **delete the `fieldkit` A record** in the DNS tab, then add the hostname (creates the CNAME). The gap is seconds and the record was proxied before and after, so **clients see no IP change** — the switch happens inside Cloudflare; no client DNS caching is involved. Keep `fieldkit-new` for now. | 🧑 CF | T+15 | `curl -sI https://fieldkit.cletize.com/login` from phone → 200 and the response has header `cf-ray`; the login page's company branding is FieldKit's |
| 9.11 | Repoint monitors: Kuma HTTP monitor URL → `https://fieldkit.cletize.com/login`; the ubuntu-services check → same; un-pause n8n checks (retargeted if they used IPs). | 🧑🤖 | T+17 | Kuma green |
| 9.12 | On prod: **install cron**: `crontab ~/crontab.prod`. (Only now: there is exactly one production again — trap T4.) | 🤖 prod | T+18 | `crontab -l`; wait for the next `*/15` `uninvoiced` tick → `~/logs/fieldkit-jobs.log` gets a line, `/settings/company` shows the run |
| 9.13 | **Go/no-go #3 (Chris): end of the rollback-without-loss window.** From here on, every write by a user goes to Hetzner. | 🧑 | T+20 | — |
| 9.14 | On prod: 🧑 Chris pastes the real `RESEND_API_KEY` into `.env`; 🤖 `docker compose restart app`; verify `/settings/company` invoice page now says email is configured. Send one test email **to Chris** (password-reset to his own account, or a statement to his own address). | 🧑🤖 prod | T+22 | Email arrives; links in it point at `https://fieldkit.cletize.com/...` |
| 9.15 | On ubuntu-business: **stop the old stack for good**: `docker compose down` (containers removed, `pgdata` volume kept), then `mv ~/docker/fieldkit-prod ~/docker/fieldkit-prod.RETIRED-$(date +%F)`. Nothing can serve or write the stale copy, and the cron is already gone (9.2). The `RETIRED` directory is the fast rollback source for 7 days. | 🧑🤖 old | T+25 | `docker ps` shows only `statements-*` |
| 9.16 | Ask Chris O (next morning) to open FieldKit on the tablet and confirm it loads and his session is still valid (same secret key → it should be). If the tablet is on office wifi with a stale LAN DNS cache, `ipconfig /flushdns` equivalent or just toggling wifi fixes it. | 🧑 | next day | — |
| 9.17 | Watch the first 24 h: 07:15 backup on prod, 07:25 R2 copy, 07:45 NAS pull (`fieldkit-pull-hetzner`), Kuma push monitors green. The **old** pull timer `fieldkit-pull.timer` will **alert at 07:45** because ubuntu-business produced no snapshot — either disable it before bed (`systemctl disable --now fieldkit-pull.timer` on ubuntu-services) or expect the Pushover and ignore it. Prefer disabling it. | 🤖 | next day | All three Pushover-silent, Kuma green |

### Rollback

**A. Before 9.10 (DNS not switched) — zero data loss, ~3 min:** on ubuntu-business `docker compose start app`, `crontab ~/crontab.backup-<date>`. Production never left home. Investigate on Hetzner at leisure.

**B. Between 9.10 and 9.13 (DNS switched, cron on, but no users have written yet) — zero data loss, ~5 min:** Cloudflare: remove `fieldkit.cletize.com` public hostname from the tunnel, re-create the **A record to the home WAN IP, proxied** (the value is in ddclient's logs/OPNsense WAN status); on prod `crontab -r`; on ubuntu-business start app + cron as in A. Re-add `fieldkit` to ddclient if it was there.

**C. After 9.13 — rollback loses whatever was written on Hetzner since 9.13**, unless reversed properly: on prod `crontab -r && docker compose stop app`, run `fieldkit-backup.sh`, push the snapshot to ubuntu-business (**allowed direction: house pulls** — so from ubuntu-services: `rsync` from prod to the NAS, then to ubuntu-business), restore there with the `backups.md` procedure, then B. ~20 min. After the first business day the practical answer is "fix forward on Hetzner"; the NPM entry and `RETIRED` directory stay for 7 days as insurance, then go (§P10).

---

## 11. Phase 9 — Post-cutover cleanup (after 7 clean days) 🧑🤖

**Checkpoint 3 — Chris OKs decommissioning at home.**

| # | Step | Where |
|---|---|---|
| 10.1 | NPM: delete the `fieldkit.cletize.com` proxy host. Delete `fieldkit-new.cletize.com` from the tunnel and DNS (or keep it as a permanent "direct" name for testing — harmless; if kept, note it in docs). Remove the Access policy from 5.5 if any. | 🧑 NPM / CF |
| 10.2 | OPNsense: remove any NAT/firewall rule that existed only for the FieldKit DMZ path (0.x findings). Leave the statements site's path alone. | 🧑 OPNsense |
| 10.3 | ubuntu-services: `systemctl disable --now fieldkit-pull.timer` (old), keep `fieldkit-pull-hetzner.timer`. Remove the old unit files. Keep the key: it is now also the build VM's pull key if Chris wants build-VM snapshots pulled (optional). | 🤖 |
| 10.4 | ubuntu-business: delete `~/docker/fieldkit-prod.RETIRED-*` **after** confirming the NAS holds the FINAL snapshot and a successful restore test from the NAS copy of FINAL has been done once (`backups.md` procedure into a scratch DB on the dev stack). `docker volume rm fieldkit-prod_pgdata`. | 🧑🤖 |
| 10.5 | Proxmox: VM 101 stays in the weekly job (it's the build VM + statements). Nothing to change; note it in docs. | — |
| 10.6 | Turn ubuntu-business into the build VM: clone the repo fresh to `~/dev/fsm-system` (or keep the existing checkout, now the *only* purpose of the machine), set up the dev stack (§6), install the deploy key (7D.2). CrowdSec/pf bouncer entries for FieldKit: none to remove unless specifically created. | 🤖 |
| 10.7 | **[R1] Approved, do it:** nightly `pg_dump` of `fsm_prod` to `~/backups/statements/`, pulled by the existing homelab pattern. It removes the "weekly VM image is the only backup of Michele's tax data" risk. Can be done any time, even before the migration. **Never touch `statements.cletize.com`'s DNS, NPM entry or stack** during this work. | 🤖 |
| 10.8 | Docs, in one commit on the build VM: `FIELDKIT_STACK_REFERENCE.md` (new request path: CF → tunnel → compose), `fieldkit-prod-server.md` (new host, cloudflared service and its pinned version; [R1] no volume or symlinks), `backups.md` (R2, new pull source, Kuma push), `cron-jobs.md` (+offsite line, +disk timer), `CLAUDE.md` (production is on Hetzner; **never edit it in place; deploy via `deploy.sh` with Chris's OK**; dev stack location), `CURRENT-STATUS.md` (migration done, date, server type/price), new `docs/DEPLOYMENT/deploying.md` (§5 as runbook), `docs/DEPLOYMENT/dev-environment.md` (§6), a `D-###` entry for each decision above (hosting size, R2, ACL, deploy design, dev design, kill switch). Update `FIELDKIT_PROJECT_REFERENCE.md`'s infra inventory. Add `ops/deploy/*`, `ops/backup/fieldkit-offsite.sh`, `ops/monitoring/disk-check.*`, the ACL JSON (as `ops/tailscale/acl.json`, comment-stripped copy of what's in the console). | 🤖 |
| 10.9 | Update the Letize Homelab project notes: ubuntu-business role change, new Tailscale node and ACL, ddclient change, new NAS folder, new timers, retired NPM host. | 🧑 (or the homelab session) |

---

## 12. §5 Deploy design (answers to the brief's questions)

- **Bind-mount + `git checkout`, not image builds.** Reasons: it's what runs today; a rebuild on a 2 GB box is slow and memory-hungry; the app is pure Python with pinned requirements, so "the image" changes only when `requirements.txt`/`Dockerfile` do, and `deploy.sh` detects that and rebuilds then. Revisit when there's a CI pipeline or a second server.
- **Deploy a sha, not "main".** The session tests sha X on the build VM, Chris approves sha X, production checks out sha X. Branch heads drift; shas don't.
- **Migrations:** `migrate.sh` + `schema_migrations(number int primary key, applied_at timestamptz)` in each DB, applied inside one transaction per file per DB. If DB 3 of 4 fails, DBs 1–2 are migrated and 3–4 aren't → the script stops and says so; fixing forward or restoring the pre-deploy snapshot are the options. That is strictly better than today's hand-applied-and-sometimes-forgotten state (D-112). Rule stays: migration file and code in the same commit.
- **Rollback for a bad deploy:** code → `deploy.sh <previous sha>` (same path, 30 s). Code + migration → restore the `pre-deploy-<sha>` snapshot's DBs (the `backups.md` scratch-and-rename procedure) then `deploy.sh <previous sha>`. Destructive migrations (dropping columns) are banned anyway by the soft-delete culture; add "no destructive migrations without a two-release deprecation" to `CLAUDE.md`.
- **Build VM → production:** Tailscale only, SSH on prod's Tailscale IP only, forced-command key (`deploy`/`status` and nothing else). Chris's own key is the only unrestricted one.
- **Claude Code auto-mode:** the executing session will be prompted at the `ssh ... deploy <sha>` command; that prompt *is* the approval moment. Don't pre-approve it.

## 13. §6 Dev environment design

- **Where:** ubuntu-business, `~/docker/fieldkit-dev/`, its own compose project (`-p fieldkit-dev`), own `pgdata-dev` volume, app published on `127.0.0.1:3001`. If 0.13 found an existing "staging" on 3001, convert it rather than add a third.
- **Address:** `tailscale serve --bg --https=443 http://127.0.0.1:3001` on ubuntu-business → `https://ubuntu-business.<tailnet>.ts.net`. Needs MagicDNS + HTTPS certificates enabled in the Tailscale admin console (0.7, 🧑). Only tailnet devices can reach it; no public name, no Cloudflare, no second-level subdomain problem. Chris O never needs it; Michele reviewing a feature would need Tailscale on her PC, which is the one trade-off (Q6). Fallback if that becomes a real need: `fieldkit-dev.cletize.com` on the *same* tunnel? No — the tunnel is on Hetzner and dev is at home; it would need a second tunnel on the build VM plus Cloudflare Access. Possible, later, not now.
- **Email can't happen, in three layers:** (1) `.env` has `RESEND_API_KEY=` empty; (2) **code**: add `FIELDKIT_ENV` to `app.py` — when it equals `dev`, `_send_email_via_resend` and the password-reset sender raise `RuntimeError('email disabled in dev')` before touching `_resend`, and the compose file for dev sets `FIELDKIT_ENV=dev`; production sets `FIELDKIT_ENV=prod` and `deploy.sh` refuses to run if it's anything else; (3) **data**: the refresh script rewrites every email column to `<local>@example.invalid` (customers, contacts, prospects, users except Chris's own row so reset-link testing works against his address, `company_settings` recipient fields, statement recipients) and sets `scheduled_alerts_enabled=false` for all four. Also `APP_BASE_URL=https://ubuntu-business.<tailnet>.ts.net` so any link anyone copies points at dev.
- **Refresh:** `ops/dev/refresh-dev.sh` on the build VM: takes the snapshot path pushed by ubuntu-services (`rsync` from the NAS copy to `ubuntu-business:~/restore/` — VLAN30 → VLAN70 is already allowed and is the direction the house permits), restores into the dev Postgres exactly like 6.3–6.5 (`-p fieldkit-dev`), runs the scrub SQL, restarts. Run on demand, or weekly on Sunday. Uploads: restore too (they're needed for the PDF viewer) — they're real documents, but they're already on this VM today.
- **Test the kill switch** once with a real key present in dev `.env` deliberately: click Send → must raise, not send. Then remove the key again. Belt, braces, and a third thing.

---

## 14. Order-of-operations traps and silent failures (consolidated)

| # | Trap | Where it bites | Avoided by |
|---|---|---|---|
| T1 | `FLASK_SECRET_KEY` missing/misnamed → random per worker → random logouts, nothing logged | any restore, any `.env` edit | 4.4 checks, 6.6 check, `deploy.sh` asserts the five keys exist and are non-empty (except Resend, which it checks is non-empty **in prod**) |
| T2 | ddclient rewrites the tunnel CNAME back to an A record | hours to a day after cutover; FieldKit flaps between home (now dead) and Hetzner | 5.4 before cutover |
| T3 | Split DNS: Pi-hole/Unbound override sends LAN devices to NPM → Chris sees "works" or "broken" that nobody else sees | after cutover | 0.4; test from cellular at 9.10 |
| T4 | Two production crons: duplicate `uninvoiced`/`nightly` rows; duplicate emails later | rehearsal, cutover | cron installed only at 9.12, after old cron removed at 9.2; `deploy.sh` never touches cron |
| T5 | `globals.sql` sets the `fieldkit` role's password to production's; if `.env` on Hetzner has a different `DB_PASSWORD`, the app can't connect after the restore even though it could before | 6.3, 9.7 | Same password in `.env` (4.4); 6.6 verifies |
| T6 | `init/` first-boot scripts already created the four DBs → a naive `pg_restore` into them errors on existing objects | 6.4 | drop + `--create` |
| T7 | `~/logs` missing → every cron line fails, no email, no backup, no alert for days | first night | 2.11; Kuma push monitor catches a missing backup within 30 h anyway |
| T8 | Resend key present on Hetzner before cutover → a rehearsal click emails a customer | rehearsal | key empty until 9.14; the app itself shows "not configured" |
| T9 | Sales map blank: Range requests or `max_age` caching through Cloudflare behave differently than through NPM | first map load after cutover | tested on `fieldkit-new` in 6.7 (zoom in to street level, which forces many tile ranges) |
| T10 | Old stack left running: a tablet with a stale route, or a curious admin on LAN, writes to the home copy | days after | 9.15 `down` + rename; NPM host deleted at 10.1 |
| T11 | Hetzner snapshot/backups add-on gives a false sense of data safety (crash-consistent, 7 days) | months later | 7C.6 wording in docs: the pg_dumps are the backup |
| T12 | Nightly tarball of all uploads (§0.5) grows with photos until the disk is full of 14 copies of the same photos ([R1] moot while photos go to R2, §17) | 6–12 months after the mobile app ships | Backlog item: change `fieldkit-backup.sh` to tar only `uploads/**/*.pdf` + metadata and `rclone sync` the photo tree to R2 incrementally; disk alert (7C.3) is the backstop |
| T13 | Tailscale node key expiry on an untagged node → SSH and pulls die in 180 days with no warning | 6 months later | tagged node (2.4); confirm "Expiry disabled" shows in the console |
| T14 | Rescaling or re-creating `letizecloud` re-prices it at 2026 rates | any time | §0.1 note in docs and homelab notes |
| T15 | Ubuntu unattended reboot at 06:00 UTC mid-backup or mid-geocode | random mornings | 2.10 no auto-reboot; monthly manual patch-reboot in a window |
| T16 | `postgres:16` floating tag pulls a newer minor on a rebuild; fine, but a *major* bump (someone "fixes" it to `postgres:17`) can't read `pgdata` | any `up --build` | pinned tag (4.3); note in `fieldkit-prod-server.md` |
| T17 | `import_job_dates.py` attaches to `statements_default` network — impossible from Hetzner | whenever that import resumes | documented as "run against a dump on the build VM" |
| T18 | Kuma and prod both on Hetzner → a Hetzner-wide outage is silent | rare | 7C.4 home check |
| T19 | The old `fieldkit-pull.timer` alerts every morning after cutover | 07:45 UTC day 1 | 9.17 |
| T20 | `APP_BASE_URL` default in code is a two-level subdomain; a future "cleanup" that drops it from `.env` breaks every email link | later | `deploy.sh` asserts it; mention in docs |
| T21 | Cloudflare Tunnel public hostname can't be added while an A record exists; deleting the A record first means a few seconds of 1016/530 | 9.10 | Known, ~5 s, during the maintenance window anyway |
| T22 | IPv6-only server to save €0.50: Census geocoder and others fail silently (jobs.py logs errors nobody reads) | nightly geocode | keep IPv4 (1.3) |

---

## 15. Questions for Chris — **[R1] answered 2026-10-29**

- **Q1 Size/location:** **Ashburn CPX21**, no backups add-on, ~€32.5/mo, in a new FieldKit-only Hetzner account (§0.1).
- **Q2 Off-site:** **Cloudflare R2.** Job photos go there too later, behind a switchable S3-compatible storage layer (§17).
- **Q3 `letizecloud`:** in Germany. Measured 128 ms round trip from the house, which ruled out a German server for
  production. Its old price stays as long as it isn't resized or re-created (T14).
- **Q4 Hostname:** FieldKit is `fieldkit.cletize.com` (confirmed in the live `.env`). The statements site is
  **`statements.cletize.com`**. Leave it, its NPM entry and its stack completely alone.
- **Q5 Tailscale ACL:** **yes**, replace the default allow-all with §P3.
- **Q6 Dev access:** Tailscale-only. Chris will add Tailscale to Michele's PC when she needs dev.
- **Q7 sudo on prod:** **yes**, passwordless sudo for `letize`.
- **Q8 Resend test mode:** not needed. Dev already blocks email three ways (§6).
- **Q9 Window:** **a Friday night**, 23:00 ET (§10 pre-flight).
- **Q10 Statements backup:** **yes**, do it (10.7).
- **Q11 Cloudflare Access on `/login`:** later, after the mobile app's token auth exists.
- **Also confirmed:** Cloudflare account 2FA. Chris believes it's on; check before Phase 5.
- **Already verified on ubuntu-business, 2026-10-29:**
  - 0.13: no second "staging" stack exists. `docker ps` shows only `fieldkit-prod-*` and `statements-*`.
  - 0.10: the crontab has the 7 entries listed in the brief.
  - 0.12: `APP_BASE_URL=https://fieldkit.cletize.com`.

## 16. Risks, ranked by how much they'd hurt

1. ~~Budget reality~~ **[R1] Resolved:** CPX21 at ~€32.5, slightly over the €30 target by Chris's choice. A future across-the-board increase (like April 2026's) can still raise it.
2. **Secrets mismatch on restore (T1, T5).** The most likely cause of a scary-looking cutover ("nobody can log in", "app can't reach DB"). Fully preventable; the plan checks it twice.
3. **Tailscale ACL mistake.** Too loose → Hetzner can reach the house (silent, no symptom). Too tight → the NAS pull or the deploy key fails (noisy, caught next morning). The verify step in §P3 tests both directions.
4. **ddclient/split-DNS ghosts (T2, T3).** Flapping or invisible breakage days later. Cheap to prevent, expensive to diagnose.
5. **Unnoticed email path during rehearsal (T8).** A customer gets a statement from a test. Prevented by the empty key; the kill switch adds a second layer later.
6. **[R1] RAM at 30–50 users.** CPX21 (4 GB), with the app tuned and photos off-box, should hold. The memory figure in the disk-check push (7C.3) is the early warning; the fix is a resize to CPX31.
7. **Local-snapshot bloat from photos (T12).** Fails in 6–12 months; disk alert is the backstop; fix is a small script change — put it in the backlog now.
8. **Both watchers on Hetzner (T18).** Covered by 7C.4.
9. **Off-site copy depends on one R2 token on the server.** If the server is compromised, the attacker can read (not delete, with lifecycle-only deletion and a write-only token where supported) the backups. Mitigation: R2 token scoped to the one bucket; snapshots contain customer data but not `.env`. Acceptable at this size; revisit with photos.
10. **`fsm_prod` statements data has only a weekly crash-consistent image (10.7).** Not caused by the migration, but the migration is when someone is finally looking.

---

## 17. [R1] Before office go-live (separate from the migration, tracked here so it isn't lost)

These come from sizing for ~30 users at go-live and ~50 later. Speed for the techs in the field is the standing rule.
Each is a normal build-VM change, deployed with §5's process after the migration.

1. **App tuning.** Today gunicorn runs **2 sync workers**, one request each, so one slow PDF export ties up half the app.
   - Move to threaded workers, for example `--workers 3 --threads 4 --worker-class gthread`, sized to the CPX21's RAM.
   - Add a **Postgres connection pool**. Today the app opens a new `psycopg2` connection for every request, per database.
   - Confirm Postgres `max_connections` and memory settings against the pool size.
   - Load-test with a few dozen simulated users before go-live.
2. **Photo storage on R2 behind a switchable layer** (mobile app work):
   - talk to it through the **S3 API**, with endpoint, bucket and keys in `.env`;
   - photos never stored on the server disk;
   - thumbnails generated once;
   - 26-month retention as a bucket lifecycle rule;
   - a separate bucket and token from the backups.

   Switching providers later is a configuration change plus `rclone` copying the files across.
3. **Backup script, once photos exist:** keep photos out of the nightly tarball. The R2 photo bucket gets its own
   protection (versioning or a second-provider copy, decided at mobile-app design time).
4. **Accounts and billing:** set up the LLC (or settle which company owns FieldKit) before office go-live. Then move the
   Hetzner, Cloudflare, Resend, GitHub and Apple Developer accounts and billing to it in one sitting. Until then,
   costs are tracked in Firefly III under tag `fieldkit`.
