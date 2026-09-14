"""
North Carolina Sales & Use Tax Rate Reference

Source of truth: NCDOR "Current Sales and Use Tax Rates"
https://www.ncdor.gov/taxes-forms/sales-and-use-tax/sales-and-use-tax-rates/current-sales-and-use-tax-rates
Verified against the NCDOR county list effective July 1, 2026.

-------------------------------------------------------------------------------
WHY THIS MODULE IS RATE-KEYED, NOT COUNTY-KEYED
-------------------------------------------------------------------------------
The tax report is CASH BASIS: rows are selected by payment date, but the rate on
each row was locked in when the invoice was billed. A single report can therefore
contain several rates for the same county.

Mecklenburg is the live example. It went from 7.25% to 8.25% on 07/01/2026, so any
report run since then legitimately contains both. Splitting a county's *pooled* tax
by a single county rate silently mis-states every component the moment two rates
coexist -- the total still ties, so nothing looks broken.

So: the rate actually billed (from the ServiceFusion Tax Report "Tax Rate" column)
selects the component structure. This table's job is to VALIDATE that rate, not to
supply it. A (county, rate) pair that is not listed here is returned as unmatched
and surfaced on the report rather than being quietly allocated.

-------------------------------------------------------------------------------
NC RATE COMPONENTS
-------------------------------------------------------------------------------
    State ............... 4.75%  (every county, always)
    County .............. 2.00% or 2.25%
    Transit ............. 0.50%  (Mecklenburg, Wake, Durham, Orange only)
    Additional county ... 1.00%  (Mecklenburg only, effective 07/01/2026)

Mecklenburg's additional 1% was approved by referendum 11/04/2025, levied by the
County Commission 12/02/2025, and took effect 07/01/2026. It is reported to NCDOR
SEPARATELY from the 2.00% county rate and the 0.50% transit rate.
"""

# Component composition of every rate NC currently levies.
# Keys are the combined rate as it appears on a ServiceFusion invoice.
RATE_STRUCTURES = {
    6.75: {'state': 4.75, 'county': 2.00, 'transit': 0.00, 'additional_county': 0.00},
    7.00: {'state': 4.75, 'county': 2.25, 'transit': 0.00, 'additional_county': 0.00},
    7.25: {'state': 4.75, 'county': 2.00, 'transit': 0.50, 'additional_county': 0.00},
    7.50: {'state': 4.75, 'county': 2.25, 'transit': 0.50, 'additional_county': 0.00},
    8.25: {'state': 4.75, 'county': 2.00, 'transit': 0.50, 'additional_county': 1.00},
}

# Rates each county is permitted to have billed.
# First entry is the CURRENT rate; any further entries are prior rates that may
# still legitimately appear on cash-basis reports for invoices billed earlier.
NC_COUNTY_RATES = {
    'Alamance':        [6.75],
    'Alexander':       [7.00],
    'Alleghany':       [7.00],
    'Anson':           [7.00],
    'Ashe':            [7.00],
    'Avery':           [6.75],
    'Beaufort':        [6.75],
    'Bertie':          [7.00],
    'Bladen':          [6.75],
    'Brunswick':       [6.75],
    'Buncombe':        [7.00],
    'Burke':           [6.75],
    'Cabarrus':        [7.00],
    'Caldwell':        [6.75],
    'Camden':          [6.75],
    'Carteret':        [6.75],
    'Caswell':         [6.75],
    'Catawba':         [7.00],
    'Chatham':         [7.00],
    'Cherokee':        [7.00],
    'Chowan':          [6.75],
    'Clay':            [7.00],
    'Cleveland':       [6.75],
    'Columbus':        [6.75],
    'Craven':          [6.75],
    'Cumberland':      [7.00],
    'Currituck':       [6.75],
    'Dare':            [6.75],
    'Davidson':        [7.00],
    'Davie':           [6.75],
    'Duplin':          [7.00],
    'Durham':          [7.50],
    'Edgecombe':       [7.00],
    'Forsyth':         [7.00],
    'Franklin':        [6.75],
    'Gaston':          [7.00],
    'Gates':           [6.75],
    'Graham':          [7.00],
    'Granville':       [6.75],
    'Greene':          [7.00],
    'Guilford':        [6.75],
    'Halifax':         [7.00],
    'Harnett':         [7.00],
    'Haywood':         [7.00],
    'Henderson':       [6.75],
    'Hertford':        [7.00],
    'Hoke':            [6.75],
    'Hyde':            [6.75],
    'Iredell':         [6.75],
    'Jackson':         [7.00],
    'Johnston':        [6.75],
    'Jones':           [7.00],
    'Lee':             [7.00],
    'Lenoir':          [6.75],
    'Lincoln':         [7.00],
    'Macon':           [6.75],
    'Madison':         [7.00],
    'Martin':          [7.00],
    'McDowell':        [6.75],
    'Mecklenburg':     [8.25, 7.25],  # 7.25 retained: pre-7/1/2026 invoices still appear on cash-basis reports
    'Mitchell':        [6.75],
    'Montgomery':      [7.00],
    'Moore':           [7.00],
    'Nash':            [6.75],
    'New Hanover':     [7.00],
    'Northampton':     [6.75],
    'Onslow':          [7.00],
    'Orange':          [7.50],
    'Pamlico':         [6.75],
    'Pasquotank':      [7.00],
    'Pender':          [6.75],
    'Perquimans':      [6.75],
    'Person':          [6.75],
    'Pitt':            [7.00],
    'Polk':            [6.75],
    'Randolph':        [7.00],
    'Richmond':        [6.75],
    'Robeson':         [7.00],
    'Rockingham':      [7.00],
    'Rowan':           [7.00],
    'Rutherford':      [7.00],
    'Sampson':         [7.00],
    'Scotland':        [6.75],
    'Stanly':          [7.00],
    'Stokes':          [6.75],
    'Surry':           [7.00],
    'Swain':           [7.00],
    'Transylvania':    [6.75],
    'Tyrrell':         [6.75],
    'Union':           [6.75],
    'Vance':           [6.75],
    'Wake':            [7.25],
    'Warren':          [6.75],
    'Washington':      [7.00],
    'Watauga':         [6.75],
    'Wayne':           [6.75],
    'Wilkes':          [7.00],
    'Wilson':          [6.75],
    'Yadkin':          [6.75],
    'Yancey':          [6.75],
}

# Component labels in canonical reporting order.
COMPONENTS = ('state', 'county', 'transit', 'additional_county')

# Human-readable labels, for report headers and PDF tables.
COMPONENT_LABELS = {
    'state': 'State',
    'county': 'County',
    'transit': 'Transit',
    'additional_county': 'Additional County',
}


def _normalize_rate(rate):
    """Coerce a rate to the canonical float used as a dict key.

    Accepts 7.25, '7.25', '7.2500%' -- ServiceFusion emits the last form.
    Returns None if the value cannot be read as a number.
    """
    if rate is None:
        return None
    if isinstance(rate, str):
        rate = rate.replace('%', '').strip()
        if not rate:
            return None
    try:
        return round(float(rate), 4)
    except (TypeError, ValueError):
        return None


def _normalize_county(county_name):
    """Trim and title-case a county name for lookup. 'MECKLENBURG ' -> 'Mecklenburg'."""
    if not county_name:
        return ''
    name = str(county_name).strip()
    if name in NC_COUNTY_RATES:
        return name
    for known in NC_COUNTY_RATES:
        if known.lower() == name.lower():
            return known
    return name


def get_tax_breakdown(county_name, tax_collected, rate_charged):
    """Split one invoice's collected tax into its NC reporting components.

    This operates on a SINGLE invoice, never on a county's pooled tax. Pooling
    first and splitting after is only valid when every row shares one rate, which
    stopped being true for Mecklenburg on 07/01/2026.

    Args:
        county_name:   County as it appears on the SF Tax Report.
        tax_collected: Tax dollars on this invoice.
        rate_charged:  Combined rate actually billed, from the SF "Tax Rate"
                       column. Accepts 7.25, '7.25', or '7.2500%'.

    Returns dict:
        state, county, transit, additional_county
                       -- FULL PRECISION, deliberately unrounded. Callers must
                          accumulate first and round once at the end; rounding
                          per-invoice and then summing accumulates visible drift.
        total          -- tax_collected as passed in.
        unallocated    -- tax_collected when unmatched, else 0.0. Keeps the report
                          tying to the source even when a rate is unrecognized.
        matched        -- True when (county, rate) is a known pair.
        rate           -- normalized rate, or None if unreadable.
        county_name    -- normalized county name.
        reason         -- None when matched; otherwise why it failed.
        expected_rates -- rates this county is allowed to have billed.

    An unmatched result allocates NOTHING to components. That is intentional: a
    hole in the breakdown is loud, and a rate we do not recognize means either a
    mis-billed invoice or a rate change this table has not caught up to. Both
    need a human, not a silent guess.
    """
    county = _normalize_county(county_name)
    rate = _normalize_rate(rate_charged)

    try:
        tax_collected = float(tax_collected)
    except (TypeError, ValueError):
        tax_collected = 0.0

    expected = NC_COUNTY_RATES.get(county, [])

    empty = {c: 0.0 for c in COMPONENTS}
    unmatched = dict(
        empty,
        total=tax_collected,
        unallocated=tax_collected,
        matched=False,
        rate=rate,
        county_name=county,
        expected_rates=list(expected),
    )

    if not expected:
        unmatched['reason'] = f"Unknown county '{county_name}'"
        return unmatched

    if rate is None:
        unmatched['reason'] = f"Unreadable tax rate '{rate_charged}'"
        return unmatched

    if rate not in expected:
        allowed = ' or '.join(f'{r:g}%' for r in expected)
        unmatched['reason'] = (
            f"Billed {rate:g}%, but {county} should be {allowed}"
        )
        return unmatched

    structure = RATE_STRUCTURES.get(rate)
    if structure is None:
        unmatched['reason'] = f"No component structure defined for {rate:g}%"
        return unmatched

    # Proportional split. Components are defined as shares of the combined rate,
    # so this reproduces the billed amounts exactly for any taxable base.
    result = {c: (structure[c] / rate) * tax_collected for c in COMPONENTS}
    result.update(
        total=tax_collected,
        unallocated=0.0,
        matched=True,
        rate=rate,
        county_name=county,
        reason=None,
        expected_rates=list(expected),
    )
    return result


def get_current_rate(county_name):
    """Current combined rate for a county, or None if unknown."""
    rates = NC_COUNTY_RATES.get(_normalize_county(county_name))
    return rates[0] if rates else None


def is_known_rate(county_name, rate_charged):
    """True when this county is allowed to have billed this rate."""
    rate = _normalize_rate(rate_charged)
    if rate is None:
        return False
    return rate in NC_COUNTY_RATES.get(_normalize_county(county_name), [])


def get_county_rate_display(county_name, rate_charged=None):
    """Format a rate and its components for display.

    'Mecklenburg 8.25% (4.75% state + 2.00% county + 0.50% transit + 1.00% additional county)'

    Defaults to the county's current rate when rate_charged is omitted.
    """
    county = _normalize_county(county_name)
    rate = _normalize_rate(rate_charged) if rate_charged is not None else get_current_rate(county)

    if rate is None:
        return f'{county_name}: unknown rate'

    structure = RATE_STRUCTURES.get(rate)
    if structure is None:
        return f'{rate:.2f}% (components undefined)'

    parts = [
        f"{structure[c]:.2f}% {COMPONENT_LABELS[c].lower()}"
        for c in COMPONENTS if structure[c] > 0
    ]
    return f"{rate:.2f}% ({' + '.join(parts)})"
