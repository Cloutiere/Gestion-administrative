# mon_application/__init__.py
"""
Ce module est le cœur de l'application (paquet).
Il contient la factory de l'application `create_app`.
"""

import datetime
import os
from typing import Any

from flask import Flask, flash, g, jsonify, redirect, request, session, url_for
from flask_login import LoginManager, current_user
from werkzeug.wrappers import Response

from .extensions import db, migrate
from .models import User
from .services import (
    determine_active_school_year_service,
    get_all_annees_service,
)


def load_active_school_year() -> None:
    """
    Charge l'année scolaire active pour la requête en cours en utilisant les services ORM.
    """
    if not current_user.is_authenticated:
        g.toutes_les_annees = []
        g.annee_active = None
        return

    try:
        toutes_les_annees = get_all_annees_service()
        g.toutes_les_annees = toutes_les_annees

        has_dashboard_access = current_user.is_admin or current_user.is_dashboard_only
        annee_id_session = session.get("annee_scolaire_id")

        annee_active, warning_message = determine_active_school_year_service(toutes_les_annees, has_dashboard_access, annee_id_session)
        g.annee_active = annee_active

        if warning_message:
            flash(warning_message, "warning")

    except Exception as e:
        # Utiliser get_current_object() pour obtenir l'instance de l'app dans ce contexte
        from flask import current_app

        current_app.logger.error(f"Impossible de charger les années scolaires : {e}")
        g.toutes_les_annees = []
        g.annee_active = None
        flash("Erreur critique: Impossible de charger les données des années scolaires.", "danger")


def get_database_uri() -> str:
    """Construit l'URI de la base de données pour SQLAlchemy en se basant sur FLASK_ENV."""
    flask_env = os.environ.get("FLASK_ENV", "production")
    prefix = {"development": "DEV_", "test": "TEST_"}.get(flask_env, "PROD_")

    db_host = os.environ.get(f"{prefix}PGHOST")
    db_name = os.environ.get(f"{prefix}PGDATABASE")
    db_user = os.environ.get(f"{prefix}PGUSER")
    db_pass = os.environ.get(f"{prefix}PGPASSWORD")
    db_port = os.environ.get(f"{prefix}PGPORT", "5432")

    if not all([db_host, db_name, db_user, db_pass]):
        raise ValueError(f"Variables de BDD manquantes pour l'environnement '{flask_env}' (préfixe '{prefix}')")

    return f"postgresql+psycopg2://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}"


def create_app(test_config: dict[str, Any] | None = None) -> Flask:
    """Crée et configure une instance de l'application Flask (Application Factory)."""
    app = Flask(__name__, instance_relative_config=True)

    upload_folder = os.path.join(app.instance_path, "uploads")

    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev"),
        UPLOAD_FOLDER=upload_folder,
        ALLOWED_EXTENSIONS={"xlsx"},
        SQLALCHEMY_DATABASE_URI=get_database_uri(),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
    )

    if test_config:
        app.config.from_mapping(test_config)

    try:
        os.makedirs(app.instance_path, exist_ok=True)
        os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    except OSError as e:
        app.logger.error(f"Erreur lors de la création des dossiers d'instance/upload: {e}")

    db.init_app(app)
    migrate.init_app(app, db)

    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Veuillez vous connecter pour accéder à cette page."
    login_manager.login_message_category = "info"

    @login_manager.unauthorized_handler
    def unauthorized_callback() -> tuple[Response, int] | Response:
        if request.path.startswith(("/api/", "/admin/api/")):
            return jsonify({"success": False, "message": "Authentification requise."}), 401
        flash("Veuillez vous connecter pour accéder à cette page.", "info")
        return redirect(url_for("auth.login"))

    @login_manager.user_loader
    def load_user(user_id: str) -> User | None:
        return db.session.get(User, int(user_id))

    app.before_request(load_active_school_year)

    @app.context_processor
    def inject_global_data() -> dict[str, Any]:
        return {
            "current_user": current_user,
            "SCRIPT_YEAR": datetime.datetime.now().year,
            "annee_active": getattr(g, "annee_active", None),
            "toutes_les_annees": getattr(g, "toutes_les_annees", []),
        }

    from . import admin, api, auth, dashboard, views

    app.register_blueprint(auth.bp)
    app.register_blueprint(views.bp)
    app.add_url_rule("/", endpoint="index")
    app.register_blueprint(admin.bp)
    app.register_blueprint(dashboard.bp)
    app.register_blueprint(api.bp)

    from . import commands

    commands.init_app(app)

    return app
