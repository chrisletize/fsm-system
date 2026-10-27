# FieldKit backups

*Set up 2026-10-19 (D-113). The script lives in the repo at `ops/backup/fieldkit-backup.sh`.*

## How it works

ubuntu-business (10.83.70.10) is in the VLAN70 DMZ and **can't reach any LAN address**
(see `FIELDKIT_STACK_REFERENCE.md`). So the backup runs in two halves:

1. **Local snapshot (this server, done).** Cron runs `ops/backup/fieldkit-backup.sh`
   every night at **07:15 UTC** (3:15am EDT / 2:15am EST) and writes to
   `~/backups/fieldkit/`. The log is `~/logs/fieldkit-backup.log`.
2. **Off-box copy (homelab side, NOT YET SET UP).** Something on the trusted side
   (ubuntu-services, 10.83.30.10, or the NAS itself) pulls the snapshots over SSH with
   a read-only key. Until this half exists, the backups sit on the same disk as
   the database and won't survive losing that VM.

## What each snapshot contains

```
~/backups/fieldkit/
├── daily/2026-10-19T0715Z/       one dir per run, UTC-stamped; newest 14 kept
│   ├── fieldkit_getagrip.dump    pg_dump -Fc, one per company DB
│   ├── fieldkit_kleanit_charlotte.dump
│   ├── fieldkit_cts.dump
│   ├── fieldkit_kleanit_sf.dump
│   ├── globals.sql               roles
│   ├── uploads.tar.gz            signed release forms + business-card photos
│   ├── server-config.tar.gz      docker-compose.yml, Dockerfile, init/
│   ├── MANIFEST                  git commit, table counts, upload count
│   └── SHA256SUMS
├── latest -> daily/<newest>
├── last-success                  UTC timestamp of the last good run
├── last-failure                  only exists if a run has ever failed
└── .incomplete-<stamp>/          a run in progress, or a failed run kept for inspection
```

Each run checks every dump with `pg_restore --list` before the snapshot is moved into
`daily/`, so **anything under `daily/` is complete**. About 8.5 MB per snapshot as of
2026-10-19 (mostly uploads).

**`maps/` (the sales-map basemap, ~570 MB) is excluded too**: it's rebuilt from
OpenStreetMap by `ops/maps/refresh-basemap.sh` in about a minute.

**`.env` is deliberately excluded** (DB password, Flask secret key, Resend API key).
Keep a copy in your password manager. Without it, a restore means generating a new
DB password and Flask key (which logs everyone out) and fetching the Resend key from
Resend.

## Homelab side — handoff for setting up the pull

Recommended: run the pull from ubuntu-services (VLAN30, which can already SSH into
VLAN70) and write onto the NAS mount there.

1. **Make a dedicated key** on the puller. Don't reuse `ubuntu-services-backup`;
   that key has an unrestricted shell on ubuntu-business:
   ```
   ssh-keygen -t ed25519 -f ~/.ssh/fieldkit_backup_pull -N "" -C fieldkit-backup-pull
   ```
2. **Authorize it read-only, backup folder only.** Append this line to
   `/home/letize/.ssh/authorized_keys` on ubuntu-business, with the real public key:
   ```
   command="/usr/bin/rrsync -ro /home/letize/backups/fieldkit",restrict ssh-ed25519 AAAA...  fieldkit-backup-pull
   ```
   `rrsync` (already installed at `/usr/bin/rrsync`) limits that key to read-only rsync
   inside the backup folder: no shell, no other files, no writes.
3. **Pull nightly**, after the 07:15 UTC run (e.g. 08:00 UTC). With rrsync, paths are
   relative to the backup root:
   ```
   rsync -a -e "ssh -i ~/.ssh/fieldkit_backup_pull" \
       letize@10.83.70.10:daily/ /mnt/<nas>/fieldkit/daily/
   rsync -a -e "ssh -i ~/.ssh/fieldkit_backup_pull" \
       letize@10.83.70.10:last-success /mnt/<nas>/fieldkit/
   ```
   No `--delete`, so the NAS keeps snapshots after the server prunes its 14. Set NAS
   retention separately (e.g. 90 dailies, plus month-end copies kept longer).
4. **Verify after copying**: `cd /mnt/<nas>/fieldkit/daily/<stamp> && sha256sum -c SHA256SUMS`.
5. **Alert on staleness**: if the pulled `last-success` is more than 26 hours old,
   either the server backup or the pull has stopped. Send that alert through whatever
   the homelab already uses.

Later, Hetzner (Storage Box or object storage) can be a second destination fed from
the NAS copy, so the DMZ box never needs outbound credentials.

## Restoring

Restore into a **scratch database first**, check it, then swap. Never `pg_restore
--clean` straight over a live company DB without a fresh snapshot of its current state.

```
cd ~/docker/fieldkit-prod
SNAP=~/backups/fieldkit/daily/<stamp>
(cd $SNAP && sha256sum -c SHA256SUMS)

# 1. restore to scratch and inspect
docker compose exec -T db psql -U fieldkit -d postgres -c "create database zz_restore"
docker compose exec -T db pg_restore -U fieldkit -d zz_restore --no-owner --exit-on-error \
    < $SNAP/fieldkit_getagrip.dump
docker compose exec -T db psql -U fieldkit -d zz_restore -c "select count(*) from customers"

# 2. replace the live DB (stop the app so nothing writes mid-restore)
docker compose stop app
docker compose exec -T db psql -U fieldkit -d postgres -c "drop database fieldkit_getagrip"
docker compose exec -T db psql -U fieldkit -d postgres -c "alter database zz_restore rename to fieldkit_getagrip"
docker compose start app

# uploads
tar -C ~/docker/fieldkit-prod -xzf $SNAP/uploads.tar.gz
```

**Tested 2026-10-19:** the first snapshot's getagrip dump restored cleanly into a
scratch DB, row counts matched live for customers / work_orders / invoices /
sales_visits / sales_prospects / record_audit / users, checksums verified, and the
scratch DB was dropped. Repeat the test now and then; a backup nobody has restored
isn't known to work.

## Older manual backups

`~/db-backups/<date-reason>/` holds the ad-hoc pre-change dumps from June–September
2026. Left as they are; take one there before any risky manual change, as before.
