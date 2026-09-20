"""Admin routes: platform dashboard, user verification, donations, claims."""

from flask import Blueprint, render_template, redirect, url_for, request, flash, abort
from flask_login import login_required, current_user
from sqlalchemy import func

from models import (
    db, User, FoodDonation, DonationClaim, ImpactRecord,
    ROLE_ADMIN, ROLE_DONOR, ROLE_RECIPIENT,
    STATUS_AVAILABLE, STATUS_CLAIMED, STATUS_PICKED_UP, STATUS_EXPIRED, STATUS_CANCELLED,
)
from decorators import role_required

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


@admin_bp.route("/dashboard")
@login_required
@role_required(ROLE_ADMIN)
def dashboard():
    total_users = User.query.count()
    total_donors = User.query.filter_by(role=ROLE_DONOR).count()
    total_recipients = User.query.filter_by(role=ROLE_RECIPIENT).count()
    pending_verifications = User.query.filter(
        User.role.in_([ROLE_DONOR, ROLE_RECIPIENT]), User.is_verified.is_(False)
    ).count()

    total_donations = FoodDonation.query.count()
    active_donations = FoodDonation.query.filter_by(status=STATUS_AVAILABLE).count()
    claimed_donations = FoodDonation.query.filter_by(status=STATUS_CLAIMED).count()
    picked_up_donations = FoodDonation.query.filter_by(status=STATUS_PICKED_UP).count()
    expired_donations = FoodDonation.query.filter_by(status=STATUS_EXPIRED).count()

    impact_agg = db.session.query(
        func.coalesce(func.sum(ImpactRecord.meals_rescued), 0),
        func.coalesce(func.sum(ImpactRecord.food_weight_kg), 0),
        func.coalesce(func.sum(ImpactRecord.co2e_avoided_kg), 0),
    ).first()

    recent_donations = FoodDonation.query.order_by(FoodDonation.created_at.desc()).limit(6).all()
    recent_users = User.query.order_by(User.created_at.desc()).limit(6).all()

    return render_template(
        "admin/dashboard.html",
        total_users=total_users,
        total_donors=total_donors,
        total_recipients=total_recipients,
        pending_verifications=pending_verifications,
        total_donations=total_donations,
        active_donations=active_donations,
        claimed_donations=claimed_donations,
        picked_up_donations=picked_up_donations,
        expired_donations=expired_donations,
        total_meals=int(impact_agg[0] or 0),
        total_weight=round(impact_agg[1] or 0, 1),
        total_co2e=round(impact_agg[2] or 0, 1),
        recent_donations=recent_donations,
        recent_users=recent_users,
    )


@admin_bp.route("/users")
@login_required
@role_required(ROLE_ADMIN)
def users():
    role_filter = request.args.get("role", "").strip()
    verified_filter = request.args.get("verified", "").strip()

    query = User.query.filter(User.role.in_([ROLE_DONOR, ROLE_RECIPIENT, ROLE_ADMIN]))
    if role_filter:
        query = query.filter_by(role=role_filter)
    if verified_filter == "yes":
        query = query.filter_by(is_verified=True)
    elif verified_filter == "no":
        query = query.filter_by(is_verified=False)

    all_users = query.order_by(User.created_at.desc()).all()
    return render_template(
        "admin/users.html", users=all_users, role_filter=role_filter, verified_filter=verified_filter
    )


@admin_bp.route("/users/<int:user_id>/verify", methods=["POST"])
@login_required
@role_required(ROLE_ADMIN)
def verify_user(user_id):
    user = User.query.get_or_404(user_id)
    user.is_verified = True
    db.session.commit()
    flash(f"{user.name} ({user.organization_name}) has been verified.", "success")
    return redirect(url_for("admin.users"))


@admin_bp.route("/users/<int:user_id>/toggle-active", methods=["POST"])
@login_required
@role_required(ROLE_ADMIN)
def toggle_active(user_id):
    user = User.query.get_or_404(user_id)
    if user.role == ROLE_ADMIN:
        flash("Admin accounts cannot be deactivated.", "warning")
        return redirect(url_for("admin.users"))
    user.is_active_account = not user.is_active_account
    db.session.commit()
    state = "activated" if user.is_active_account else "deactivated"
    flash(f"{user.name} has been {state}.", "info")
    return redirect(url_for("admin.users"))


@admin_bp.route("/donations")
@login_required
@role_required(ROLE_ADMIN)
def donations():
    status_filter = request.args.get("status", "").strip()
    query = FoodDonation.query
    if status_filter:
        query = query.filter_by(status=status_filter)
    all_donations = query.order_by(FoodDonation.created_at.desc()).all()
    return render_template("admin/donations.html", donations=all_donations, status_filter=status_filter)


@admin_bp.route("/donations/<int:donation_id>/remove", methods=["POST"])
@login_required
@role_required(ROLE_ADMIN)
def remove_donation(donation_id):
    donation = FoodDonation.query.get_or_404(donation_id)
    if donation.status == STATUS_AVAILABLE:
        donation.status = STATUS_CANCELLED
        db.session.commit()
        flash("Donation removed from the platform.", "info")
    else:
        flash("Only available donations can be removed.", "warning")
    return redirect(url_for("admin.donations"))


@admin_bp.route("/claims")
@login_required
@role_required(ROLE_ADMIN)
def claims():
    status_filter = request.args.get("status", "").strip()
    query = DonationClaim.query
    if status_filter:
        query = query.filter_by(status=status_filter)
    all_claims = query.order_by(DonationClaim.claimed_at.desc()).all()
    return render_template("admin/claims.html", claims=all_claims, status_filter=status_filter)
