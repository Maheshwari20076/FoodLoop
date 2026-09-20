"""
FoodLoop seed script.

Creates demo accounts and realistic sample data so the dashboards look good
during a hackathon demo.

Usage:
    python seed.py            # seed the database (safe to re-run: wipes & reseeds)
"""

import random
from datetime import datetime, timedelta

from app import create_app
from models import (
    db, User, FoodDonation, DonationClaim, ImpactRecord, Notification,
    ROLE_DONOR, ROLE_RECIPIENT, ROLE_ADMIN,
    STATUS_AVAILABLE, STATUS_CLAIMED, STATUS_PICKED_UP, STATUS_EXPIRED,
    generate_pickup_code,
)
from services import matching
from services.impact import build_impact_numbers
from services.locations import AREAS

app = create_app()


def reset_database():
    db.drop_all()
    db.create_all()
    print("Database reset.")


def make_user(**kwargs):
    password = kwargs.pop("password")
    user = User(**kwargs)
    user.set_password(password)
    db.session.add(user)
    return user


def seed():
    reset_database()

    # ---------------------------------------------------------------
    # Demo accounts (required credentials)
    # ---------------------------------------------------------------
    admin = make_user(
        role=ROLE_ADMIN, name="Ananya Rao", organization_name="FoodLoop Admin",
        email="admin@foodloop.demo", password="Admin@123", phone="9900011122",
        address="FoodLoop HQ, MG Road", area="MG Road", latitude=AREAS["MG Road"][0],
        longitude=AREAS["MG Road"][1], is_verified=True,
    )

    donor_main = make_user(
        role=ROLE_DONOR, name="Rahul Sharma", organization_name="Green Leaf Restaurant",
        email="donor@foodloop.demo", password="Donor@123", phone="9900011234",
        address="80 Ft Road, Koramangala", area="Koramangala",
        latitude=AREAS["Koramangala"][0], longitude=AREAS["Koramangala"][1],
        is_verified=True,
    )

    recipient_main = make_user(
        role=ROLE_RECIPIENT, name="Priya Menon", organization_name="Asha Community Kitchen",
        email="recipient@foodloop.demo", password="Recipient@123", phone="9900011999",
        address="5th Cross, HSR Layout", area="HSR Layout",
        latitude=AREAS["HSR Layout"][0], longitude=AREAS["HSR Layout"][1],
        recipient_type="Community Kitchen", daily_meal_capacity=120,
        is_verified=True,
    )

    db.session.flush()

    # ---------------------------------------------------------------
    # Extra donors
    # ---------------------------------------------------------------
    extra_donors_data = [
        ("Sunita Iyer", "Whitefield Tech Park Canteen", "whitefield.canteen@foodloop.demo", "Whitefield", True),
        ("Vikram Patel", "St. Xavier's College Hostel Mess", "sxc.hostel@foodloop.demo", "Jayanagar", True),
        ("Meera Nair", "Spice Route Caterers", "spiceroute@foodloop.demo", "Indiranagar", True),
        ("Arjun Reddy", "Electronic City Corporate Cafeteria", "ecity.cafeteria@foodloop.demo", "Electronic City", False),
        ("Kavya Das", "Sunrise Banquet Hall", "sunrise.banquet@foodloop.demo", "Marathahalli", True),
        ("Farhan Khan", "Malleshwaram Sweet House", "malleshwaram.sweets@foodloop.demo", "Malleshwaram", False),
    ]
    donors = [donor_main]
    for name, org, email, area, verified in extra_donors_data:
        d = make_user(
            role=ROLE_DONOR, name=name, organization_name=org, email=email,
            password="Donor@123", phone=f"99000{random.randint(10000,99999)}",
            address=f"{org}, {area}", area=area,
            latitude=AREAS[area][0], longitude=AREAS[area][1], is_verified=verified,
        )
        donors.append(d)

    # ---------------------------------------------------------------
    # Extra recipients
    # ---------------------------------------------------------------
    extra_recipients_data = [
        ("Deepa Krishnan", "Nightingale Shelter Home", "nightingale.shelter@foodloop.demo", "BTM Layout", "Shelter", 60, True),
        ("Suresh Kumar", "Bright Future NGO", "brightfuture.ngo@foodloop.demo", "Jayanagar", "NGO", 90, True),
        ("Lakshmi Venkatesh", "Hope Orphanage", "hope.orphanage@foodloop.demo", "JP Nagar", "Orphanage", 45, True),
        ("Ravi Shastri", "Sunset Old Age Home", "sunset.oldage@foodloop.demo", "Yeshwanthpur", "Old Age Home", 35, True),
        ("Fatima Sheikh", "Seva Bharati NGO", "sevabharati@foodloop.demo", "Indiranagar", "NGO", 100, False),
        ("Joseph Thomas", "Milaap Community Kitchen", "milaap.kitchen@foodloop.demo", "Whitefield", "Community Kitchen", 150, True),
    ]
    recipients = [recipient_main]
    for name, org, email, area, r_type, capacity, verified in extra_recipients_data:
        r = make_user(
            role=ROLE_RECIPIENT, name=name, organization_name=org, email=email,
            password="Recipient@123", phone=f"99000{random.randint(10000,99999)}",
            address=f"{org}, {area}", area=area,
            latitude=AREAS[area][0], longitude=AREAS[area][1],
            recipient_type=r_type, daily_meal_capacity=capacity, is_verified=verified,
        )
        recipients.append(r)

    db.session.flush()

    # ---------------------------------------------------------------
    # Donations: mix of AVAILABLE (varied urgency), CLAIMED, PICKED_UP, EXPIRED
    # ---------------------------------------------------------------
    now = datetime.utcnow()

    food_catalog = [
        ("Veg Biryani & Raita", "Cooked Meals", 45, 15, "kg", "Fresh"),
        ("Assorted Bakery Items", "Bakery", 30, 8, "kg", "Good"),
        ("Fresh Vegetable Mix", "Produce", 60, 25, "kg", "Fresh"),
        ("Packaged Sandwiches", "Packaged Food", 25, 12, "packets", "Fresh"),
        ("Dal Rice & Sabzi", "Cooked Meals", 80, 30, "kg", "Fresh"),
        ("Milk & Dairy Surplus", "Dairy", 20, 10, "litres", "Near Expiry"),
        ("Wedding Buffet Leftovers", "Cooked Meals", 120, 40, "kg", "Fresh"),
        ("Bread & Pastries", "Bakery", 35, 9, "kg", "Good"),
        ("Fruit Juice Bottles", "Beverages", 15, 6, "litres", "Fresh"),
        ("Chapati & Curry Combo", "Cooked Meals", 55, 20, "kg", "Fresh"),
        ("Canteen Snack Surplus", "Packaged Food", 18, 7, "packets", "Good"),
        ("Idli Sambar Batch", "Cooked Meals", 40, 14, "kg", "Fresh"),
    ]

    donations = []

    # AVAILABLE donations with a spread of urgency (critical -> low)
    urgency_hours = [0.9, 1.3, 2.5, 3.8, 6, 9, 14, 22]
    for i, hours in enumerate(urgency_hours):
        food_name, category, meals, qty, unit, condition = food_catalog[i % len(food_catalog)]
        donor = donors[i % len(donors)]
        donation = FoodDonation(
            donor_id=donor.id,
            food_name=food_name,
            category=category,
            description=f"Surplus {food_name.lower()} in good condition, ready for immediate pickup.",
            quantity=qty,
            quantity_unit=unit,
            meal_count=meals,
            food_condition=condition,
            pickup_location=donor.address,
            area=donor.area,
            latitude=donor.latitude,
            longitude=donor.longitude,
            available_until=now + timedelta(hours=hours),
            status=STATUS_AVAILABLE,
        )
        donation.priority = matching.compute_donation_priority(donation)
        db.session.add(donation)
        donations.append(donation)

    db.session.flush()

    # Compute best match for each available donation
    all_recipients = [r for r in recipients]
    for donation in donations:
        best = matching.find_best_matches(donation, all_recipients, top_n=1)
        if best:
            top = best[0]
            donation.best_match_recipient_id = top["recipient"].id
            donation.best_match_score = top["score"]
            donation.best_match_reason = top["reason"]

    # ---------------------------------------------------------------
    # A few CLAIMED donations (in progress)
    # ---------------------------------------------------------------
    claimed_specs = [
        ("Paneer Butter Masala & Rice", "Cooked Meals", 50, 18, "kg", "Fresh", 3),
        ("Leftover Party Snacks", "Packaged Food", 22, 9, "packets", "Good", 5),
    ]
    for i, (food_name, category, meals, qty, unit, condition, hours) in enumerate(claimed_specs):
        donor = donors[(i + 2) % len(donors)]
        recipient = recipients[(i + 1) % len(recipients)]
        donation = FoodDonation(
            donor_id=donor.id,
            food_name=food_name, category=category,
            description=f"Surplus {food_name.lower()}, claimed and awaiting pickup.",
            quantity=qty, quantity_unit=unit, meal_count=meals, food_condition=condition,
            pickup_location=donor.address, area=donor.area,
            latitude=donor.latitude, longitude=donor.longitude,
            available_until=now + timedelta(hours=hours),
            status=STATUS_CLAIMED,
        )
        donation.priority = matching.compute_donation_priority(donation)
        db.session.add(donation)
        db.session.flush()

        match = matching.score_recipient_for_donation(donation, recipient)
        donation.best_match_recipient_id = recipient.id
        donation.best_match_score = match["score"]
        donation.best_match_reason = match["reason"]

        claim = DonationClaim(
            donation_id=donation.id, recipient_id=recipient.id,
            pickup_code=generate_pickup_code(),
            match_score=match["score"], distance_km=match["distance_km"],
            status=STATUS_CLAIMED,
            claimed_at=now - timedelta(minutes=random.randint(10, 90)),
        )
        db.session.add(claim)

    # ---------------------------------------------------------------
    # PICKED_UP donations (completed rescues, spread over the past 2 weeks)
    # for realistic dashboard / impact charts
    # ---------------------------------------------------------------
    completed_specs = [
        ("Chole Bhature Surplus", "Cooked Meals", 35, 12, "kg", 12),
        ("Fresh Salad Bar Leftovers", "Produce", 20, 8, "kg", 10),
        ("Cupcakes & Pastries", "Bakery", 40, 10, "kg", 9),
        ("Rajma Chawal Batch", "Cooked Meals", 65, 22, "kg", 8),
        ("Fruit Basket Surplus", "Produce", 28, 14, "kg", 7),
        ("Sandwich Platter", "Packaged Food", 30, 10, "packets", 6),
        ("Pav Bhaji Batch", "Cooked Meals", 48, 16, "kg", 5),
        ("Dairy Surplus Pack", "Dairy", 18, 9, "litres", 4),
        ("South Indian Thali", "Cooked Meals", 70, 25, "kg", 3),
        ("Bakery Assorted Box", "Bakery", 26, 7, "kg", 2),
        ("Event Buffet Surplus", "Cooked Meals", 95, 32, "kg", 1),
        ("Juice & Beverage Surplus", "Beverages", 22, 9, "litres", 1),
    ]
    for i, (food_name, category, meals, qty, unit, days_ago) in enumerate(completed_specs):
        donor = donors[i % len(donors)]
        recipient = recipients[(i + 2) % len(recipients)]
        created_at = now - timedelta(days=days_ago, hours=random.randint(1, 5))
        available_until = created_at + timedelta(hours=random.choice([2, 3, 4, 6]))

        donation = FoodDonation(
            donor_id=donor.id,
            food_name=food_name, category=category,
            description=f"{food_name} — successfully rescued.",
            quantity=qty, quantity_unit=unit, meal_count=meals, food_condition="Fresh",
            pickup_location=donor.address, area=donor.area,
            latitude=donor.latitude, longitude=donor.longitude,
            created_at=created_at,
            available_until=available_until,
            status=STATUS_PICKED_UP,
        )
        donation.priority = matching.compute_donation_priority(donation) or "Medium"
        db.session.add(donation)
        db.session.flush()

        match = matching.score_recipient_for_donation(donation, recipient)
        donation.best_match_recipient_id = recipient.id
        donation.best_match_score = match["score"]
        donation.best_match_reason = match["reason"]

        claimed_at = created_at + timedelta(minutes=random.randint(5, 40))
        picked_up_at = claimed_at + timedelta(minutes=random.randint(15, 90))

        claim = DonationClaim(
            donation_id=donation.id, recipient_id=recipient.id,
            pickup_code=generate_pickup_code(),
            match_score=match["score"], distance_km=match["distance_km"],
            status=STATUS_PICKED_UP,
            claimed_at=claimed_at, picked_up_at=picked_up_at,
        )
        db.session.add(claim)

        impact_numbers = build_impact_numbers(meals, qty, unit)
        impact_record = ImpactRecord(
            donation_id=donation.id, donor_id=donor.id, recipient_id=recipient.id,
            meals_rescued=impact_numbers["meals"],
            food_weight_kg=impact_numbers["weight_kg"],
            co2e_avoided_kg=impact_numbers["co2e_kg"],
            created_at=picked_up_at,
        )
        db.session.add(impact_record)

    # ---------------------------------------------------------------
    # A couple of EXPIRED donations for realism
    # ---------------------------------------------------------------
    expired_specs = [
        ("Unclaimed Bread Surplus", "Bakery", 15, 5, "kg"),
        ("Unclaimed Rice Batch", "Cooked Meals", 20, 7, "kg"),
    ]
    for i, (food_name, category, meals, qty, unit) in enumerate(expired_specs):
        donor = donors[(i + 3) % len(donors)]
        created_at = now - timedelta(days=2)
        donation = FoodDonation(
            donor_id=donor.id,
            food_name=food_name, category=category,
            description=f"{food_name} — went unclaimed and expired.",
            quantity=qty, quantity_unit=unit, meal_count=meals, food_condition="Good",
            pickup_location=donor.address, area=donor.area,
            latitude=donor.latitude, longitude=donor.longitude,
            created_at=created_at,
            available_until=created_at + timedelta(hours=3),
            status=STATUS_EXPIRED,
        )
        donation.priority = "Medium"
        db.session.add(donation)

    # ---------------------------------------------------------------
    # A couple of notifications
    # ---------------------------------------------------------------
    db.session.add(Notification(
        user_id=donor_main.id,
        message="Your donation 'Paneer Butter Masala & Rice' was claimed by a recipient.",
    ))
    db.session.add(Notification(
        user_id=recipient_main.id,
        message="New high-priority donation available near HSR Layout.",
    ))

    db.session.commit()
    print("Seed data created successfully.")
    print("\nDemo accounts:")
    print("  Admin:      admin@foodloop.demo / Admin@123")
    print("  Donor:      donor@foodloop.demo / Donor@123")
    print("  Recipient:  recipient@foodloop.demo / Recipient@123")


if __name__ == "__main__":
    with app.app_context():
        seed()
