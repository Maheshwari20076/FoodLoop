"""
Sample locality coordinates (Bengaluru) used so the demo has realistic,
varied distances between donors and recipients without needing a real
geocoding API. Users pick their "Area" during registration / donation
creation, and we resolve it to a lat/lon pair server-side.
"""

AREAS = {
    "Koramangala": (12.9352, 77.6245),
    "Indiranagar": (12.9719, 77.6412),
    "HSR Layout": (12.9121, 77.6446),
    "Whitefield": (12.9698, 77.7500),
    "Jayanagar": (12.9308, 77.5838),
    "MG Road": (12.9758, 77.6045),
    "Electronic City": (12.8452, 77.6602),
    "Marathahalli": (12.9569, 77.7011),
    "BTM Layout": (12.9166, 77.6101),
    "Yeshwanthpur": (13.0284, 77.5546),
    "Malleshwaram": (13.0035, 77.5709),
    "JP Nagar": (12.9077, 77.5851),
}

DEFAULT_AREA = "Koramangala"


def resolve_area(area_name):
    return AREAS.get(area_name, AREAS[DEFAULT_AREA])


def area_choices():
    return sorted(AREAS.keys())
