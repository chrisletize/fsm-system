"""
Smoke test: the salesman's map (migration 042, D-118, Chris 2026-10-27).

Covers geocoding (Census result stored with its source, edited address
re-geocoded, incomplete addresses marked not sent, a failed batch left for
tomorrow, the strict OpenStreetMap fallback), the map data (statuses, dormant,
rehab, tips, sales hold, last visit present/missing, residential left off, one
pin per property across companies), the page, the tile/asset routes (HTTP Range
works, unknown names 404) and role access.

The geocoders are monkey-patched -- nothing is sent to Census or OSM -- and
geocode_company is restricted to the fixture rows (only_ids) so no real
customer is touched. Drives the real routes against live getagrip and
kleanit_charlotte; everything created is hard-deleted in `finally`. Run inside
the app container:

    docker compose exec -T app python tests/smoke_sales_map.py
"""
import sys
import os
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app as appmod  # noqa: E402
from app import get_db_connection, app, geocode_company, _sales_map_property_key  # noqa: E402


def check(label, condition, extra=""):
    status = "OK" if condition else "FAIL"
    print(f"  [{status}] {label} {extra}")
    if not condition:
        raise AssertionError(f"{label} {extra}")


def client_as(role, username, companies=('getagrip', 'kleanit_charlotte')):
    c = app.test_client()
    with c.session_transaction() as sess:
        sess['user_id'] = 1
        sess['username'] = username
        sess['full_name'] = f'Smoke {role}'
        sess['user_role'] = role
        sess['company_access'] = list(companies)
    return c


def main():
    gag = get_db_connection('getagrip')
    gc = gag.cursor()
    kc = get_db_connection('kleanit_charlotte')
    kcur = kc.cursor()
    real_batch, real_fallback, real_http = (appmod._census_batch_geocode, appmod._fallback_geocode,
                                            appmod._http_json)
    batch_calls = []
    batch_mode = {'fail': False}

    def fake_batch(rows):
        batch_calls.append([r[0] for r in rows])
        if batch_mode['fail']:
            raise TimeoutError('smoke: census timed out')
        out = {}
        for rid, street, city, state, zip_ in rows:
            if street.startswith('999 '):
                out[rid] = ('no_match', None, None)
            else:
                out[rid] = ('matched', 35.2 + int(rid) % 100 / 10000, -80.8)
        return out
    appmod._census_batch_geocode = fake_batch
    appmod._fallback_geocode = lambda r: (35.31, -80.71, 'osm') if r['address'].startswith('999 New') else None

    g_ids, k_ids, p_ids, wo_ids, v_ids, tip_ids = [], [], [], [], [], []
    sales = client_as('salesperson', 'smokemapsales')
    tech = client_as('technician', 'smokemaptech')

    def gq(sql, args=()):
        gc.execute(sql, args)
        return gc.fetchone()

    try:
        def add_customer(cur, conn, name, addr, ctype='Multi Family', city='Charlotte', zip_='28202', ids=g_ids):
            cur.execute("""INSERT INTO customers (property_name, customer_type, status, address, city, state, zip,
                               created_by, updated_by)
                           VALUES (%s, %s, 'Active', %s, %s, 'NC', %s, 'smokemap', 'smokemap') RETURNING id""",
                        (name, ctype, addr, city, zip_))
            i = cur.fetchone()['id']; ids.append(i); conn.commit(); return i

        active = add_customer(gc, gag, 'ZZZ Map Active', '101 Smoke St')
        dormant = add_customer(gc, gag, 'ZZZ Map Dormant', '102 Smoke St')
        held = add_customer(gc, gag, 'ZZZ Map Held', '103 Smoke St')
        resi = add_customer(gc, gag, 'ZZZ Map Home', '104 Smoke St', ctype='Residential')
        newbuild = add_customer(gc, gag, 'ZZZ Map New Build', '999 New Rd')
        nomatch = add_customer(gc, gag, 'ZZZ Map Nowhere', '999 Old Rd')
        incomplete = add_customer(gc, gag, 'ZZZ Map No Street', '', zip_='')
        shared_g = add_customer(gc, gag, 'ZZZ Map Shared', '200 Shared Way', zip_='28203')
        shared_k = add_customer(kcur, kc, 'ZZZ Map Shared Apts', '200  Shared  Way', zip_='28203-1111', ids=k_ids)
        gc.execute("""INSERT INTO work_orders (work_order_number, customer_id, status, start_date, created_by, updated_by)
                      VALUES ('ZZZ-SMOKE-MAP1', %s, 'Completed', CURRENT_DATE - 10, 'smokemap', 'smokemap'),
                             ('ZZZ-SMOKE-MAP2', %s, 'Completed', CURRENT_DATE - 900, 'smokemap', 'smokemap')
                      RETURNING id""", (active, dormant))
        wo_ids += [r['id'] for r in gc.fetchall()]
        gc.execute("UPDATE customers SET sales_delayed_until = CURRENT_DATE + 60 WHERE id = %s", (held,))
        gc.execute("""INSERT INTO sales_prospects (property_name, address, city, state, zip, rehab_planned,
                          created_by, updated_by)
                      VALUES ('ZZZ Map Rehab Prospect', '105 Smoke St', 'Charlotte', 'NC', '28202', TRUE,
                              'smokemap', 'smokemap') RETURNING id""")
        prospect = gc.fetchone()['id']; p_ids.append(prospect)
        gc.execute("""INSERT INTO sales_visits (property_id, property_type, visit_date, visit_tag, notes, created_by, updated_by)
                      VALUES (%s, 'customer', CURRENT_DATE - 3, 'Hot lead', 'Met the new <PM>', 'smokemapsales', 'smokemapsales')
                      RETURNING id""", (active,))
        v_ids.append(gc.fetchone()['id'])
        gc.execute("""INSERT INTO sales_tips (property_type, property_id, notes, due_date, created_by, updated_by)
                      VALUES ('prospect', %s, 'smoke tip', CURRENT_DATE, 'smokemap', 'smokemap') RETURNING id""", (prospect,))
        tip_ids.append(gc.fetchone()['id'])
        gag.commit()

        print("smoke_sales_map: geocoding")
        only = {'customers': g_ids, 'sales_prospects': p_ids}
        c = geocode_company('getagrip', only_ids=only)
        check(f"fixtures geocoded ({c})", c['matched'] >= 7 and c['incomplete'] == 1)
        row = gq("SELECT latitude, geocode_status, geocode_source, geocoded_address FROM customers WHERE id = %s", (active,))
        check("Census match stored with its source", row['geocode_status'] == 'matched'
              and row['geocode_source'] == 'census' and row['latitude'] is not None)
        row = gq("SELECT geocode_status, geocode_source, latitude FROM customers WHERE id = %s", (newbuild,))
        check("Census miss placed by the OSM fallback", row['geocode_status'] == 'matched' and row['geocode_source'] == 'osm')
        row = gq("SELECT geocode_status, latitude FROM customers WHERE id = %s", (nomatch,))
        check("a miss neither geocoder can place stays no_match, unpinned",
              row['geocode_status'] == 'no_match' and row['latitude'] is None)
        row = gq("SELECT geocode_status FROM customers WHERE id = %s", (incomplete,))
        check("an incomplete address is marked, not sent", row['geocode_status'] == 'incomplete'
              and str(incomplete) not in sum(batch_calls, []))
        n_calls = len(batch_calls)
        c = geocode_company('getagrip', only_ids=only)
        check("unchanged addresses aren't re-sent", len(batch_calls) == n_calls and c['matched'] == 0)
        gc.execute("UPDATE customers SET address = '101 Smoke Street' WHERE id = %s", (active,)); gag.commit()
        geocode_company('getagrip', only_ids=only)
        check("an edited address is re-geocoded", batch_calls[-1] == [str(active)])
        gc.execute("UPDATE customers SET address = '101 Smoke St' WHERE id = %s", (active,)); gag.commit()
        batch_mode['fail'] = True
        before = gq("SELECT geocoded_address FROM customers WHERE id = %s", (active,))['geocoded_address']
        c = geocode_company('getagrip', only_ids=only)
        batch_mode['fail'] = False
        after = gq("SELECT geocoded_address FROM customers WHERE id = %s", (active,))['geocoded_address']
        check("a failed Census batch counts as error and is left for the next run",
              c['error'] == 1 and before == after)
        geocode_company('getagrip', only_ids=only)
        geocode_company('kleanit_charlotte', only_ids={'customers': k_ids})

        print("smoke_sales_map: the fallback is strict")
        appmod._fallback_geocode = real_fallback
        responses = {}

        def fake_http(url, timeout=30):
            if 'onelineaddress' in url:
                return {'result': {'addressMatches': []}}
            return {'features': responses['photon']}
        appmod._http_json = fake_http
        feat = lambda hn, pc, city='Charlotte': {'properties': {'housenumber': hn, 'postcode': pc, 'city': city},
                                                 'geometry': {'coordinates': [-80.7, 35.3]}}
        base = dict(address='5100 Little Greenleaf Way', city='Charlotte', state='NC', zip='28215-4670')
        responses['photon'] = [feat('5100', '28215')]
        check("exact house number + ZIP accepted", real_fallback(base) == (35.3, -80.7, 'osm'))
        responses['photon'] = [feat('5102', '28215')]
        check("a different house number is rejected", real_fallback(base) is None)
        responses['photon'] = [feat('5100', '28269')]
        check("a different ZIP is rejected", real_fallback(base) is None)
        check("no house number (PO box / name only) isn't tried",
              real_fallback(dict(base, address='P O Box 620337')) is None)
        appmod._http_json = real_http

        print("smoke_sales_map: map data")
        r = sales.get('/sales-map/data')
        check(f"salesperson gets the data ({r.status_code})", r.status_code == 200)
        data = r.get_json()
        props = {p['name']: p for p in data['properties'] if p['name'].startswith('ZZZ Map')}
        ent = lambda name: props[name]['entries'][0]
        check("active customer is 'customer' with its last visit",
              ent('ZZZ Map Active')['status'] == 'customer'
              and ent('ZZZ Map Active')['last_visit']['tag'] == 'Hot lead'
              and ent('ZZZ Map Active')['url'] == f'/getagrip/sales/customers/{active}')
        check("900 days since service is 'dormant'", ent('ZZZ Map Dormant')['status'] == 'dormant')
        check("no visit logged is reported as missing", ent('ZZZ Map Dormant')['last_visit'] is None)
        check("sales hold carries its date", ent('ZZZ Map Held')['paused_until'] is not None)
        check("rehab prospect with its tip", ent('ZZZ Map Rehab Prospect')['rehab'] is True
              and ent('ZZZ Map Rehab Prospect')['tips'] == 1 and ent('ZZZ Map Rehab Prospect')['status'] == 'prospect')
        check("residential customers are left off", 'ZZZ Map Home' not in props)
        check("OSM-placed customer is on the map", 'ZZZ Map New Build' in props)
        check("unplaced properties aren't, and are counted",
              'ZZZ Map Nowhere' not in props and 'ZZZ Map No Street' not in props and data['unplaced']['getagrip'] >= 2)
        shared = [p for p in data['properties'] if p['name'].startswith('ZZZ Map Shared')]
        check("same building in two companies is ONE pin with two entries",
              len(shared) == 1 and sorted(e['company'] for e in shared[0]['entries']) == ['getagrip', 'kleanit_charlotte'])
        check("address keys ignore spacing and ZIP+4",
              _sales_map_property_key({'address': '200 Shared Way, Charlotte', 'zip': '28203', 'lat': 0, 'lng': 0})
              == _sales_map_property_key({'address': '200  Shared  Way, Charlotte', 'zip': '28203', 'lat': 1, 'lng': 1}))
        only_gag = client_as('salesperson', 'smokemapsales', companies=('getagrip',)).get('/sales-map/data').get_json()
        check("only companies the user can access",
              all(e['company'] == 'getagrip' for p in only_gag['properties'] for e in p['entries']))

        print("smoke_sales_map: page, tiles and access")
        r = sales.get('/sales-map')
        html = r.get_data(as_text=True)
        check(f"page renders ({r.status_code})", r.status_code == 200 and 'id="map"' in html)
        check("vendored libraries, no CDN", '/static/vendor/maplibre-gl-6.12.0/maplibre-gl.mjs' in html
              and 'unpkg.com' not in html and 'cdn.' not in html)
        check("region buttons for all four areas",
              all(n in html for n in ('Charlotte', 'Triad', 'Raleigh', 'South Florida')))
        check("script is in the body", html.index('</title>') < html.index("import * as maplibregl"))
        check("detail box closes on zoom, not on a stray tap",
              "map.on('zoomstart'" in html and 'closeOnClick: false' in html)
        check("search box, last-visit filter and full screen on the map",
              'id="mapSearch"' in html and 'id="visitFilter"' in html and 'value="never"' in html
              and 'FullscreenControl' in html and 'maplibregl-pseudo-fullscreen' in html)
        check("no clustering: every property is a dot that scales with zoom",
              'cluster: true' not in html and "'circle-sort-key'" in html and "queryRenderedFeatures([[pt.x - r" in html)
        check("search and filter panel sits inside the full-screen area",
              html.index('class="map-wrap"') < html.index('class="map-panel"') < html.index('class="legend"'))
        check("rotation and tilt are locked (no compass to undo them)",
              'touchZoomRotate.disableRotation()' in html and 'touchPitch.disable()' in html)
        for path in ('/static/vendor/maplibre-gl-6.12.0/maplibre-gl.mjs',
                     '/static/vendor/maplibre-gl-6.12.0/maplibre-gl-shared.mjs',
                     '/static/vendor/maplibre-gl-6.12.0/maplibre-gl-worker.mjs',
                     '/static/vendor/pmtiles-4.5.0/pmtiles.js', '/static/vendor/protomaps-basemaps-5.7.2/basemaps.js'):
            rr = sales.get(path)
            check(f"{path.rsplit('/', 1)[1]} served as JS ({rr.status_code} {rr.mimetype})",
                  rr.status_code == 200 and 'javascript' in rr.mimetype)
        r = sales.get('/sales-map/tiles/overview.pmtiles', headers={'Range': 'bytes=0-126'})
        check(f"tiles answer Range requests ({r.status_code}, {len(r.data)} bytes)",
              r.status_code == 206 and len(r.data) == 127 and r.data[:7] == b'PMTiles')
        r = sales.get('/sales-map/tiles/detail.pmtiles', headers={'Range': 'bytes=0-6'})
        check("detail tiles present", r.status_code == 206 and r.data == b'PMTiles')
        check("unknown tile archive 404s", sales.get('/sales-map/tiles/secrets.pmtiles').status_code == 404)
        r = sales.get('/sales-map/assets/fonts/Noto Sans Regular/0-255.pbf')
        check(f"fonts served ({r.status_code})", r.status_code == 200 and len(r.data) > 1000)
        check("asset paths can't escape the folder",
              sales.get('/sales-map/assets/../VERSION').status_code == 404)
        for path in ('/sales-map', '/sales-map/data', '/sales-map/tiles/overview.pmtiles'):
            check(f"technician blocked from {path}", tech.get(path).status_code == 403)
        r = app.test_client().get('/sales-map/data')
        check("signed-out request is sent to login", r.status_code == 302 and '/login' in r.headers.get('Location', ''))
        html = sales.get('/getagrip/sales').get_data(as_text=True)
        check("Sales dashboard links to the map", 'href="/sales-map"' in html)

        print("ALL CHECKS PASSED")

    finally:
        appmod._census_batch_geocode, appmod._fallback_geocode, appmod._http_json = real_batch, real_fallback, real_http
        gag.rollback(); kc.rollback()
        if tip_ids:
            gc.execute("DELETE FROM sales_tips WHERE id = ANY(%s)", (tip_ids,))
        if v_ids:
            gc.execute("DELETE FROM sales_visits WHERE id = ANY(%s)", (v_ids,))
        if p_ids:
            gc.execute("DELETE FROM sales_prospects WHERE id = ANY(%s)", (p_ids,))
        if wo_ids:
            gc.execute("DELETE FROM work_orders WHERE id = ANY(%s)", (wo_ids,))
        if g_ids:
            gc.execute("DELETE FROM customer_flags WHERE customer_id = ANY(%s)", (g_ids,))
            gc.execute("DELETE FROM customers WHERE id = ANY(%s)", (g_ids,))
        if k_ids:
            kcur.execute("DELETE FROM customer_flags WHERE customer_id = ANY(%s)", (k_ids,))
            kcur.execute("DELETE FROM customers WHERE id = ANY(%s)", (k_ids,))
        gag.commit(); kc.commit()
        gc.close(); gag.close(); kcur.close(); kc.close()
        print("cleanup done: map fixtures removed from getagrip and kleanit_charlotte.")


if __name__ == '__main__':
    main()
