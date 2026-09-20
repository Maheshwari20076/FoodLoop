"""
FoodLoop impact estimation helpers.

All numbers here are ESTIMATES based on commonly cited averages, used to give
donors/recipients a rough sense of impact. They are not precise measurements.

Assumptions (clearly labeled everywhere in the UI as "estimated"):
    - 1 rescued meal ≈ 0.45 kg of food
    - Every kg of food waste avoided ≈ 2.5 kg CO2e avoided
      (rough average used widely in food-waste sustainability reporting)
"""

KG_PER_MEAL = 0.45
CO2E_PER_KG_FOOD = 2.5


def estimate_weight_kg(meal_count, fallback_quantity=None, fallback_unit=None):
    if meal_count and meal_count > 0:
        return round(meal_count * KG_PER_MEAL, 2)
    if fallback_quantity:
        if fallback_unit == "kg":
            return round(fallback_quantity, 2)
        if fallback_unit == "litres":
            return round(fallback_quantity * 1.03, 2)  # ~ density of water-based food
        return round(fallback_quantity * 0.3, 2)  # packets/plates fallback
    return 0.0


def estimate_co2e_kg(weight_kg):
    return round(weight_kg * CO2E_PER_KG_FOOD, 2)


def build_impact_numbers(meal_count, quantity=None, unit=None):
    weight = estimate_weight_kg(meal_count, quantity, unit)
    co2e = estimate_co2e_kg(weight)
    return {
        "meals": meal_count or 0,
        "weight_kg": weight,
        "co2e_kg": co2e,
    }
