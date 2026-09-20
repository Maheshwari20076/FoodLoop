"""Donor routes: dashboard, create donation, my donations, donation details, impact."""

import os
import uuid
from datetime import datetime

from flask import (
    Blueprint, render_template, redirect, url_for, request, flash,
    current_app, abort
)
from flask_login import login_required, current_user
from sqlalchemy import func
from werkzeug.utils import secure_filename

from models import (
    db, FoodDonation, User, DonationClaim, ImpactRecord,
    ROLE_DONOR, ROLE_RECIPIENT, STATUS_AVAILABLE, STATUS_CLAIMED,
    STATUS_PICKED_UP, STATUS_EXPIRED, STATUS_CANCELLED,
)
from decorators import role_required
from services import matching
from services.locations import area_choices, resolve_area

donor_bp = Blueprint("donor", __name__, url_prefix="/donor")

FOOD_CATEGORIES = ["Cooked Meals", "Bakery", "Produce", "Packaged Food", "Dairy", "Beverages", "Other"]
FOOD_CONDITIONS = ["Fresh", "Good", "Near Expiry"]
QUANTITY_UNITS = ["kg", "plates", "packets", "litres"]


def _allowed_file(filename):
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return ext in current_app.config["ALLOWED_EXTENSIONS"]


def _sync_expired(donations):
    """Mark any AVAILABLE donations whose time has passed as EXPIRED."""
    changed = False
    for d in donations:
        if d.status == STATUS_AVAILABLE and d.is_expired:
            d.status = STATUS_EXPIRED
            changed = True
    if changed:
        db.session.commit()


@donor_bp.route("/dashboard")
@login_required
@role_required(ROLE_DONOR)
def dashboard():
    donations = current_user.donations.order_by(FoodDonation.created_at.desc()).all()
    _sync_expired(donations)

    active_donations = [d for d in donations if d.status == STATUS_AVAILABLE]
    successful_pickups = [d for d in donations if d.status == STATUS_PICKED_UP]

    impact_agg = db.session.query(
        func.coalesce(func.sum(ImpactRecord.meals_rescued), 0),
        func.coalesce(func.sum(ImpactRecord.food_weight_kg), 0),
    ).filter(ImpactRecord.donor_id == current_user.id).first()

    meals_rescued = int(impact_agg[0] or 0)
    food_saved_kg = round(impact_agg[1] or 0, 1)

    recent = donations[:8]

    return render_template(
        "donor/dashboard.html",
        active_count=len(active_donations),
        meals_rescued=meals_rescued,
        food_saved_kg=food_saved_kg,
        pickups_count=len(successful_pickups),
        donations=recent,
    )


@donor_bp.route("/donations/new", methods=["GET", "POST"])
@login_required
@role_required(ROLE_DONOR)
def create_donation():
    if request.method == "POST":
        food_name = request.form.get("food_name", "").strip()
        category = request.form.get("category", "").strip()
        description = request.form.get("description", "").strip()
        quantity_raw = request.form.get("quantity", "").strip()
        quantity_unit = request.form.get("quantity_unit", "kg")
        meal_count_raw = request.form.get("meal_count", "").strip()
        food_condition = request.form.get("food_condition", "Fresh")
        pickup_location = request.form.get("pickup_location", "").strip()
        area = request.form.get("area", current_user.area or "Koramangala")
        available_until_raw = request.form.get("available_until", "").strip()

        errors = []
        quantity = None
        meal_count = None

        if not food_name:
            errors.append("Food name is required.")
        if category not in FOOD_CATEGORIES:
            errors.append("Please choose a valid category.")
        try:
            quantity = float(quantity_raw)
            if quantity <= 0:
                errors.append("Quantity must be greater than zero.")
        except ValueError:
            errors.append("Quantity must be a number.")
        try:
            meal_count = int(meal_count_raw)
            if meal_count <= 0:
                errors.append("Meal count must be greater than zero.")
        except ValueError:
            errors.append("Meal count must be a whole number.")
        if quantity_unit not in QUANTITY_UNITS:
            errors.append("Please choose a valid quantity unit.")
        if food_condition not in FOOD_CONDITIONS:
            errors.append("Please choose a valid food condition.")
        if not pickup_location:
            errors.append("Pickup location is required.")

        available_until = None
        if not available_until_raw:
            errors.append("Please specify how long this food is available for pickup.")
        else:
            try:
                available_until = datetime.strptime(available_until_raw, "%Y-%m-%dT%H:%M")
                if available_until <= datetime.utcnow():
                    errors.append("Availability deadline must be in the future.")
            except ValueError:
                errors.append("Invalid date/time format.")

        image_filename = None
        image_file = request.files.get("image")
        if image_file and image_file.filename:
            if _allowed_file(image_file.filename):
                ext = image_file.filename.rsplit(".", 1)[-1].lower()
                image_filename = f"{uuid.uuid4().hex}.{ext}"
                os.makedirs(current_app.config["UPLOAD_FOLDER"], exist_ok=True)
                image_file.save(os.path.join(current_app.config["UPLOAD_FOLDER"], image_filename))
            else:
                errors.append("Image must be a png, jpg, jpeg, gif, or webp file.")

        if errors:
            for e in errors:
                flash(e, "danger")
            return render_template(
                "donor/create_donation.html",
                categories=FOOD_CATEGORIES, conditions=FOOD_CONDITIONS,
                units=QUANTITY_UNITS, areas=area_choices(), form=request.form,
            )

        lat, lng = resolve_area(area)

        donation = FoodDonation(
            donor_id=current_user.id,
            food_name=food_name,
            category=category,
            description=description,
            quantity=quantity,
            quantity_unit=quantity_unit,
            meal_count=meal_count,
            food_condition=food_condition,
            pickup_location=pickup_location,
            area=area,
            latitude=lat,
            longitude=lng,
            available_until=available_until,
            image_filename=image_filename,
            status=STATUS_AVAILABLE,
        )

        # --- Smart Rescue Matching ---------------------------------------
        donation.priority = matching.compute_donation_priority(donation)

        recipients = User.query.filter_by(role=ROLE_RECIPIENT, is_active_account=True).all()
        if recipients:
            best_matches = matching.find_best_matches(donation, recipients, top_n=5)
            if best_matches:
                top = best_matches[0]
                donation.best_match_recipient_id = top["recipient"].id
                donation.best_match_score = top["score"]
                donation.best_match_reason = top["reason"]

        db.session.add(donation)
        db.session.commit()

        flash("Donation created! Smart Rescue Matching found recommended recipients.", "success")
        return redirect(url_for("donor.donation_details", donation_id=donation.id))

    return render_template(
        "donor/create_donation.html",
        categories=FOOD_CATEGORIES, conditions=FOOD_CONDITIONS,
        units=QUANTITY_UNITS, areas=area_choices(), form={},
    )


@donor_bp.route("/donations")
@login_required
@role_required(ROLE_DONOR)
def my_donations():
    status_filter = request.args.get("status", "").strip()
    query = current_user.donations
    donations = query.order_by(FoodDonation.created_at.desc()).all()
    _sync_expired(donations)

    if status_filter:
        donations = [d for d in donations if d.status == status_filter]

    return render_template("donor/my_donations.html", donations=donations, status_filter=status_filter)


@donor_bp.route("/donations/<int:donation_id>")
@login_required
@role_required(ROLE_DONOR)
def donation_details(donation_id):
    donation = FoodDonation.query.get_or_404(donation_id)
    if donation.donor_id != current_user.id:
        abort(403)

    if donation.status == STATUS_AVAILABLE and donation.is_expired:
        donation.status = STATUS_EXPIRED
        db.session.commit()

    recommendations = []
    if donation.status == STATUS_AVAILABLE:
        recipients = User.query.filter_by(role=ROLE_RECIPIENT, is_active_account=True).all()
        recommendations = matching.find_best_matches(donation, recipients, top_n=5)

    return render_template(
        "donor/donation_details.html",
        donation=donation,
        recommendations=recommendations,
    )


@donor_bp.route("/donations/<int:donation_id>/cancel", methods=["POST"])
@login_required
@role_required(ROLE_DONOR)
def cancel_donation(donation_id):
    donation = FoodDonation.query.get_or_404(donation_id)
    if donation.donor_id != current_user.id:
        abort(403)
    if donation.status == STATUS_AVAILABLE:
        donation.status = STATUS_CANCELLED
        db.session.commit()
        flash("Donation cancelled.", "info")
    else:
        flash("Only available donations can be cancelled.", "warning")
    return redirect(url_for("donor.donation_details", donation_id=donation.id))


@donor_bp.route("/impact")
@login_required
@role_required(ROLE_DONOR)
def impact():
    records = ImpactRecord.query.filter_by(donor_id=current_user.id).order_by(ImpactRecord.created_at).all()

    total_meals = sum(r.meals_rescued for r in records)
    total_weight = round(sum(r.food_weight_kg for r in records), 1)
    total_co2e = round(sum(r.co2e_avoided_kg for r in records), 1)
    total_connections = len(records)

    chart_labels = [r.created_at.strftime("%d %b") for r in records][-10:]
    chart_meals = [r.meals_rescued for r in records][-10:]

    return render_template(
        "donor/impact.html",
        total_meals=total_meals,
        total_weight=total_weight,
        total_co2e=total_co2e,
        total_connections=total_connections,
        chart_labels=chart_labels,
        chart_meals=chart_meals,
        records=records[::-1][:10],
    )
