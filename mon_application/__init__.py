# mon_application/__init__.py
"""
Ce module est le cœur de l'application (paquet).

Il contient la factory `create_app`, qui est responsable de l'initialisation
et de la configuration de l'instance Flask, de la base de données, du gestionnaire
de connexion, des commandes CLI et de l'enregistrement des "Blueprints".
Il gère également la détermination de l'année scolaire active pour chaque requête.
"""

import datetime
import os
from typing import Any, cast

from flask import Flask, flash, g, jsonify, redirect, request, session, url_for
from flask_login import LoginManager, current_user
from werkzeug.wrappers import Response

from .models import User


def determine_active_school_year(
    toutes_les_annees: list[dict[str, Any]], has_dashboard_access: bool, annee_id_session: int | None
) -> dict[str, Any] | None:
    """
    Détermine l'année scolaire active en fonction du contexte utilisateur et de la session.

    Args:
        toutes_les_annees: La liste de toutes les années scolaires disponibles.
        has_dashboard_access: Booléen indiquant si l'utilisateur a accès au tableau de bord.
        annee_id_session: L'ID de l'année stocké dans la session, ou None.

    Returns:
        Le dictionnaire de l'année active, ou None si aucune année n'existe.
    """
    from . import database as db

    annee_active: dict[str, Any] | None = None

    if has_dashboard_access and annee_id_session:
        annee_active = next((annee for annee in toutes_les_annees if annee["annee_id"] == annee_id_session), None)

    if not annee_active:
        annee_active = db.get_annee_courante()

    if not annee_active and toutes_les_annees:
        annee_active = max(toutes_les_annees, key=lambda x: x["libelle_annee"])
        if has_dashboard_access:
            flash(
                "Aucune année scolaire n'est définie comme 'courante'. Affichage de la plus récente par défaut.",
                "warning",
            )

    return annee_active


def create_app(test_config: dict[str, Any] | None = None) -> Flask:
    """
    Crée et configure une instance de l'application Flask (Application Factory).

    Args:
        test_config: Configuration à utiliser pour les tests. Defaults to None.

    Returns:
        L'instance de l'application Flask configurée.
    """
    app = Flask(__name__, instance_relative_config=False)

    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY", os.urandom(24)),
        UPLOAD_FOLDER=os.path.join(app.root_path, "uploads"),
        ALLOWED_EXTENSIONS={"xlsx"},
    )

    if test_config:
        app.config.from_mapping(test_config)

    try:
        os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    except OSError as e:
        app.logger.error(f"Erreur lors de la création du dossier d'upload: {e}")

    # --- Initialisation des extensions et services ---
    from . import database

    database.init_app(app)

    login_manager = LoginManager()
    login_manager.init_app(app)
    # pyright: ignore [reportAttributeAccessIssue]
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Veuillez vous connecter pour accéder à cette page."
    login_manager.login_message_category = "info"

    @login_manager.unauthorized_handler
    def unauthorized_callback() -> tuple[Response, int] | Response:
        """
        Gère les accès non authentifiés.
        Renvoie du JSON pour les requêtes API et redirige pour les autres.
        """
        if request.path.startswith(("/api/", "/admin/api/")):
            return jsonify({"success": False, "message": "Authentification requise."}), 401
        flash("Veuillez vous connecter pour accéder à cette page.", "info")
        return redirect(url_for("auth.login"))

    @login_manager.user_loader
    def load_user(user_id: str) -> User | None:
        """Fonction pour recharger l'objet utilisateur à partir de l'ID stocké en session."""
        from .database import get_user_obj_by_id

        return get_user_obj_by_id(int(user_id))

    @app.before_request
    def load_active_school_year() -> None:
        """
        Détermine l'année scolaire active pour la requête et la stocke dans `g`.
        """
        from . import database as db

        g.toutes_les_annees = db.get_all_annees()
        has_dashboard_access = current_user.is_authenticated and (current_user.is_admin or current_user.is_dashboard_only)
        annee_id_session = session.get("annee_scolaire_id")

        g.annee_active = determine_active_school_year(
            cast(list[dict[str, Any]], g.toutes_les_annees),
            has_dashboard_access,
            annee_id_session,
        )

    # --- Filtres Jinja2 et Context Processors ---
    def format_periodes_filter(value: float | None) -> str:
        """Filtre Jinja pour formater joliment les nombres de périodes."""
        if value is None:
            return ""
        return f"{float(value):g}"

    app.jinja_env.filters["format_periodes"] = format_periodes_filter

    @app.context_processor
    def inject_global_data() -> dict[str, Any]:
        """Rend des variables globales disponibles dans tous les templates."""
        return {
            "current_user": current_user,
            "SCRIPT_YEAR": datetime.datetime.now().year,
            "annee_active": getattr(g, "annee_active", None),
            "toutes_les_annees": getattr(g, "toutes_les_annees", []),
        }

    # --- Enregistrement des Blueprints ---
    from . import admin, api, auth, dashboard, views

    app.register_blueprint(auth.bp)
    app.register_blueprint(views.bp)
    app.add_url_rule("/", endpoint="index")
    app.register_blueprint(admin.bp)
    app.register_blueprint(dashboard.bp)
    app.register_blueprint(api.bp)

    # --- Enregistrement des commandes CLI ---
    from . import commands

    commands.init_app(app)

    return app