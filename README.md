# 🍃 FoodLoop

**"Don't let good food become waste."**

FoodLoop reduces surplus food waste by connecting **food donors** (restaurants, college canteens, hostels, caterers, events) with **verified recipients** (NGOs, shelters, community kitchens) before the food expires — using a built-in **Smart Rescue Matching** engine.

Built for **HACKDAY 1.0 — "Tech for a Better Tomorrow"**.

---

## ✨ Core Flow

```
Donor Login → Create Food Donation → Smart Rescue Matching → Recommended Recipient
Recipient Login → Discover Food → View Donation → Claim → Receive Pickup Code → Confirm Pickup
System → Donation becomes PICKED_UP → Impact record created → Dashboards update
```

## 🧠 Smart Rescue Matching (Core Innovation)

Every donation gets a **Match Score (0–100)**, computed with a transparent, rule-based algorithm — **no external AI / paid APIs required**:

| Factor | Weight |
|---|---|
| ⏱ Urgency / time remaining | 40% |
| 📍 Distance | 30% |
| ⚖️ Quantity compatibility | 20% |
| ✅ Recipient suitability / verification | 10% |

The result is shown as:

```
93% Match
🔥 HIGH PRIORITY
1.8 km away
Enough capacity
Only 1h 20m remaining
```

See `services/matching.py` for the full implementation (haversine distance + weighted scoring), and `services/impact.py` for the (clearly labeled, estimated) environmental impact math.

---

## 🛠 Tech Stack

- **Backend:** Python, Flask, Flask-SQLAlchemy, Flask-Login, Werkzeug password hashing
- **Frontend:** HTML, CSS, vanilla JavaScript, Bootstrap 5 + Bootstrap Icons
- **Database:** MySQL (production) with automatic **SQLite fallback** for local dev
- **Config:** `.env` file — no secrets hard-coded

---

## 📁 Project Structure

```
FoodLoop/
├── app.py                 # Flask app factory / entry point
├── config.py               # Env-based config (MySQL / SQLite fallback)
├── models.py                # SQLAlchemy models
├── seed.py                  # Demo accounts + realistic seed data
├── decorators.py            # Role-based access control
├── requirements.txt
├── README.md
├── .env.example
├── .gitignore
├── routes/
│   ├── main.py               # Landing page
│   ├── auth.py                # Register / Login / Logout
│   ├── donor.py                # Donor dashboard, create/manage donations, impact
│   ├── recipient.py            # Discover food, claim, pickup, impact
│   └── admin.py                 # Users, donations, claims, stats
├── services/
│   ├── matching.py            # Smart Rescue Matching algorithm
│   ├── impact.py               # Meals → kg → CO2e estimation
│   └── locations.py            # Sample Bengaluru locality coordinates
├── templates/                 # Jinja2 templates (donor/recipient/admin/auth)
├── static/
│   ├── css/style.css           # Eco-tech design system
│   ├── js/app.js                # Countdown timers, filters, confirmations
│   └── uploads/                  # Donation photos
└── database/                  # SQLite file lives here (dev fallback)
```

---

## 🚀 Getting Started

### 1. Clone & install dependencies

```bash
cd FoodLoop
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# edit .env and set a real SECRET_KEY
# leave DATABASE_URL empty to use the bundled SQLite fallback,
# or point it at MySQL, e.g.:
# DATABASE_URL=mysql+pymysql://root:password@localhost:3306/foodloop
```

### 3. Seed the database (creates tables + demo data)

```bash
python seed.py
```

### 4. Run the app

```bash
python app.py
```

Visit **http://localhost:5000**

---

## 🔑 Demo Accounts

| Role | Email | Password |
|---|---|---|
| Admin | `admin@foodloop.demo` | `Admin@123` |
| Donor | `donor@foodloop.demo` | `Donor@123` |
| Recipient | `recipient@foodloop.demo` | `Recipient@123` |

---

## 👥 Roles & Permissions

**Donor** — register/login, create donations, view donations, view recommended recipients, track rescued food, view impact.

**Recipient** — register/login, browse available food, filter/sort, view rescue priority & match score, claim donation, confirm pickup, view impact.

**Admin** — view users, verify users, view/manage donations, view claims, view platform statistics.

Role-based access is enforced server-side via the `@role_required(...)` decorator on every protected route.

---

## 🗄 Database Models

- **User** — donors, recipients & admins (role column), verification status, location
- **FoodDonation** — a surplus food listing, with computed priority + best match
- **DonationClaim** — a recipient's claim, pickup code, status
- **ImpactRecord** — created on confirmed pickup (meals, weight, CO₂e)
- **Notification** — simple in-app notifications

## 📝 Notes

- Distances are computed with the haversine formula between the donor's and recipient's chosen "Area" (a small set of real Bengaluru localities is bundled in `services/locations.py`) — no paid geocoding API required.
- Environmental impact numbers (food weight, CO₂e avoided) are clearly labeled **estimates**, based on standard averages (`services/impact.py`).
- This is a hackathon MVP and is not affiliated with any real food-rescue organization.
