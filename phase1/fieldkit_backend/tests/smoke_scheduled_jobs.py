"""
Smoke test: Increment 2.5 — scheduled jobs (nightly + periodic) and the
customer_flags-derived delinquent badge.

*** SAFETY ***
Same discipline as smoke_email_delivery.py (Increment 1.7): `_resend.Emails.send`
is monkey-patched for the entire run so no real network call can ever happen,
restored in `finally` even on failure. This test also flips
company_settings.scheduled_alerts_enabled to TRUE temporarily to prove the
email path actually fires when told to — the ORIGINAL value (production
default: FALSE) is captured first and restored in `finally` no matter what,
so the real switch is never left on by this test.

Run inside the app container:

    docker compose exec -T app python tests/smoke_scheduled_jobs.py
"""
import sys
import os
import json
from datetime import datetime, timedelta, date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app as app_module  # noqa: E402
from app import (  # noqa: E402
    get_db_connection, app,
    _job_recompute_customer_flags, _job_extraction_upkeep, _job_escalation_check,
    _job_uninvoiced_check, _job_eod_escalation,
    job_nightly, job_uninvoiced, job_eod_escalation, job_weekly_sales_report,
)


def check(label, condition, extra=""):
    status = "OK" if condition else "FAIL"
    print(f"  [{status}] {label} {extra}")
    if not condition:
        raise AssertionError(f"{label} {extra}")


def close(a, b, tol=0.02):
    return abs(a - b) < tol


def main():
    conn = get_db_connection('getagrip')
    cur = conn.cursor()
    wo_ids, invoice_ids, customer_ids = [], [], []

    client = app.test_client()
    with client.session_transaction() as sess:
        sess['user_id'] = 1
        sess['username'] = 'smoketest'
        sess['user_role'] = 'admin'
        sess['company_access'] = ['getagrip']

    sent_calls = []
    def fake_resend_send(payload):
        sent_calls.append(payload)
        return {'id': f'fake-msg-{len(sent_calls)}'}
    original_send = app_module._resend.Emails.send
    app_module._resend.Emails.send = fake_resend_send

    cur.execute("SELECT scheduled_alerts_enabled, alert_email FROM company_settings WHERE deleted_at IS NULL")
    original_settings = cur.fetchone()

    try:
        check("production default: scheduled_alerts_enabled is FALSE before this test touches anything",
              original_settings['scheduled_alerts_enabled'] is False)

        cur.execute("SELECT id FROM catalog_items WHERE billing_behavior='standard' AND deleted_at IS NULL LIMIT 1")
        catalog_id = cur.fetchone()['id']

        cur.execute("""
            INSERT INTO customers (property_name, customer_type, status, payment_terms, created_by, updated_by)
            VALUES ('SMOKE Scheduled Jobs Co', 'Commercial', 'Active', 'Net 30', 'smoketest', 'smoketest')
            RETURNING id
        """)
        customer_id = cur.fetchone()['id']
        customer_ids.append(customer_id)
        conn.commit()

        print("smoke_scheduled_jobs: customer_flags — delinquent detection")
        cur.execute("""
            INSERT INTO work_orders (work_order_number, customer_id, status, created_by, updated_by)
            VALUES ('ZZZ-JOBS-0001', %s, 'Completed', 'smoketest', 'smoketest') RETURNING id
        """, (customer_id,))
        wo_old = cur.fetchone()['id']
        wo_ids.append(wo_old)
        cur.execute("""
            INSERT INTO work_order_line_items (work_order_id, catalog_item_id, description, quantity, unit_price, total, is_taxable, sort_order, created_by, updated_by)
            VALUES (%s, %s, 'Smoke line', 1, 500.00, 500.00, FALSE, 0, 'smoketest', 'smoketest')
        """, (wo_old, catalog_id))
        conn.commit()
        r = client.post(f'/getagrip/workorders/{wo_old}/invoice/new', follow_redirects=False)
        check(f"invoice created ({r.status_code})", r.status_code == 302)
        cur.execute("SELECT id FROM invoices WHERE work_order_id = %s", (wo_old,))
        inv_old = cur.fetchone()['id']
        invoice_ids.append(inv_old)
        old_date = (date.today() - timedelta(days=120)).isoformat()
        cur.execute("UPDATE invoices SET invoice_date = %s WHERE id = %s", (old_date, inv_old))
        conn.commit()
        client.post(f'/getagrip/invoices/{inv_old}/harden')
        client.post(f'/getagrip/invoices/{inv_old}/send')

        n = _job_recompute_customer_flags('getagrip')
        check(f"customer_flags recomputed for all customers ({n})", n > 0)
        cur.execute("SELECT * FROM customer_flags WHERE customer_id = %s", (customer_id,))
        flags = cur.fetchone()
        check(f"is_delinquent = true (invoice 120 days old > 90-day threshold) ({flags['is_delinquent']})",
              flags['is_delinquent'] is True)
        check(f"open_balance = 500.00 ({flags['open_balance']})", close(float(flags['open_balance']), 500.00))
        check(f"oldest_open_invoice_date matches ({flags['oldest_open_invoice_date']})",
              flags['oldest_open_invoice_date'].isoformat() == old_date)

        print("smoke_scheduled_jobs: delinquent badge shows on customer detail, WO form, dispatch board")
        r = client.get(f'/getagrip/customers/{customer_id}')
        check(f"customer detail renders ({r.status_code})", r.status_code == 200)
        check("customer detail shows Delinquent badge", b'Delinquent' in r.data)

        r = client.get('/getagrip/workorders/new')
        check(f"new WO form renders ({r.status_code})", r.status_code == 200)
        check("delinquent customer flagged in the embedded customer options JSON",
              b'"is_delinquent": true' in r.data or b'"is_delinquent":true' in r.data)

        print("smoke_scheduled_jobs: extraction upkeep — day count + Missed Today logging")
        started = date.today() - timedelta(days=3)
        cur.execute("""
            INSERT INTO work_orders (work_order_number, customer_id, status, is_extraction,
                extraction_status, extraction_started_at, start_date, created_by, updated_by)
            VALUES ('ZZZ-JOBS-EXTRACT', %s, 'Extraction Active', TRUE, 'Drying', %s, %s, 'smoketest', 'smoketest')
            RETURNING id
        """, (customer_id, started, started))
        wo_extract = cur.fetchone()['id']
        wo_ids.append(wo_extract)
        conn.commit()

        n_active, n_missed = _job_extraction_upkeep('getagrip')
        check(f"at least one active extraction upkept ({n_active})", n_active >= 1)
        cur.execute("SELECT extraction_day_count FROM work_orders WHERE id = %s", (wo_extract,))
        check("extraction_day_count = 4 (3 days ago -> day 4)", cur.fetchone()['extraction_day_count'] == 4)
        yesterday = date.today() - timedelta(days=1)
        cur.execute("SELECT extraction_status FROM extraction_daily_log WHERE work_order_id = %s AND log_date = %s",
                    (wo_extract, yesterday))
        missed_row = cur.fetchone()
        check("Missed Today auto-logged for yesterday (no check recorded)",
              missed_row is not None and missed_row['extraction_status'] == 'Missed Today')

        print("smoke_scheduled_jobs: escalation check with alerts OFF — no email sent")
        calls_before = len(sent_calls)
        n_escalated = _job_escalation_check('getagrip')
        check(f"day 5+ escalation count is 0 (job started 3 days ago, escalation is day 5) ({n_escalated})",
              n_escalated == 0)
        check("no Resend call while switch is off", len(sent_calls) == calls_before)

        print("smoke_scheduled_jobs: flip the master switch ON (temporarily) — verify the email path actually fires")
        cur.execute("""
            UPDATE company_settings SET scheduled_alerts_enabled = TRUE, alert_email = %s WHERE deleted_at IS NULL
        """, ('smoketest-alerts@smoketest.invalid',))
        conn.commit()

        # Push the extraction job to day 5+ for the escalation test.
        cur.execute("UPDATE work_orders SET extraction_started_at = %s WHERE id = %s",
                    (date.today() - timedelta(days=5), wo_extract))
        conn.commit()
        calls_before = len(sent_calls)
        n_escalated_on = _job_escalation_check('getagrip')
        check(f"escalation count is 1 now ({n_escalated_on})", n_escalated_on == 1)
        check("Resend WAS called with alerts on", len(sent_calls) == calls_before + 1)
        check("escalation email went to the configured alert_email",
              sent_calls[-1]['to'] == ['smoketest-alerts@smoketest.invalid'])

        # Uninvoiced check: back-date the Completed WO's status history so it
        # qualifies (>1h old), no invoice on it.
        cur.execute("""
            INSERT INTO work_orders (work_order_number, customer_id, status, created_by, updated_by)
            VALUES ('ZZZ-JOBS-UNINV', %s, 'Completed', 'smoketest', 'smoketest') RETURNING id
        """, (customer_id,))
        wo_uninv = cur.fetchone()['id']
        wo_ids.append(wo_uninv)
        cur.execute("""
            INSERT INTO work_order_status_history (work_order_id, status, changed_by, changed_at)
            VALUES (%s, 'Completed', 'smoketest', %s)
        """, (wo_uninv, datetime.now() - timedelta(hours=3)))
        conn.commit()

        calls_before = len(sent_calls)
        n_uninv = _job_uninvoiced_check('getagrip')
        check(f"uninvoiced check finds the fixture ({n_uninv})", n_uninv >= 1)
        check("Resend called for the uninvoiced alert", len(sent_calls) > calls_before)
        cur.execute("SELECT alert_sent_at FROM work_orders WHERE id = %s", (wo_uninv,))
        check("alert_sent_at dedupe column set", cur.fetchone()['alert_sent_at'] is not None)

        calls_before = len(sent_calls)
        n_uninv_again = _job_uninvoiced_check('getagrip')
        check(f"second run finds nothing new (deduped by alert_sent_at) ({n_uninv_again})", n_uninv_again == 0)
        check("no additional Resend call on the deduped re-run", len(sent_calls) == calls_before)

        calls_before = len(sent_calls)
        n_eod = _job_eod_escalation('getagrip')
        check(f"eod digest still lists it (not deduped — a digest, not a per-WO alert) ({n_eod})", n_eod >= 1)
        check("Resend called for the eod digest", len(sent_calls) > calls_before)

        print("smoke_scheduled_jobs: switch back OFF — verify nothing sends even with fresh qualifying data")
        cur.execute("""
            UPDATE company_settings SET scheduled_alerts_enabled = FALSE WHERE deleted_at IS NULL
        """)
        conn.commit()
        cur.execute("""
            INSERT INTO work_orders (work_order_number, customer_id, status, created_by, updated_by)
            VALUES ('ZZZ-JOBS-UNINV2', %s, 'Completed', 'smoketest', 'smoketest') RETURNING id
        """, (customer_id,))
        wo_uninv2 = cur.fetchone()['id']
        wo_ids.append(wo_uninv2)
        cur.execute("""
            INSERT INTO work_order_status_history (work_order_id, status, changed_by, changed_at)
            VALUES (%s, 'Completed', 'smoketest', %s)
        """, (wo_uninv2, datetime.now() - timedelta(hours=3)))
        conn.commit()
        calls_before = len(sent_calls)
        n_off = _job_uninvoiced_check('getagrip')
        check(f"uninvoiced check still COMPUTES the count even while off ({n_off})", n_off >= 1)
        check("but sends NOTHING while the switch is off", len(sent_calls) == calls_before)
        cur.execute("SELECT alert_sent_at FROM work_orders WHERE id = %s", (wo_uninv2,))
        check("alert_sent_at stays NULL when nothing was actually sent", cur.fetchone()['alert_sent_at'] is None)

        print("smoke_scheduled_jobs: job_runs bookkeeping via the job_* wrappers")
        summary = job_nightly('getagrip')
        check("job_nightly returns a summary string", isinstance(summary, str) and len(summary) > 0)
        cur.execute("SELECT status FROM job_runs WHERE job_name = 'nightly' AND company_key = 'getagrip' ORDER BY id DESC LIMIT 1")
        check("nightly job_runs row is success", cur.fetchone()['status'] == 'success')

        job_uninvoiced('getagrip')
        job_eod_escalation('getagrip')
        # Increment 3.5 built the Sales CRM for real -- this subcommand now
        # always computes real data (visit/prospect counts) and only skips
        # the email itself while scheduled_alerts_enabled is off (which it is
        # here, restored at line ~205 above). See tests/smoke_sales_crm.py
        # for the full weekly-report/email-path coverage.
        report_summary = job_weekly_sales_report('getagrip')
        check(f"weekly_sales_report computes real data, no email while alerts are off ({report_summary})",
              'no email sent' in report_summary)
        cur.execute("SELECT status, summary FROM job_runs WHERE job_name = 'weekly_sales_report' AND company_key = 'getagrip' ORDER BY id DESC LIMIT 1")
        row = cur.fetchone()
        check("weekly_sales_report job_runs row is success with a real summary",
              row['status'] == 'success' and 'visit(s)' in row['summary'])

        print("smoke_scheduled_jobs: /settings/company shows the panel + toggle route works")
        r = client.get('/getagrip/settings/company')
        check(f"settings page renders ({r.status_code})", r.status_code == 200)
        check("Scheduled Jobs panel present", b'Scheduled Jobs' in r.data)
        check("nightly job appears in the panel", b'nightly' in r.data)

        r = client.post('/getagrip/settings/company/scheduled-alerts', data={'scheduled_alerts_enabled': 'on'}, follow_redirects=False)
        check(f"toggle route responds 302 ({r.status_code})", r.status_code == 302)
        cur.execute("SELECT scheduled_alerts_enabled FROM company_settings WHERE deleted_at IS NULL")
        check("toggle route actually flipped it on", cur.fetchone()['scheduled_alerts_enabled'] is True)
        r = client.post('/getagrip/settings/company/scheduled-alerts', data={}, follow_redirects=False)
        cur.execute("SELECT scheduled_alerts_enabled FROM company_settings WHERE deleted_at IS NULL")
        check("posting without the checkbox flips it back off", cur.fetchone()['scheduled_alerts_enabled'] is False)

        print("ALL CHECKS PASSED")

    finally:
        app_module._resend.Emails.send = original_send
        # Restore company_settings to exactly what it was before this test
        # touched it — the real production switch must never be left on.
        cur.execute("""
            UPDATE company_settings SET scheduled_alerts_enabled = %s, alert_email = %s WHERE deleted_at IS NULL
        """, (original_settings['scheduled_alerts_enabled'], original_settings['alert_email']))

        for iid in invoice_ids:
            cur.execute("DELETE FROM invoice_status_history WHERE invoice_id = %s", (iid,))
            cur.execute("DELETE FROM invoice_version_line_items WHERE version_id IN (SELECT id FROM invoice_versions WHERE invoice_id = %s)", (iid,))
            cur.execute("UPDATE invoices SET current_version_id = NULL WHERE id = %s", (iid,))
            cur.execute("DELETE FROM invoice_versions WHERE invoice_id = %s", (iid,))
        if invoice_ids:
            cur.execute("DELETE FROM invoices WHERE id = ANY(%s)", (invoice_ids,))
        for wid in wo_ids:
            cur.execute("DELETE FROM work_order_status_history WHERE work_order_id = %s", (wid,))
            cur.execute("DELETE FROM extraction_daily_log WHERE work_order_id = %s", (wid,))
            cur.execute("DELETE FROM work_order_line_items WHERE work_order_id = %s", (wid,))
        if wo_ids:
            cur.execute("DELETE FROM work_orders WHERE id = ANY(%s)", (wo_ids,))
        if customer_ids:
            cur.execute("DELETE FROM customer_flags WHERE customer_id = ANY(%s)", (customer_ids,))
            # job_nightly (Increment 3.2) also recomputes customer_ratings for
            # every customer it touches -- clean that up too, or the FK blocks
            # the customer delete below.
            cur.execute("DELETE FROM customer_ratings WHERE customer_id = ANY(%s)", (customer_ids,))
            cur.execute("DELETE FROM customers WHERE id = ANY(%s)", (customer_ids,))
        cur.execute("DELETE FROM job_runs WHERE company_key = 'getagrip' AND started_at > NOW() - INTERVAL '5 minutes'")
        conn.commit()
        cur.close()
        conn.close()
        print(f"cleanup done: {len(invoice_ids)} invoice(s), {len(wo_ids)} WO(s), "
              f"{len(customer_ids)} customer(s) removed, company_settings restored, "
              f"{len(sent_calls)} fake Resend call(s) made this run (0 real).")


if __name__ == '__main__':
    main()
