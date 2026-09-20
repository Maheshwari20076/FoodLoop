"""Public routes: landing page."""

from flask import Blueprint, render_template
from flask_login import current_user

from models import db, FoodDonation, ImpactRecord, User, STATUS_PICKED_UP, ROLE_DONOR, ROLE_RECIPIENT
from sqlalchemy import func

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def landing():
    # Live-ish platform stats for the landing page
    meals_rescued = db.session.query(func.coalesce(func.sum(ImpactRecord.meals_rescued), 0)).scalar()
    food_saved_kg = db.session.query(func.coalesce(func.sum(ImpactRecord.food_weight_kg), 0)).scalar()
    co2e_avoided = db.session.query(func.coalesce(func.sum(ImpactRecord.co2e_avoided_kg), 0)).scalar()
    successful_connections = ImpactRecord.query.count()
    donor_count = User.query.filter_by(role=ROLE_DONOR).count()
    recipient_count = User.query.filter_by(role=ROLE_RECIPIENT).count()
    active_donations = FoodDonation.query.filter_by(status="AVAILABLE").count()

    stats = {
        "meals_rescued": int(meals_rescued or 0),
        "food_saved_kg": round(food_saved_kg or 0, 1),
        "co2e_avoided_kg": round(co2e_avoided or 0, 1),
        "successful_connections": successful_connections,
        "donor_count": donor_count,
        "recipient_count": recipient_count,
        "active_donations": active_donations,
    }

    return render_template("landing.html", stats=stats)
