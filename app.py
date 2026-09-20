"""
FoodLoop — "Don't let good food become waste."

Main Flask application factory / entry point.
"""

import os
from datetime import datetime

from flask import Flask, render_template
from flask_login import LoginManager, current_user

from config import Config
from models import db, User, Notification


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # --- Extensions ---------------------------------------------------------
    db.init_app(app)

    login_manager = LoginManager()
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Please log in to access that page."
    login_manager.login_message_category = "info"
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    # --- Blueprints ----------------------------------------------------------
    from routes.main import main_bp
    from routes.auth import auth_bp
    from routes.donor import donor_bp
    from routes.recipient import recipient_bp
    from routes.admin import admin_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(donor_bp)
    app.register_blueprint(recipient_bp)
    app.register_blueprint(admin_bp)

    # --- Template context ------------------------------------------------
    @app.context_processor
    def inject_globals():
        unread_count = 0
        if current_user.is_authenticated:
            unread_count = Notification.query.filter_by(
                user_id=current_user.id, is_read=False
            ).count()
        return {"current_year": datetime.utcnow().year, "unread_notifications": unread_count}

    # --- Error handlers ----------------------------------------------------
    @app.errorhandler(403)
    def forbidden(e):
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def not_found(e):
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def server_error(e):
        return render_template("errors/500.html"), 500

    # --- Ensure folders exist ------------------------------------------------
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    os.makedirs(os.path.join(os.path.dirname(__file__), "database"), exist_ok=True)

    # --- CLI helper: `flask create-db` --------------------------------------
    @app.cli.command("create-db")
    def create_db():
        """Create all database tables."""
        with app.app_context():
            db.create_all()
        print("Database tables created.")

    return app


app = create_app()

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(host="0.0.0.0", port=5000, debug=app.config.get("DEBUG", True))
