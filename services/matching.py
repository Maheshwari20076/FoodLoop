"""
FoodLoop Smart Rescue Matching engine.

Pure-python, rule-based scoring engine — NO external AI / paid APIs.

Match Score (0-100) is built from 4 weighted components:
    - Urgency / time remaining   : 40%
    - Distance                   : 30%
    - Quantity compatibility     : 20%
    - Recipient suitability      : 10%   (verification status / capacity fit)

The same building blocks are used to:
    1. Compute a donation's overall "Rescue Priority" (Low/Medium/High/Critical)
    2. Rank recipients against a donation to recommend the best match
    3. Rank donations for a recipient's "Find Food" / discovery screen
"""

import math
from datetime import datetime

# ---------------------------------------------------------------------------
# Weights (must sum to 100)
# ---------------------------------------------------------------------------
WEIGHT_URGENCY = 40
WEIGHT_DISTANCE = 30
WEIGHT_QUANTITY = 20
WEIGHT_SUITABILITY = 10


# ---------------------------------------------------------------------------
# Distance
# ---------------------------------------------------------------------------

def haversine_distance_km(lat1, lon1, lat2, lon2):
    """Great-circle distance between two lat/lon points, in kilometers."""
    if None in (lat1, lon1, lat2, lon2):
        return 5.0  # sane default when coordinates are missing

    R = 6371.0  # Earth radius, km
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)

    a = (math.sin(d_phi / 2) ** 2
         + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


# ---------------------------------------------------------------------------
# Component scores (each returns 0..weight)
# ---------------------------------------------------------------------------

def urgency_score(hours_remaining):
    """More urgent (less time left) => higher score. Max 40 pts."""
    if hours_remaining <= 0:
        return 0.0
    if hours_remaining <= 1:
        return WEIGHT_URGENCY * 1.0
    if hours_remaining <= 2:
        return WEIGHT_URGENCY * 0.9
    if hours_remaining <= 4:
        return WEIGHT_URGENCY * 0.75
    if hours_remaining <= 8:
        return WEIGHT_URGENCY * 0.55
    if hours_remaining <= 24:
        return WEIGHT_URGENCY * 0.35
    return WEIGHT_URGENCY * 0.15


def distance_score(distance_km):
    """Closer => higher score. Max 30 pts."""
    if distance_km <= 1:
        return WEIGHT_DISTANCE * 1.0
    if distance_km <= 3:
        return WEIGHT_DISTANCE * 0.85
    if distance_km <= 5:
        return WEIGHT_DISTANCE * 0.7
    if distance_km <= 10:
        return WEIGHT_DISTANCE * 0.5
    if distance_km <= 20:
        return WEIGHT_DISTANCE * 0.25
    return WEIGHT_DISTANCE * 0.1


def quantity_score(meal_count, recipient_capacity):
    """
    Reward recipients whose daily capacity can comfortably absorb the
    donation, without being wildly oversized for it. Max 20 pts.
    """
    if not recipient_capacity or recipient_capacity <= 0:
        recipient_capacity = 50  # default assumption

    if meal_count <= 0:
        return WEIGHT_QUANTITY * 0.5

    ratio = recipient_capacity / meal_count

    if ratio < 0.5:
        # Way too small for this donation
        return WEIGHT_QUANTITY * 0.2
    if ratio < 1:
        return WEIGHT_QUANTITY * 0.6
    if ratio <= 3:
        # Sweet spot: capacity comfortably covers it without huge excess
        return WEIGHT_QUANTITY * 1.0
    if ratio <= 6:
        return WEIGHT_QUANTITY * 0.8
    return WEIGHT_QUANTITY * 0.6


def suitability_score(recipient):
    """Verified, active recipients score higher. Max 10 pts."""
    score = 0.0
    if getattr(recipient, "is_verified", False):
        score += WEIGHT_SUITABILITY * 0.8
    else:
        score += WEIGHT_SUITABILITY * 0.3
    if getattr(recipient, "is_active_account", True):
        score += WEIGHT_SUITABILITY * 0.2
    return min(score, WEIGHT_SUITABILITY)


# ---------------------------------------------------------------------------
# Priority classification (based on overall urgency of the donation itself)
# ---------------------------------------------------------------------------

def classify_priority(hours_remaining):
    if hours_remaining <= 1.5:
        return "Critical"
    if hours_remaining <= 4:
        return "High"
    if hours_remaining <= 10:
        return "Medium"
    return "Low"


PRIORITY_ICONS = {
    "Critical": "🔥",
    "High": "⚠️",
    "Medium": "🟡",
    "Low": "🟢",
}


# ---------------------------------------------------------------------------
# Main scoring entry points
# ---------------------------------------------------------------------------

def hours_remaining_for(available_until):
    delta = available_until - datetime.utcnow()
    return max(delta.total_seconds() / 3600.0, 0)


def score_recipient_for_donation(donation, recipient):
    """
    Compute the full match score (0-100) for one (donation, recipient) pair,
    plus a breakdown and a human-readable reason string.
    """
    hrs = hours_remaining_for(donation.available_until)
    dist = haversine_distance_km(
        donation.latitude, donation.longitude,
        recipient.latitude, recipient.longitude
    )

    u = urgency_score(hrs)
    d = distance_score(dist)
    q = quantity_score(donation.meal_count, recipient.daily_meal_capacity)
    s = suitability_score(recipient)

    total = round(u + d + q + s, 1)
    total = max(0.0, min(total, 100.0))

    reasons = []
    if dist <= 3:
        reasons.append(f"{round(dist, 1)} km away")
    else:
        reasons.append(f"{round(dist, 1)} km away")

    if recipient.daily_meal_capacity and recipient.daily_meal_capacity >= donation.meal_count:
        reasons.append("Enough capacity")
    else:
        reasons.append("Limited capacity")

    if hrs <= 0:
        reasons.append("Expired")
    else:
        h = int(hrs)
        m = int((hrs - h) * 60)
        if h > 0:
            reasons.append(f"Only {h}h {m}m remaining")
        else:
            reasons.append(f"Only {m}m remaining")

    if recipient.is_verified:
        reasons.append("Verified recipient")

    return {
        "recipient": recipient,
        "score": total,
        "distance_km": round(dist, 1),
        "priority": classify_priority(hrs),
        "breakdown": {
            "urgency": round(u, 1),
            "distance": round(d, 1),
            "quantity": round(q, 1),
            "suitability": round(s, 1),
        },
        "reason": " • ".join(reasons),
    }


def find_best_matches(donation, recipients, top_n=5):
    """Rank a list of recipient Users against a donation. Returns sorted list of dicts."""
    results = [score_recipient_for_donation(donation, r) for r in recipients]
    results.sort(key=lambda r: r["score"], reverse=True)
    return results[:top_n]


def compute_donation_priority(donation):
    """Overall rescue priority for a donation (independent of any specific recipient)."""
    hrs = hours_remaining_for(donation.available_until)
    return classify_priority(hrs)
