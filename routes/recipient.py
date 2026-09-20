"""Recipient routes: dashboard, discover food, claim, pickup confirmation, impact."""

from datetime import datetime

from flask import Blueprint, render_template, redirect, url_for, request, flash, abort
from flask_login import login_required, current_user
from sqlalchemy import func

from models import (
    db, FoodDonation, User, DonationClaim, ImpactRecord, Notification,
    ROLE_RECIPIENT, STATUS_AVAILABLE, STATUS_CLAIMED, STATUS_PICKED_UP, STATUS_EXPIRED,
    generate_pickup_code,
)
from decorators import role_required
from services import matching
from services.impact import build_impact_numbers

recipient_bp = Blueprint("recipient", __name__, url_prefix="/recipient")


def _sync_expired(donations):
    changed = False
    for d in donations:
        if d.status == STATUS_AVAILABLE and d.is_expired:
            d.status = STATUS_EXPIRED
            changed = True
    if changed:
        db.session.commit()


@recipient_bp.route("/dashboard")
@login_required
@role_required(ROLE_RECIPIENT)
def dashboard():
    claims = current_user.claims.order_by(DonationClaim.claimed_at.desc()).all()
    active_claims = [c for c in claims if c.status == STATUS_CLAIMED]
    completed_claims = [c for c in claims if c.status == STATUS_PICKED_UP]

    impact_agg = db.session.query(
        func.coalesce(func.sum(ImpactRecord.meals_rescued), 0),
        func.coalesce(func.sum(ImpactRecord.food_weight_kg), 0),
    ).filter(ImpactRecord.recipient_id == current_user.id).first()

    meals_received = int(impact_agg[0] or 0)
    food_received_kg = round(impact_agg[1] or 0, 1)

    # Top nearby available donations, ranked by match score, as a quick preview
    available = FoodDonation.query.filter_by(status=STATUS_AVAILABLE).all()
    _sync_expired(available)
    available = [d for d in available if d.status == STATUS_AVAILABLE]
    scored = []
    for d in available:
        result = matching.score_recipient_for_donation(d, current_user)
        result["donation"] = d
        scored.append(result)
    scored.sort(key=lambda r: r["score"], reverse=True)
    top_matches = scored[:5]

    return render_template(
        "recipient/dashboard.html",
        active_claims_count=len(active_claims),
        completed_claims_count=len(completed_claims),
        meals_received=meals_received,
        food_received_kg=food_received_kg,
        top_matches=top_matches,
    )


@recipient_bp.route("/find-food")
@login_required
@role_required(ROLE_RECIPIENT)
def find_food():
    donations = FoodDonation.query.filter_by(status=STATUS_AVAILABLE).all()
    _sync_expired(donations)
    donations = [d for d in donations if d.status == STATUS_AVAILABLE]

    scored = []
    for d in donations:
        result = matching.score_recipient_for_donation(d, current_user)
        result["donation"] = d
        scored.append(result)

    # --- Filters ---
    category = request.args.get("category", "").strip()
    priority = request.args.get("priority", "").strip()
    max_distance = request.args.get("max_distance", "").strip()
    min_meals = request.args.get("min_meals", "").strip()
    sort_by = request.args.get("sort", "match")

    if category:
        scored = [r for r in scored if r["donation"].category == category]
    if priority:
        scored = [r for r in scored if r["priority"] == priority]
    if max_distance:
        try:
            max_d = float(max_distance)
            scored = [r for r in scored if r["distance_km"] <= max_d]
        except ValueError:
            pass
    if min_meals:
        try:
            m = int(min_meals)
            scored = [r for r in scored if r["donation"].meal_count >= m]
        except ValueError:
            pass

    if sort_by == "nearest":
        scored.sort(key=lambda r: r["distance_km"])
    elif sort_by == "urgent":
        scored.sort(key=lambda r: r["donation"].available_until)
    else:  # "match" (default): highest match score first
        scored.sort(key=lambda r: r["score"], reverse=True)

    categories = sorted({d.category for d in donations}) or [
        "Cooked Meals", "Bakery", "Produce", "Packaged Food", "Dairy", "Beverages", "Other"
    ]

    return render_template(
        "recipient/find_food.html",
        results=scored,
        categories=categories,
        selected_category=category,
        selected_priority=priority,
        max_distance=max_distance,
        min_meals=min_meals,
        sort_by=sort_by,
    )


@recipient_bp.route("/donations/<int:donation_id>")
@login_required
@role_required(ROLE_RECIPIENT)
def donation_details(donation_id):
    donation = FoodDonation.query.get_or_404(donation_id)
    if donation.status == STATUS_AVAILABLE and donation.is_expired:
        donation.status = STATUS_EXPIRED
        db.session.commit()

    match = matching.score_recipient_for_donation(donation, current_user)
    my_claim = DonationClaim.query.filter_by(
        donation_id=donation.id, recipient_id=current_user.id
    ).first()

    return render_template(
        "recipient/donation_details.html",
        donation=donation,
        match=match,
        my_claim=my_claim,
    )


@recipient_bp.route("/donations/<int:donation_id>/claim", methods=["POST"])
@login_required
@role_required(ROLE_RECIPIENT)
def claim_donation(donation_id):
    donation = FoodDonation.query.get_or_404(donation_id)

    if donation.status != STATUS_AVAILABLE or donation.is_expired:
        flash("This donation is no longer available.", "warning")
        return redirect(url_for("recipient.find_food"))

    match = matching.score_recipient_for_donation(donation, current_user)

    claim = DonationClaim(
        donation_id=donation.id,
        recipient_id=current_user.id,
        pickup_code=generate_pickup_code(),
        match_score=match["score"],
        distance_km=match["distance_km"],
        status=STATUS_CLAIMED,
    )
    donation.status = STATUS_CLAIMED
    db.session.add(claim)

    notice = Notification(
        user_id=donation.donor_id,
        message=f"{current_user.organization_name} claimed your donation '{donation.food_name}'.",
        link=url_for("donor.donation_details", donation_id=donation.id),
    )
    db.session.add(notice)

    db.session.commit()

    flash("Donation claimed successfully! Here's your pickup code.", "success")
    return redirect(url_for("recipient.claim_confirmation", claim_id=claim.id))


@recipient_bp.route("/claims/<int:claim_id>")
@login_required
@role_required(ROLE_RECIPIENT)
def claim_confirmation(claim_id):
    claim = DonationClaim.query.get_or_404(claim_id)
    if claim.recipient_id != current_user.id:
        abort(403)
    return render_template("recipient/claim_confirmation.html", claim=claim, donation=claim.donation)


@recipient_bp.route("/claims/<int:claim_id>/confirm-pickup", methods=["POST"])
@login_required
@role_required(ROLE_RECIPIENT)
def confirm_pickup(claim_id):
    claim = DonationClaim.query.get_or_404(claim_id)
    if claim.recipient_id != current_user.id:
        abort(403)

    if claim.status != STATUS_CLAIMED:
        flash("This pickup has already been processed.", "info")
        return redirect(url_for("recipient.my_claims"))

    donation = claim.donation
    claim.status = STATUS_PICKED_UP
    claim.picked_up_at = datetime.utcnow()
    donation.status = STATUS_PICKED_UP

    impact_numbers = build_impact_numbers(donation.meal_count, donation.quantity, donation.quantity_unit)
    impact_record = ImpactRecord(
        donation_id=donation.id,
        donor_id=donation.donor_id,
        recipient_id=current_user.id,
        meals_rescued=impact_numbers["meals"],
        food_weight_kg=impact_numbers["weight_kg"],
        co2e_avoided_kg=impact_numbers["co2e_kg"],
    )
    db.session.add(impact_record)

    notice = Notification(
        user_id=donation.donor_id,
        message=f"Pickup confirmed for '{donation.food_name}' by {current_user.organization_name}. 🎉",
        link=url_for("donor.donation_details", donation_id=donation.id),
    )
    db.session.add(notice)

    db.session.commit()

    flash("Pickup confirmed! Thank you for rescuing this food. 🎉", "success")
    return redirect(url_for("recipient.my_claims"))


@recipient_bp.route("/my-claims")
@login_required
@role_required(ROLE_RECIPIENT)
def my_claims():
    status_filter = request.args.get("status", "").strip()
    claims = current_user.claims.order_by(DonationClaim.claimed_at.desc()).all()
    if status_filter:
        claims = [c for c in claims if c.status == status_filter]
    return render_template("recipient/my_claims.html", claims=claims, status_filter=status_filter)


@recipient_bp.route("/impact")
@login_required
@role_required(ROLE_RECIPIENT)
def impact():
    records = ImpactRecord.query.filter_by(recipient_id=current_user.id).order_by(ImpactRecord.created_at).all()

    total_meals = sum(r.meals_rescued for r in records)
    total_weight = round(sum(r.food_weight_kg for r in records), 1)
    total_co2e = round(sum(r.co2e_avoided_kg for r in records), 1)
    total_connections = len(records)

    chart_labels = [r.created_at.strftime("%d %b") for r in records][-10:]
    chart_meals = [r.meals_rescued for r in records][-10:]

    return render_template(
        "recipient/impact.html",
        total_meals=total_meals,
        total_weight=total_weight,
        total_co2e=total_co2e,
        total_connections=total_connections,
        chart_labels=chart_labels,
        chart_meals=chart_meals,
        records=records[::-1][:10],
    )
