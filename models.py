"""
FoodLoop database models.

Models:
- User            : donors, recipients and admins (single table, role column)
- FoodDonation    : a surplus food listing created by a donor
- DonationClaim   : a recipient's claim on a donation (pickup code, status)
- ImpactRecord    : created once a donation is successfully picked up
- Notification    : simple in-app notifications for users
"""

from datetime import datetime, timedelta
import random
import string

from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def generate_pickup_code():
    """Generate a unique-ish 6 digit pickup code."""
    return "".join(random.choices(string.digits, k=6))


ROLE_DONOR = "donor"
ROLE_RECIPIENT = "recipient"
ROLE_ADMIN = "admin"

STATUS_AVAILABLE = "AVAILABLE"
STATUS_CLAIMED = "CLAIMED"
STATUS_PICKED_UP = "PICKED_UP"
STATUS_EXPIRED = "EXPIRED"
STATUS_CANCELLED = "CANCELLED"

PRIORITY_LOW = "Low"
PRIORITY_MEDIUM = "Medium"
PRIORITY_HIGH = "High"
PRIORITY_CRITICAL = "Critical"


# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------

class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    role = db.Column(db.String(20), nullable=False, default=ROLE_DONOR)  # donor / recipient / admin

    name = db.Column(db.String(120), nullable=False)
    organization_name = db.Column(db.String(150), nullable=True)
    email = db.Column(db.String(150), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    phone = db.Column(db.String(20), nullable=True)

    address = db.Column(db.String(250), nullable=True)
    area = db.Column(db.String(100), nullable=True, default="Koramangala")
    latitude = db.Column(db.Float, nullable=True, default=12.9716)   # default: Bengaluru
    longitude = db.Column(db.Float, nullable=True, default=77.5946)

    # Recipient-specific
    recipient_type = db.Column(db.String(50), nullable=True)  # NGO / Shelter / Community Kitchen
    daily_meal_capacity = db.Column(db.Integer, nullable=True, default=50)

    is_verified = db.Column(db.Boolean, default=False, nullable=False)
    is_active_account = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    donations = db.relationship(
        "FoodDonation", backref="donor", lazy="dynamic",
        foreign_keys="FoodDonation.donor_id"
    )
    claims = db.relationship(
        "DonationClaim", backref="recipient", lazy="dynamic",
        foreign_keys="DonationClaim.recipient_id"
    )
    notifications = db.relationship(
        "Notification", backref="user", lazy="dynamic",
        cascade="all, delete-orphan"
    )

    # -- password helpers ---------------------------------------------------
    def set_password(self, raw_password):
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password):
        return check_password_hash(self.password_hash, raw_password)

    # -- convenience ----------------------------------------------------------
    @property
    def is_donor(self):
        return self.role == ROLE_DONOR

    @property
    def is_recipient(self):
        return self.role == ROLE_RECIPIENT

    @property
    def is_admin(self):
        return self.role == ROLE_ADMIN

    def __repr__(self):
        return f"<User {self.email} ({self.role})>"


# ---------------------------------------------------------------------------
# FoodDonation
# ---------------------------------------------------------------------------

class FoodDonation(db.Model):
    __tablename__ = "food_donations"

    id = db.Column(db.Integer, primary_key=True)
    donor_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    food_name = db.Column(db.String(150), nullable=False)
    category = db.Column(db.String(50), nullable=False)  # Cooked Meals, Bakery, Produce, Packaged, Dairy, Other
    description = db.Column(db.Text, nullable=True)

    quantity = db.Column(db.Float, nullable=False)         # numeric quantity
    quantity_unit = db.Column(db.String(20), nullable=False, default="kg")  # kg / plates / packets / litres
    meal_count = db.Column(db.Integer, nullable=False, default=0)

    food_condition = db.Column(db.String(50), nullable=False, default="Fresh")  # Fresh / Good / Near Expiry

    pickup_location = db.Column(db.String(250), nullable=False)
    area = db.Column(db.String(100), nullable=True, default="Koramangala")
    latitude = db.Column(db.Float, nullable=True, default=12.9716)
    longitude = db.Column(db.Float, nullable=True, default=77.5946)

    image_filename = db.Column(db.String(255), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    available_until = db.Column(db.DateTime, nullable=False)

    status = db.Column(db.String(20), nullable=False, default=STATUS_AVAILABLE)

    # Smart Rescue Matching results (best match, computed at creation time)
    priority = db.Column(db.String(20), nullable=True)          # Low / Medium / High / Critical
    best_match_score = db.Column(db.Float, nullable=True)
    best_match_recipient_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    best_match_reason = db.Column(db.String(255), nullable=True)

    best_match_recipient = db.relationship("User", foreign_keys=[best_match_recipient_id])

    claim = db.relationship(
        "DonationClaim", backref="donation", uselist=False,
        foreign_keys="DonationClaim.donation_id", cascade="all, delete-orphan"
    )
    impact_record = db.relationship(
        "ImpactRecord", backref="donation", uselist=False,
        foreign_keys="ImpactRecord.donation_id", cascade="all, delete-orphan"
    )

    # -- computed helpers -----------------------------------------------------
    @property
    def time_remaining(self):
        """Returns a timedelta (can be negative if expired)."""
        return self.available_until - datetime.utcnow()

    @property
    def time_remaining_display(self):
        delta = self.time_remaining
        total_seconds = int(delta.total_seconds())
        if total_seconds <= 0:
            return "Expired"
        hours, remainder = divmod(total_seconds, 3600)
        minutes = remainder // 60
        if hours >= 24:
            days = hours // 24
            hours = hours % 24
            return f"{days}d {hours}h"
        if hours > 0:
            return f"{hours}h {minutes}m"
        return f"{minutes}m"

    @property
    def is_expired(self):
        return self.time_remaining.total_seconds() <= 0 and self.status == STATUS_AVAILABLE

    def __repr__(self):
        return f"<FoodDonation {self.food_name} ({self.status})>"


# ---------------------------------------------------------------------------
# DonationClaim
# ---------------------------------------------------------------------------

class DonationClaim(db.Model):
    __tablename__ = "donation_claims"

    id = db.Column(db.Integer, primary_key=True)
    donation_id = db.Column(db.Integer, db.ForeignKey("food_donations.id"), nullable=False)
    recipient_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    pickup_code = db.Column(db.String(6), nullable=False, default=generate_pickup_code)
    match_score = db.Column(db.Float, nullable=True)
    distance_km = db.Column(db.Float, nullable=True)

    status = db.Column(db.String(20), nullable=False, default=STATUS_CLAIMED)  # CLAIMED / PICKED_UP / CANCELLED

    claimed_at = db.Column(db.DateTime, default=datetime.utcnow)
    picked_up_at = db.Column(db.DateTime, nullable=True)

    def __repr__(self):
        return f"<DonationClaim donation={self.donation_id} recipient={self.recipient_id}>"


# ---------------------------------------------------------------------------
# ImpactRecord
# ---------------------------------------------------------------------------

class ImpactRecord(db.Model):
    __tablename__ = "impact_records"

    id = db.Column(db.Integer, primary_key=True)
    donation_id = db.Column(db.Integer, db.ForeignKey("food_donations.id"), nullable=False)
    donor_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    recipient_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    meals_rescued = db.Column(db.Integer, nullable=False, default=0)
    food_weight_kg = db.Column(db.Float, nullable=False, default=0)   # estimated weight saved
    co2e_avoided_kg = db.Column(db.Float, nullable=False, default=0)  # estimated CO2e avoided

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    donor = db.relationship("User", foreign_keys=[donor_id])
    recipient = db.relationship("User", foreign_keys=[recipient_id])

    def __repr__(self):
        return f"<ImpactRecord donation={self.donation_id} meals={self.meals_rescued}>"


# ---------------------------------------------------------------------------
# Notification
# ---------------------------------------------------------------------------

class Notification(db.Model):
    __tablename__ = "notifications"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    message = db.Column(db.String(255), nullable=False)
    link = db.Column(db.String(255), nullable=True)
    is_read = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Notification user={self.user_id} read={self.is_read}>"
