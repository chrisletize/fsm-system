"""
North Carolina County Tax Rate Breakdown
Data accurate as of December 2025

NC Sales Tax Structure:
- State: Always 4.75%
- County: 2.00% or 2.25%
- Transit: 0.5% (only certain counties)

Total rates range from 6.75% to 7.50%
"""

# County tax rate breakdown
# Format: 'County Name': {'total': 7.00, 'state': 4.75, 'county': 2.25, 'transit': 0.00}

NC_COUNTY_TAX_RATES = {
    # 6.75% counties (State 4.75% + County 2.00%)
    'Alamance': {'total': 6.75, 'state': 4.75, 'county': 2.00, 'transit': 0.00},
    'Avery': {'total': 6.75, 'state': 4.75, 'county': 2.00, 'transit': 0.00},
    'Beaufort': {'total': 6.75, 'state': 4.75, 'county': 2.00, 'transit': 0.00},
    'Bladen': {'total': 6.75, 'state': 4.75, 'county': 2.00, 'transit': 0.00},
    'Brunswick': {'total': 6.75, 'state': 4.75, 'county': 2.00, 'transit': 0.00},
    'Burke': {'total': 6.75, 'state': 4.75, 'county': 2.00, 'transit': 0.00},
    'Caldwell': {'total': 6.75, 'state': 4.75, 'county': 2.00, 'transit': 0.00},
    'Camden': {'total': 6.75, 'state': 4.75, 'county': 2.00, 'transit': 0.00},
    'Carteret': {'total': 6.75, 'state': 4.75, 'county': 2.00, 'transit': 0.00},
    'Caswell': {'total': 6.75, 'state': 4.75, 'county': 2.00, 'transit': 0.00},
    'Chowan': {'total': 6.75, 'state': 4.75, 'county': 2.00, 'transit': 0.00},
    'Cleveland': {'total': 6.75, 'state': 4.75, 'county': 2.00, 'transit': 0.00},
    'Columbus': {'total': 6.75, 'state': 4.75, 'county': 2.00, 'transit': 0.00},
    'Craven': {'total': 6.75, 'state': 4.75, 'county': 2.00, 'transit': 0.00},
    'Currituck': {'total': 6.75, 'state': 4.75, 'county': 2.00, 'transit': 0.00},
    'Dare': {'total': 6.75, 'state': 4.75, 'county': 2.00, 'transit': 0.00},
    'Davie': {'total': 6.75, 'state': 4.75, 'county': 2.00, 'transit': 0.00},
    'Forsyth': {'total': 6.75, 'state': 4.75, 'county': 2.00, 'transit': 0.00},
    'Franklin': {'total': 6.75, 'state': 4.75, 'county': 2.00, 'transit': 0.00},
    'Gates': {'total': 6.75, 'state': 4.75, 'county': 2.00, 'transit': 0.00},
    'Granville': {'total': 6.75, 'state': 4.75, 'county': 2.00, 'transit': 0.00},
    'Guilford': {'total': 6.75, 'state': 4.75, 'county': 2.00, 'transit': 0.00},
    'Henderson': {'total': 6.75, 'state': 4.75, 'county': 2.00, 'transit': 0.00},
    'Hoke': {'total': 6.75, 'state': 4.75, 'county': 2.00, 'transit': 0.00},
    'Hyde': {'total': 6.75, 'state': 4.75, 'county': 2.00, 'transit': 0.00},
    'Iredell': {'total': 6.75, 'state': 4.75, 'county': 2.00, 'transit': 0.00},
    'Johnston': {'total': 6.75, 'state': 4.75, 'county': 2.00, 'transit': 0.00},
    'Lenoir': {'total': 6.75, 'state': 4.75, 'county': 2.00, 'transit': 0.00},
    'Macon': {'total': 6.75, 'state': 4.75, 'county': 2.00, 'transit': 0.00},
    'Madison': {'total': 6.75, 'state': 4.75, 'county': 2.00, 'transit': 0.00},
    'McDowell': {'total': 6.75, 'state': 4.75, 'county': 2.00, 'transit': 0.00},
    'Mitchell': {'total': 6.75, 'state': 4.75, 'county': 2.00, 'transit': 0.00},
    'Nash': {'total': 6.75, 'state': 4.75, 'county': 2.00, 'transit': 0.00},
    'Northampton': {'total': 6.75, 'state': 4.75, 'county': 2.00, 'transit': 0.00},
    'Pamlico': {'total': 6.75, 'state': 4.75, 'county': 2.00, 'transit': 0.00},
    'Pender': {'total': 6.75, 'state': 4.75, 'county': 2.00, 'transit': 0.00},
    'Perquimans': {'total': 6.75, 'state': 4.75, 'county': 2.00, 'transit': 0.00},
    'Person': {'total': 6.75, 'state': 4.75, 'county': 2.00, 'transit': 0.00},
    'Polk': {'total': 6.75, 'state': 4.75, 'county': 2.00, 'transit': 0.00},
    'Richmond': {'total': 6.75, 'state': 4.75, 'county': 2.00, 'transit': 0.00},
    'Scotland': {'total': 6.75, 'state': 4.75, 'county': 2.00, 'transit': 0.00},
    'Stokes': {'total': 6.75, 'state': 4.75, 'county': 2.00, 'transit': 0.00},
    'Transylvania': {'total': 6.75, 'state': 4.75, 'county': 2.00, 'transit': 0.00},
    'Tyrrell': {'total': 6.75, 'state': 4.75, 'county': 2.00, 'transit': 0.00},
    'Union': {'total': 6.75, 'state': 4.75, 'county': 2.00, 'transit': 0.00},
    'Vance': {'total': 6.75, 'state': 4.75, 'county': 2.00, 'transit': 0.00},
    'Warren': {'total': 6.75, 'state': 4.75, 'county': 2.00, 'transit': 0.00},
    'Washington': {'total': 6.75, 'state': 4.75, 'county': 2.00, 'transit': 0.00},
    'Watauga': {'total': 6.75, 'state': 4.75, 'county': 2.00, 'transit': 0.00},
    'Wayne': {'total': 6.75, 'state': 4.75, 'county': 2.00, 'transit': 0.00},
    'Wilson': {'total': 6.75, 'state': 4.75, 'county': 2.00, 'transit': 0.00},
    'Yadkin': {'total': 6.75, 'state': 4.75, 'county': 2.00, 'transit': 0.00},
    'Yancey': {'total': 6.75, 'state': 4.75, 'county': 2.00, 'transit': 0.00},
    
    # 7.00% counties (State 4.75% + County 2.25%)
    'Alexander': {'total': 7.00, 'state': 4.75, 'county': 2.25, 'transit': 0.00},
    'Alleghany': {'total': 7.00, 'state': 4.75, 'county': 2.25, 'transit': 0.00},
    'Anson': {'total': 7.00, 'state': 4.75, 'county': 2.25, 'transit': 0.00},
    'Ashe': {'total': 7.00, 'state': 4.75, 'county': 2.25, 'transit': 0.00},
    'Bertie': {'total': 7.00, 'state': 4.75, 'county': 2.25, 'transit': 0.00},
    'Buncombe': {'total': 7.00, 'state': 4.75, 'county': 2.25, 'transit': 0.00},
    'Cabarrus': {'total': 7.00, 'state': 4.75, 'county': 2.25, 'transit': 0.00},
    'Catawba': {'total': 7.00, 'state': 4.75, 'county': 2.25, 'transit': 0.00},
    'Chatham': {'total': 7.00, 'state': 4.75, 'county': 2.25, 'transit': 0.00},
    'Cherokee': {'total': 7.00, 'state': 4.75, 'county': 2.25, 'transit': 0.00},
    'Clay': {'total': 7.00, 'state': 4.75, 'county': 2.25, 'transit': 0.00},
    'Cumberland': {'total': 7.00, 'state': 4.75, 'county': 2.25, 'transit': 0.00},
    'Davidson': {'total': 7.00, 'state': 4.75, 'county': 2.25, 'transit': 0.00},
    'Duplin': {'total': 7.00, 'state': 4.75, 'county': 2.25, 'transit': 0.00},
    'Edgecombe': {'total': 7.00, 'state': 4.75, 'county': 2.25, 'transit': 0.00},
    'Gaston': {'total': 7.00, 'state': 4.75, 'county': 2.25, 'transit': 0.00},
    'Graham': {'total': 7.00, 'state': 4.75, 'county': 2.25, 'transit': 0.00},
    'Greene': {'total': 7.00, 'state': 4.75, 'county': 2.25, 'transit': 0.00},
    'Halifax': {'total': 7.00, 'state': 4.75, 'county': 2.25, 'transit': 0.00},
    'Harnett': {'total': 7.00, 'state': 4.75, 'county': 2.25, 'transit': 0.00},
    'Haywood': {'total': 7.00, 'state': 4.75, 'county': 2.25, 'transit': 0.00},
    'Hertford': {'total': 7.00, 'state': 4.75, 'county': 2.25, 'transit': 0.00},
    'Jackson': {'total': 7.00, 'state': 4.75, 'county': 2.25, 'transit': 0.00},
    'Jones': {'total': 7.00, 'state': 4.75, 'county': 2.25, 'transit': 0.00},
    'Lee': {'total': 7.00, 'state': 4.75, 'county': 2.25, 'transit': 0.00},
    'Lincoln': {'total': 7.00, 'state': 4.75, 'county': 2.25, 'transit': 0.00},
    'Martin': {'total': 7.00, 'state': 4.75, 'county': 2.25, 'transit': 0.00},
    'Montgomery': {'total': 7.00, 'state': 4.75, 'county': 2.25, 'transit': 0.00},
    'Moore': {'total': 7.00, 'state': 4.75, 'county': 2.25, 'transit': 0.00},
    'New Hanover': {'total': 7.00, 'state': 4.75, 'county': 2.25, 'transit': 0.00},
    'Onslow': {'total': 7.00, 'state': 4.75, 'county': 2.25, 'transit': 0.00},
    'Pasquotank': {'total': 7.00, 'state': 4.75, 'county': 2.25, 'transit': 0.00},
    'Pitt': {'total': 7.00, 'state': 4.75, 'county': 2.25, 'transit': 0.00},
    'Randolph': {'total': 7.00, 'state': 4.75, 'county': 2.25, 'transit': 0.00},
    'Robeson': {'total': 7.00, 'state': 4.75, 'county': 2.25, 'transit': 0.00},
    'Rockingham': {'total': 7.00, 'state': 4.75, 'county': 2.25, 'transit': 0.00},
    'Rowan': {'total': 7.00, 'state': 4.75, 'county': 2.25, 'transit': 0.00},
    'Rutherford': {'total': 7.00, 'state': 4.75, 'county': 2.25, 'transit': 0.00},
    'Sampson': {'total': 7.00, 'state': 4.75, 'county': 2.25, 'transit': 0.00},
    'Stanly': {'total': 7.00, 'state': 4.75, 'county': 2.25, 'transit': 0.00},
    'Surry': {'total': 7.00, 'state': 4.75, 'county': 2.25, 'transit': 0.00},
    'Swain': {'total': 7.00, 'state': 4.75, 'county': 2.25, 'transit': 0.00},
    'Wilkes': {'total': 7.00, 'state': 4.75, 'county': 2.25, 'transit': 0.00},
    
    # 7.25% counties (State 4.75% + County 2.00% + Transit 0.5%)
    'Mecklenburg': {'total': 7.25, 'state': 4.75, 'county': 2.00, 'transit': 0.50},
    'Wake': {'total': 7.25, 'state': 4.75, 'county': 2.00, 'transit': 0.50},
    
    # 7.50% counties (State 4.75% + County 2.25% + Transit 0.5%)
    'Durham': {'total': 7.50, 'state': 4.75, 'county': 2.25, 'transit': 0.50},
    'Orange': {'total': 7.50, 'state': 4.75, 'county': 2.25, 'transit': 0.50},
}

def get_tax_breakdown(county_name, tax_collected):
    """
    Calculate state, county, and transit tax portions
    
    Args:
        county_name (str): Name of NC county
        tax_collected (float): Total tax collected
    
    Returns:
        dict: {'state': float, 'county': float, 'transit': float, 'total': float}
    """
    if county_name not in NC_COUNTY_TAX_RATES:
        # Default to 7.00% if county not found
        rates = {'total': 7.00, 'state': 4.75, 'county': 2.25, 'transit': 0.00}
    else:
        rates = NC_COUNTY_TAX_RATES[county_name]
    
    total_rate = rates['total']
    
    # Calculate each portion based on percentage of total rate
    state_portion = (rates['state'] / total_rate) * tax_collected
    county_portion = (rates['county'] / total_rate) * tax_collected
    transit_portion = (rates['transit'] / total_rate) * tax_collected if rates['transit'] > 0 else 0
    
    return {
        'state': round(state_portion, 2),
        'county': round(county_portion, 2),
        'transit': round(transit_portion, 2),
        'total': round(tax_collected, 2),
        'rate_info': rates
    }

def get_county_rate_display(county_name):
    """
    Get formatted display string for county tax rate
    
    Args:
        county_name (str): Name of NC county
    
    Returns:
        str: Formatted rate string like "7.00% (4.75% state + 2.25% county)"
    """
    if county_name not in NC_COUNTY_TAX_RATES:
        return "7.00% (4.75% state + 2.25% county)"
    
    rates = NC_COUNTY_TAX_RATES[county_name]
    
    if rates['transit'] > 0:
        return f"{rates['total']:.2f}% ({rates['state']:.2f}% state + {rates['county']:.2f}% county + {rates['transit']:.2f}% transit)"
    else:
        return f"{rates['total']:.2f}% ({rates['state']:.2f}% state + {rates['county']:.2f}% county)"
