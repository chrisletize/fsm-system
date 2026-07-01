# FieldKit — GitHub Raw URLs for Session Startup

Repository: `https://github.com/chrisletize/fsm-system`

## Standard Session Load (paste all at once to Claude)

### Documentation
```
https://raw.githubusercontent.com/chrisletize/fsm-system/main/docs/PROJECT-KNOWLEDGE/CURRENT-STATUS.md
https://raw.githubusercontent.com/chrisletize/fsm-system/main/docs/PROJECT-KNOWLEDGE/SESSION-NOTES.md
https://raw.githubusercontent.com/chrisletize/fsm-system/main/docs/PROJECT-KNOWLEDGE/ACTIVE-SPRINT.md
https://raw.githubusercontent.com/chrisletize/fsm-system/main/docs/PROJECT-KNOWLEDGE/DECISIONS.md
https://raw.githubusercontent.com/chrisletize/fsm-system/main/docs/PROJECT-KNOWLEDGE/FUTURE-PLANS.md
https://raw.githubusercontent.com/chrisletize/fsm-system/main/docs/PROJECT-KNOWLEDGE/HELP-SYSTEM.md
https://raw.githubusercontent.com/chrisletize/fsm-system/main/README.md
```

### Phase 0 — FSM Statement Generator (Production on ubuntu-business)
```
https://raw.githubusercontent.com/chrisletize/fsm-system/main/backend/api/app.py
https://raw.githubusercontent.com/chrisletize/fsm-system/main/backend/api/branding.py
https://raw.githubusercontent.com/chrisletize/fsm-system/main/backend/api/nc_tax_rates.py
https://raw.githubusercontent.com/chrisletize/fsm-system/main/backend/api/tax_processor.py
https://raw.githubusercontent.com/chrisletize/fsm-system/main/scripts/generate_pdf_statement.py
https://raw.githubusercontent.com/chrisletize/fsm-system/main/scripts/generate_test_statement.py
https://raw.githubusercontent.com/chrisletize/fsm-system/main/scripts/import_sf_data.py
```

### Phase 0 — Templates
```
https://raw.githubusercontent.com/chrisletize/fsm-system/main/backend/api/templates/index.html
https://raw.githubusercontent.com/chrisletize/fsm-system/main/backend/api/templates/upload.html
https://raw.githubusercontent.com/chrisletize/fsm-system/main/backend/api/templates/tax-report.html
```

### Phase 1 — Auth Backend (committed April 21, 2026)
```
https://raw.githubusercontent.com/chrisletize/fsm-system/main/phase1/fieldkit_backend/app.py
https://raw.githubusercontent.com/chrisletize/fsm-system/main/phase1/fieldkit_backend/requirements.txt
https://raw.githubusercontent.com/chrisletize/fsm-system/main/phase1/fieldkit_backend/templates/base.html
https://raw.githubusercontent.com/chrisletize/fsm-system/main/phase1/fieldkit_backend/templates/login.html
https://raw.githubusercontent.com/chrisletize/fsm-system/main/phase1/fieldkit_backend/templates/dashboard.html
https://raw.githubusercontent.com/chrisletize/fsm-system/main/phase1/fieldkit_backend/templates/select_company.html
```

### Phase 1 — Database Setup
```
https://raw.githubusercontent.com/chrisletize/fsm-system/main/phase1/fieldkit_phase1/database/init_databases.sql
https://raw.githubusercontent.com/chrisletize/fsm-system/main/phase1/fieldkit_phase1/database/schema/01_core_tables.sql
https://raw.githubusercontent.com/chrisletize/fsm-system/main/phase1/fieldkit_phase1/database/schema/02_customers.sql
https://raw.githubusercontent.com/chrisletize/fsm-system/main/phase1/fieldkit_phase1/database/seed/seed_data.sql
https://raw.githubusercontent.com/chrisletize/fsm-system/main/phase1/fieldkit_phase1/import_sf_customers.py
https://raw.githubusercontent.com/chrisletize/fsm-system/main/phase1/fieldkit_phase1/setup_databases.sh
```

### Database Schema
```
https://raw.githubusercontent.com/chrisletize/fsm-system/main/database/migrations/001_initial_schema.sql
```

---

## What's in GitHub (Verified April 21, 2026)

### ✅ Phase 0 — Committed and current
- Statement Generator (`backend/api/app.py` and supporting files)
- All four HTML templates (index, upload, tax-report, recency_report)
- Branding, nc_tax_rates, tax_processor modules
- Scripts: generate_pdf_statement, import_sf_data
- Database schema (`001_initial_schema.sql`) — full schema including
  tax_transactions and customer_job_dates (committed March 2026)
- Docs: PROJECT-KNOWLEDGE folder

### ✅ Phase 1 — Committed April 21, 2026 (commit c054bbe)
- `phase1/fieldkit_backend/app.py` — Flask auth app, bcrypt, RBAC, company switching
- `phase1/fieldkit_backend/templates/` — login, dashboard, select_company, base
- `phase1/fieldkit_phase1/database/` — init SQL, schema files, seed data
- `phase1/fieldkit_phase1/import_sf_customers.py` — ServiceFusion import script
- `phase1/fieldkit_phase1/setup_databases.sh` — database setup script
- Previously lived only on ubuntu1 at `/home/chrisletize/fieldkit_backend/`
  and `/home/chrisletize/fieldkit_phase1/` — now safely in GitHub

### ✅ Phase 1 Database Dumps — Saved to NAS (April 21, 2026)
Database contents are NOT in git (by design). Dumps saved to:
`/nas/nvme/db/fieldkit-backups/` on LetizeNAS

| File | Size | Contents |
|------|------|----------|
| `fieldkit_getagrip_backup.sql` | 771K | 2,476 Get a Grip customers + schema |
| `fieldkit_kleanit_charlotte_backup.sql` | 28K | Schema + seed users only |
| `fieldkit_cts_backup.sql` | 28K | Schema + seed users only |
| `fieldkit_kleanit_sf_backup.sql` | 28K | Schema + seed users only |

To restore Get a Grip customer data to a new database:
```bash
psql -U postgres -d fieldkit_getagrip < fieldkit_getagrip_backup.sql
```

Note: ubuntu1 (flat LAN) can reach the NAS directly — no need to route via ubuntu-services.
ubuntu-business (VLAN70) cannot reach NAS — restore ops must be orchestrated from ubuntu-services.

---

## Infrastructure Quick Reference

| What | Where | How to reach |
|------|-------|-------------|
| Phase 0 prod | ubuntu-business:3000 | fieldkit.cletize.com |
| Phase 0 staging | ubuntu-business:3001 | staging.fieldkit.cletize.com |
| SSH to ubuntu-business | 10.83.70.10 | `ssh letize@10.83.70.10` (from VLAN20) |
| SSH to ubuntu-services | 10.83.30.10 | `ssh letize@10.83.30.10` |
| ubuntu1 (legacy) | 10.83.184.50 | `ssh chrisletize@10.83.184.50` — pending decommission |
| NPM admin | 10.83.30.10:81 | nginx.cletize.com:81 |
| Phase 0 DB backups | NAS | `/nas/nvme/db/fieldkit-backups/fsm_prod_*.sql.gz` |
| Phase 1 DB dumps | NAS | `/nas/nvme/db/fieldkit-backups/fieldkit_*_backup.sql` |
| GitHub | chrisletize/fsm-system | https://github.com/chrisletize/fsm-system |

---

## Next Steps — Phase 1 Migration to ubuntu-business

With code in GitHub and data on NAS, the migration path is:

1. Stand up Phase 1 as a new Docker Compose stack on ubuntu-business
   - Separate from Phase 0 (different port, different databases)
   - Four PostgreSQL databases: fieldkit_getagrip, fieldkit_kleanit_charlotte, fieldkit_cts, fieldkit_kleanit_sf
2. Copy the NAS dump to ubuntu-services, then restore into the new container
3. Build out the customer management interface
4. Continue Phase 1 feature development

Phase 1 state when work paused (Feb 10, 2026):
- ✅ Auth system with bcrypt, sessions, RBAC
- ✅ Company switcher (multi-tab support for Michele)
- ✅ Dashboard with live customer counts
- ✅ 2,476 Get a Grip customers imported
- 🔄 Customer list / search / CRUD — NOT YET BUILT
- 🔄 Contact management — NOT YET BUILT
- 📋 Other 3 company customer imports — NOT YET DONE

---

*Last updated: April 21, 2026 — Phase 1 code rescued from ubuntu1 and committed to GitHub*
