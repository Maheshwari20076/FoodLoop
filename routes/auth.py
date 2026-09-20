"""Authentication routes: register, login, logout."""

from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_user, logout_user, login_required, current_user

from models import db, User, ROLE_DONOR, ROLE_RECIPIENT, ROLE_ADMIN
from services.locations import area_choices, resolve_area

auth_bp = Blueprint("auth", __name__)


def _redirect_for_role(user):
    if user.role == ROLE_ADMIN:
        return redirect(url_for("admin.dashboard"))
    if user.role == ROLE_RECIPIENT:
        return redirect(url_for("recipient.dashboard"))
    return redirect(url_for("donor.dashboard"))


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return _redirect_for_role(current_user)

    if request.method == "POST":
        role = request.form.get("role", ROLE_DONOR)
        name = request.form.get("name", "").strip()
        organization_name = request.form.get("organization_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")
        phone = request.form.get("phone", "").strip()
        address = request.form.get("address", "").strip()
        area = request.form.get("area", "Koramangala")
        recipient_type = request.form.get("recipient_type", "").strip()
        daily_meal_capacity = request.form.get("daily_meal_capacity", "").strip()

        errors = []
        if role not in (ROLE_DONOR, ROLE_RECIPIENT):
            errors.append("Please choose a valid account type.")
        if not name:
            errors.append("Name is required.")
        if not organization_name:
            errors.append("Organization / establishment name is required.")
        if not email or "@" not in email:
            errors.append("A valid email is required.")
        if len(password) < 6:
            errors.append("Password must be at least 6 characters.")
        if password != confirm_password:
            errors.append("Passwords do not match.")
        if User.query.filter_by(email=email).first():
            errors.append("An account with this email already exists.")

        if role == ROLE_RECIPIENT and not recipient_type:
            errors.append("Please select your recipient organization type.")

        if errors:
            for e in errors:
                flash(e, "danger")
            return render_template(
                "auth/register.html",
                areas=area_choices(),
                form=request.form,
            )

        lat, lng = resolve_area(area)

        user = User(
            role=role,
            name=name,
            organization_name=organization_name,
            email=email,
            phone=phone,
            address=address,
            area=area,
            latitude=lat,
            longitude=lng,
            recipient_type=recipient_type if role == ROLE_RECIPIENT else None,
            daily_meal_capacity=int(daily_meal_capacity) if daily_meal_capacity.isdigit() else 50,
            is_verified=False,
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        flash("Account created! You can now log in.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/register.html", areas=area_choices(), form={})


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return _redirect_for_role(current_user)

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        remember = bool(request.form.get("remember"))

        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            if not user.is_active_account:
                flash("This account has been deactivated. Contact the FoodLoop admin.", "danger")
                return render_template("auth/login.html")
            login_user(user, remember=remember)
            flash(f"Welcome back, {user.name.split(' ')[0]}!", "success")
            return _redirect_for_role(user)
        flash("Invalid email or password.", "danger")

    return render_template("auth/login.html")


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("main.landing"))
