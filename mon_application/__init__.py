# mon_application/__init__.py
"""
Ce module est le cœur de l'application (paquet).

Il contient la factory `create_app`, qui est responsable de l'initialisation
et de la configuration de l'instance Flask, de la base de données, du gestionnaire
de connexion et de l'enregistrement des "Blueprints" (nos modules de routes).
"""

import datetime
import os
from typing import Any

from flask import Flask, flash, jsonify, redirect, request, url_for
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
    # L'ancienne méthode de redirection est conservée comme fallback.
    # Le point d'entrée `auth.login` est le nom de la vue de connexion.
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Veuillez vous connecter pour accéder à cette page."
    login_manager.login_message_category = "info"

    # NOUVEAU: Gestionnaire personnalisé pour les accès non autorisés.
    # C'est la solution clé pour éviter les redirections sur les appels API.
    @login_manager.unauthorized_handler
    def unauthorized_callback():
        """
        Gère les accès non authentifiés.
        Renvoie du JSON pour les requêtes API et redirige pour les autres.
        """
        # Vérifie si la requête cible un endpoint d'API.
        # Note : On inclut les deux préfixes, /api/ et /admin/api/, pour une gestion complète.
        if request.path.startswith("/api/") or request.path.startswith("/admin/api/"):
            return jsonify({"success": False, "message": "Authentification requise."}), 401
        # Pour toutes les autres requêtes (pages web), on garde la redirection.
        flash("Veuillez vous connecter pour accéder à cette page.", "info")
        return redirect(url_for("auth.login"))

    @login_manager.user_loader
    def load_user(user_id: str):
        """
        Fonction de rappel pour recharger l'objet utilisateur à partir de l'ID stocké dans la session.
        """
        from .database import get_user_by_id
        from .models import User

        user_data = get_user_by_id(int(user_id))
        if user_data:
            return User(
                _id=user_data["id"],
                username=user_data["username"],
                is_admin=user_data["is_admin"],
                allowed_champs=user_data["allowed_champs"],
            )
        return None

    # --- Filtres Jinja2 et Context Processors ---
    def format_periodes_filter(value: float | None) -> str:
        """Filtre Jinja pour formater joliment les nombres de périodes."""
        if value is None:
            return ""
        num = float(value)
        # Le format 'g' est idéal: il supprime les zéros non significatifs.
        return f"{num:g}"

    app.jinja_env.filters["format_periodes"] = format_periodes_filter

    @app.context_processor
    def inject_global_data() -> dict[str, Any]:
        """Rend des variables globales disponibles dans tous les templates."""
        return {
            "current_user": current_user,
            "SCRIPT_YEAR": datetime.datetime.now().year,
        }

    # --- Enregistrement des Blueprints ---
    # Les Blueprints organisent les routes en groupes logiques.

    from . import auth

    app.register_blueprint(auth.bp)

    from . import views

    app.register_blueprint(views.bp)
    # La route racine '/' doit pointer vers la page d'accueil définie dans le blueprint 'views'.
    app.add_url_rule("/", endpoint="index")

    from . import admin

    app.register_blueprint(admin.bp)

    from . import api  # Importation du nouveau module API

    app.register_blueprint(api.bp)  # Enregistrement du blueprint API

    return app
