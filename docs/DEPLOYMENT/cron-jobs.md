# FieldKit scheduled jobs (cron)

*Installed 2026-09-19, Increment 2.5 of `docs/FIELDKIT_BUILD_DIRECTIVE_2026-09.md` §3.5.*

## Where it lives

Installed under the `letize` user's own crontab (`crontab -l` to view, `crontab -e`
to edit) on ubuntu-business — **not** `/etc/cron.d/fieldkit`, because passwordless
`sudo` wasn't available in the session that built this. The directive itself
documents this as the accepted fallback ("If `sudo` for `/etc/cron.d` is unavailable
to you, write the crontab under the `letize` user's own `crontab -e` instead and note
it"). If `sudo` becomes available later, this can be moved to `/etc/cron.d/fieldkit`
for a more discoverable, version-controllable location — functionally identical
either way, since `letize` is the same user cron would run it as in `/etc/cron.d`.

## Schedule

```
0 1 * * *    jobs.py nightly              — customer_flags, extraction day-count upkeep,
                                             Missed Today logging, day-5+ escalation email
*/15 * * * * jobs.py uninvoiced           — flags Completed WOs with no invoice after 1h
0 17 * * 1-5 jobs.py eod_escalation       — 5pm weekday digest of still-uninvoiced jobs
0 8 * * 1    jobs.py weekly_sales_report  — placeholder; no sales CRM yet (Stage 3)
```

Each line runs `docker compose exec -T app python jobs.py <subcommand>` for all four
companies in one process (`jobs.py` loops `ALL_COMPANY_KEYS`), logging to
`~/logs/fieldkit-jobs.log`.

## The master on/off switch

Every job's *computation* (customer_flags, extraction day counts, `job_runs`
bookkeeping) always runs. Only the **email-sending** step inside `uninvoiced`,
`eod_escalation`, and the nightly job's day-5+ escalation check is gated by
`company_settings.scheduled_alerts_enabled` — a **per-company** switch, defaulting
**FALSE**, toggled via `/settings/company` on the "Scheduled Jobs" panel (admin only).

**As of this writing, the switch is OFF for all four companies.** The cron schedule
above is live and will fire on schedule, but it will not send a single real email
until someone explicitly checks that box for a given company. This was a deliberate
build choice (Chris, 2026-09-19): install and verify the whole pipeline for real
against production data, but leave alerting itself opt-in.

## Verifying it's wired up

`/settings/company` → "Scheduled Jobs" panel shows the last run (timestamp, status,
summary) per job per company — that's the intended way to confirm cron is actually
firing, per the directive. `~/logs/fieldkit-jobs.log` has the raw per-run output.

## Testing note

`_send_email_via_resend` (the one function that ever calls the real Resend API) was
verified end-to-end in `phase1/fieldkit_backend/tests/smoke_scheduled_jobs.py` with
the switch temporarily flipped on inside a monkey-patched test session (Resend itself
mocked, zero real network calls) — confirming the send path actually fires when
enabled, and confirming it sends nothing when the switch is off, before the switch
was restored to its real (off) value. See that test's own safety header for detail.
