"""
Company branding configuration
Maps company IDs to their visual identity
"""
COMPANY_BRANDING = {
    0: {  # No company selected
        'name': 'LKit',
        'display_name': 'LKit - Business Tools',
        'logo': 'lkit-logo.svg',
        'primary_color': '#8b7a9e',      # Muted lavender-grey
        'secondary_color': '#b8a3d1',    # Lighter lavender
        'accent_color': '#4a4a4a',       # Medium grey
        'background_color': '#ede5f5'    # Very light lavender
    },
    1: {  # Kleanit Charlotte
        'name': 'Kleanit.com',
        'display_name': 'Kleanit.com - Charlotte',
        'logo': 'kleanit-logo.png',
        'primary_color': '#0052CC',      # Royal blue
        'secondary_color': '#00D66C',    # Bright green
        'accent_color': '#1a1a1a',       # Dark gray
        'background_color': '#e6f2ff'    # Light blue
    },
    2: {  # Get a Grip Resurfacing of Charlotte
        'name': 'Get a Grip Resurfacing of Charlotte',
        'display_name': 'Get a Grip Resurfacing of Charlotte',
        'logo': 'get-a-grip-logo.jpg',
        'primary_color': '#8B1538',      # Burgundy
        'secondary_color': '#F5F5DC',    # Cream
        'accent_color': '#2C2C2C',       # Dark charcoal
        'background_color': '#FFF5F0'    # Light cream
    },
    3: {  # CTS of Raleigh
        'name': 'CTS of Raleigh',
        'display_name': 'CTS of Raleigh',
        'logo': 'cts-logo.jpg',
        'primary_color': '#2C2C2C',      # Dark gray
        'secondary_color': '#F5F5DC',    # Cream
        'accent_color': '#666666',       # Medium gray
        'background_color': '#F5F5F5'    # Light gray
    },
    4: {  # Kleanit South Florida
        'name': 'Kleanit.com',
        'display_name': 'Kleanit.com - South Florida',
        'logo': 'kleanit-logo.png',
        'primary_color': '#00D66C',      # Green (different from Charlotte!)
        'secondary_color': '#0052CC',    # Blue
        'accent_color': '#1a1a1a',
        'background_color': '#e6ffe6'    # Light green
    }
}

def get_branding(company_id):
    """Get branding for a company, with fallback to default if not found"""
    return COMPANY_BRANDING.get(company_id, COMPANY_BRANDING[0])
