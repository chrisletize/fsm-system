# Prompt for the homelab Claude session

*Paste everything below the line into the homelab project's Claude session. It produces
`HOMELAB-CONTEXT-FOR-FIELDKIT-MIGRATION.md`, which Chris gives to Fable alongside
`docs/DEPLOYMENT/HETZNER-MIGRATION-BRIEF.md` in the FieldKit project.*

---

FieldKit (the Flask/Postgres field-service app on ubuntu-business, 10.83.70.10, VLAN70
DMZ) is moving its production off the homelab onto a Hetzner Cloud server. Fable will
write the step-by-step migration plan. It already has a full brief on the FieldKit side
(the app, its Docker stack, cron, backups as ubuntu-business sees them, and the
decisions made). **What it doesn't have is the homelab side.** Please write that up as
one markdown file: `HOMELAB-CONTEXT-FOR-FIELDKIT-MIGRATION.md`.

**Decisions already made, so you know what's relevant:**
- **Production server:** a Hetzner Cloud VM, preferably in the US (Ashburn), at most
  €30 a month.
- **Traffic in:** a **Cloudflare Tunnel**, with no inbound ports open on the server.
- **Admin access:** SSH only over **Tailscale**.
- **ubuntu-business:** stays as the "build" VM (development plus a private dev site),
  and deploys to Hetzner through git with Chris approving each deploy.
- **Statements site:** stays on ubuntu-business.
- **Backups:** the Hetzner server makes nightly snapshots, with an off-site copy at
  Hetzner and a copy on the NAS that the homelab pulls. The rule stays the same:
  **the homelab pulls, nothing reaches into the house.**
- **New monitoring:** uptime, stale-backup and disk-usage alerts (60–75% full), using
  Pushover if possible.

**Check each item live where you can, and mark anything you couldn't verify:**

1. **How FieldKit traffic gets in today:** the Cloudflare DNS record for
   `fieldkit.cletize.com` (proxied or not, record type), the OPNsense NAT/firewall rules
   involved, and the NPM proxy host for it (target, SSL cert, any custom settings).
   Note any other hostnames that point at ubuntu-business, such as the statements site.
2. **Cloudflare account:** any **tunnels already running** (`cloudflared` anywhere in
   the homelab?), Zero Trust/Access already in use, how the `cletize.com` zone is managed,
   and the SSL/TLS mode. Note anything a new tunnel could clash with.
3. **Existing Hetzner footprint:** the monitoring VM Chris runs there. Which project,
   location and server type; how it's reached (Tailscale?); what it monitors and how
   it alerts. Could it watch the new FieldKit server (uptime, disk), or would that be a
   bad idea? Any existing Storage Box or object storage.
4. **Tailscale:**
   - ACLs and tags: what can reach what today. Can ubuntu-services reach a new tailnet
     node?
   - Which nodes are exit or subnet routers, whether MagicDNS and HTTPS certs
     (`tailscale serve`) are enabled, and any key-expiry settings that could cut off a
     server.
5. **FieldKit backup pull on ubuntu-services:**
   - `fieldkit-pull.service`/`.timer` and the script, summarised: paths, checks, how
     Pushover is called, and where the key lives.
   - What would need to change for it to pull from a Hetzner server over Tailscale
     instead of 10.83.70.10 on the LAN.
6. **NAS:** the destination layout and free space, retention rules, and whether
   anything prunes old FieldKit snapshots.
7. **Proxmox:** the backup job covering VM 100–103 (which ID is ubuntu-business?), its
   schedule and retention. Is the statements site's database (`fsm_prod`, in
   `statements-db-1` on ubuntu-business) safely covered by that alone?
8. **Off-site:** LetizeRemote's status and plan, and the replication tasks currently
   erroring.
9. **Alerting:** what Pushover setup exists (app/user tokens are fine to *mention*,
   **never include their values**), and anything else used for alerts.
10. **Anything else touching ubuntu-business** that breaks or needs changing when it
    stops being production: monitoring checks, uptime pings, firewall rules, DNS
    entries, scheduled jobs on other machines, SSH keys installed on it.
11. **Power and internet resilience** at home (UPS, what survived this week's outage).
    The build VM and the NAS copy will still live there.
12. **Your own concerns:** anything about the homelab Fable should know that could trip
    up the migration or the "homelab pulls only" rule.

**Rules:**
- **Read only:** change nothing.
- **No secrets:** no passwords, API keys, tokens, private keys or full public keys.
  Name them and say where they live.
- **Facts first:** keep it factual and concise, with tables where useful. Clearly
  separate "verified today" from "from notes/memory".
- **Where to save it:** somewhere Chris can grab it easily, and tell him the path.
