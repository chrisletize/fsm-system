#!/usr/bin/env python3
"""
FieldKit scheduled jobs (directive §3.5, Increment 2.5).

A thin CLI wrapper: the actual work lives in app.py (job_nightly,
job_uninvoiced, job_eod_escalation, job_weekly_sales_report) so the same
functions are importable and testable from the smoke suite without shelling
out to this file. This file just loops over all four companies and dispatches
by subcommand, matching how host cron invokes it:

    docker compose exec -T app python jobs.py nightly
    docker compose exec -T app python jobs.py uninvoiced
    docker compose exec -T app python jobs.py eod_escalation
    docker compose exec -T app python jobs.py weekly_sales_report

Each company's failure is isolated -- one company erroring doesn't stop the
others (job_runs records the failure for whichever company hit it; see
app.py's job_* wrappers).
"""
import sys

from app import (
    ALL_COMPANY_KEYS,
    job_nightly,
    job_uninvoiced,
    job_eod_escalation,
    job_weekly_sales_report,
)

JOBS = {
    'nightly': job_nightly,
    'uninvoiced': job_uninvoiced,
    'eod_escalation': job_eod_escalation,
    'weekly_sales_report': job_weekly_sales_report,
}


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in JOBS:
        print(f"Usage: python jobs.py <{'|'.join(JOBS)}>")
        sys.exit(1)

    job_name = sys.argv[1]
    job_fn = JOBS[job_name]
    exit_code = 0
    for company_key in ALL_COMPANY_KEYS:
        try:
            summary = job_fn(company_key)
            print(f"[{company_key}] {job_name}: {summary}")
        except Exception as e:
            print(f"[{company_key}] {job_name} FAILED: {type(e).__name__}: {e}")
            exit_code = 1
    sys.exit(exit_code)


if __name__ == '__main__':
    main()
