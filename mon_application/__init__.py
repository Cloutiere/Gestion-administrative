# mon_application/__init__.py
"""
Ce module est le cœur de l'application (paquet).

Il contient la factory `create_app`, qui est responsable de l'initialisation
et de la configuration de l'instance Flask, de la base de données, du gestionnaire
de connexion et de l'enregistrement des "Blueprints" (nos modules de routes).
Il gère également la détermination de l'année scolaire active pour chaque requête.
"""

import datetime
import os
from typing import Any

from flask import Flask, flash, g, jsonify, redirect, request, session, url_for
from flask_login import LoginManager, current_user


def create_app(test_config: dict[str, Any] | None = None) -> Flask:
    """
    Crée et configure une instance de l'application Flask (Application Factory).

    Args:
        test_config (dict, optional): Configuration à utiliser pour les tests. Defaults to None.

    Returns:
        Flask: L'instance de l'application Flask configurée.
    """
    # Crée l'application Flask. __name__ fait référence au nom de ce package.
    # L'application cherchera les dossiers `static` et `templates` dans ce même dossier.
    app = Flask(__name__, instance_relative_config=False)

    # Configuration par défaut de l'application.
    # Le SECRET_KEY est essentiel pour la sécurité des sessions.
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY", os.urandom(24)),
        UPLOAD_FOLDER=os.path.join(app.root_path, "uploads"),
        ALLOWED_EXTENSIONS={"xlsx"},
    )

    if test_config:
        # Surcharge la configuration avec celle passée pour les tests.
        app.config.from_mapping(test_config)

    # S'assure que le dossier pour les fichiers téléversés existe.
    try:
        os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    except OSError as e:
        app.logger.error(f"Erreur lors de la création du dossier d'upload: {e}")

    # --- Initialisation des extensions et services ---

    # Initialisation de la base de données
    from . import database

    database.init_app(app)

    # Initialisation de Flask-Login
    login_manager = LoginManager()
    login_manager.init_app(app)
    # Le point d'entrée `auth.login` est le nom de la vue de connexion.
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Veuillez vous connecter pour accéder à cette page."
    login_manager.login_message_category = "info"

    # Gestionnaire personnalisé pour les accès non autorisés, évitant les redirections sur les appels API.
    @login_manager.unauthorized_handler
    def unauthorized_callback():
        """
        Gère les accès non authentifiés.
        Renvoie du JSON pour les requêtes API et redirige pour les autres.
        """
        # Note : On inclut les deux préfixes, /api/ et /admin/api/, pour une gestion complète.
        if request.path.startswith(("/api/", "/admin/api/")):
            return jsonify({"success": False, "message": "Authentification requise."}), 401
        # Pour toutes les autres requêtes (pages web), on garde la redirection.
        flash("Veuillez vous connecter pour accéder à cette page.", "info")
        return redirect(url_for("auth.login"))

    @login_manager.user_loader
    def load_user(user_id: str):
        """
        Fonction de rappel pour recharger l'objet utilisateur à partir de l'ID stocké dans la session.
        Cette fonction est cruciale pour la persistance de la session de connexion.
        """
        from .database import get_user_by_id
        from .models import User

        user_data = get_user_by_id(int(user_id))
        if user_data:
            # Crée l'objet User avec toutes les données nécessaires, y compris les permissions.
            # CORRECTION : Ajout de is_dashboard_only pour assurer la persistance de ce rôle.
            return User(
                _id=user_data["id"],
                username=user_data["username"],
                is_admin=user_data["is_admin"],
                is_dashboard_only=user_data["is_dashboard_only"],
                allowed_champs=user_data["allowed_champs"],
            )
        return None

    # Détermination de l'année scolaire active avant chaque requête.
    # Cette fonction s'assure que 'g.annee_active' est toujours disponible.
    @app.before_request
    def load_active_school_year():
        """
        Détermine l'année scolaire active pour la requête en cours et la stocke dans `g`.

        - Pour les administrateurs, elle utilise l'année stockée en session s'il y en a une.
        - Pour tous les autres, ou si la session est vide, elle utilise l'année "courante" de la BDD.
        - En dernier recours, elle utilise l'année la plus récente.
        """
        from . import database as db

        # Met en cache la liste des années pour la durée de la requête afin d'éviter les appels BDD multiples
        g.toutes_les_annees = db.get_all_annees()
        annee_active = None

        # Si l'utilisateur est admin, on vérifie s'il a choisi une année spécifique
        if current_user.is_authenticated and current_user.is_admin:
            annee_id_session = session.get("annee_scolaire_id")
            if annee_id_session:
                # Cherche l'année choisie par l'admin dans la liste des années
                annee_active = next(
                    (
                        annee
                        for annee in g.toutes_les_annees
                        if annee["annee_id"] == annee_id_session
                    ),
                    None,
                )

        # Si aucune année n'a été choisie par l'admin, ou si l'utilisateur n'est pas admin
        if not annee_active:
            # On cherche l'année marquée comme "courante" dans la BDD
            annee_active = db.get_annee_courante()

        # Si aucune année n'est marquée comme courante (fallback)
        if not annee_active and g.toutes_les_annees:
            # On prend la plus récente par libellé (ex: "2024-2025" > "2023-2024")
            annee_active = max(g.toutes_les_annees, key=lambda x: x["libelle_annee"])
            if current_user.is_authenticated and current_user.is_admin:
                flash(
                    "Aucune année scolaire n'est définie comme 'courante'. Affichage de la plus récente par défaut.",
                    "warning",
                )

        # On stocke l'année active (dictionnaire) dans le contexte de la requête 'g'
        g.annee_active = annee_active

    # --- Filtres Jinja2 et Context Processors ---
    def format_periodes_filter(value: float | None) -> str:
        """Filtre Jinja pour formater joliment les nombres de périodes."""
        if value is None:
            return ""
        # Le format 'g' est idéal: il supprime les zéros non significatifs.
        return f"{float(value):g}"

    app.jinja_env.filters["format_periodes"] = format_periodes_filter

    # Le context processor injecte maintenant aussi les données de l'année scolaire.
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
    from . import auth

    app.register_blueprint(auth.bp)

    from . import views

    app.register_blueprint(views.bp)
    # La route racine '/' doit pointer vers la page d'accueil définie dans le blueprint 'views'.
    app.add_url_rule("/", endpoint="index")

    from . import admin

    app.register_blueprint(admin.bp)

    from . import api  # Importation du module API

    app.register_blueprint(api.bp)  # Enregistrement du blueprint API

    return app