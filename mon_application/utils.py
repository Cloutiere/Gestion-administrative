# mon_application/utils.py
"""
Ce module contient des fonctions et décorateurs utilitaires partagés par l'application.

Le fait de les placer dans un module séparé permet d'éviter les problèmes
d'importation circulaire qui peuvent survenir lorsque les blueprints
et le paquet principal (__init__.py) dépendent les uns des autres.
"""

from collections.abc import Callable
from functools import wraps
from typing import Any, cast

from flask import flash, g, jsonify, redirect, url_for
from flask_login import current_user
from werkzeug.wrappers import Response


def annee_active_required(f: Callable[..., Any]) -> Callable[..., Any]:
    """
    Décorateur pour les routes d'API qui nécessitent une année scolaire active.

    Vérifie si `g.annee_active` est défini. Si ce n'est pas le cas, il retourne
    une erreur JSON 400. Sinon, il injecte l'année active en tant qu'argument
    nommé `annee_active` dans la fonction de la vue.
    """

    @wraps(f)
    def decorated_function(*args: Any, **kwargs: Any) -> tuple[Response, int] | Any:
        annee_active = cast(dict[str, Any] | None, getattr(g, "annee_active", None))
        if not annee_active:
            return jsonify({"success": False, "message": "Aucune année scolaire active."}), 400
        # Injecte l'année active dans les arguments de la fonction décorée
        return f(*args, annee_active=annee_active, **kwargs)

    return decorated_function


def api_login_required(f: Callable[..., Any]) -> Callable[..., Any]:
    """
    Décorateur pour les routes d'API qui nécessitent une authentification.
    Si l'utilisateur n'est pas connecté, retourne une réponse JSON 401.
    """

    @wraps(f)
    def decorated_function(*args: Any, **kwargs: Any) -> tuple[Response, int] | Any:
        if not current_user.is_authenticated:
            return jsonify({"success": False, "message": "Authentification requise."}), 401
        return f(*args, **kwargs)

    return decorated_function


def admin_required(f: Callable[..., Any]) -> Callable[..., Any]:
    """
    Décorateur pour les routes de pages web nécessitant des privilèges d'administrateur.
    Si l'utilisateur n'est pas autorisé, redirige vers la page d'accueil.
    """

    @wraps(f)
    def decorated_function(*args: Any, **kwargs: Any) -> Response | Any:
        if not current_user.is_authenticated or not getattr(current_user, "is_admin", False):
            flash(
                "Vous n'avez pas les permissions suffisantes pour accéder à cette page.",
                "error",
            )
            return redirect(url_for("views.index"))
        return f(*args, **kwargs)

    return decorated_function


def admin_api_required(f: Callable[..., Any]) -> Callable[..., Any]:
    """
    Décorateur pour les routes d'API nécessitant des privilèges d'administrateur.
    Retourne une erreur JSON 401 ou 403 si l'utilisateur n'est pas autorisé.
    """

    @wraps(f)
    def decorated_function(*args: Any, **kwargs: Any) -> tuple[Response, int] | Any:
        if not current_user.is_authenticated:
            return jsonify({"success": False, "message": "Authentification requise."}), 401
        if not getattr(current_user, "is_admin", False):
            return (
                jsonify({"success": False, "message": "Permissions d'administrateur requises."}),
                403,
            )
        return f(*args, **kwargs)

    return decorated_function


def dashboard_access_required(f: Callable[..., Any]) -> Callable[..., Any]:
    """
    Décorateur pour les pages web du tableau de bord.
    Autorise l'accès aux administrateurs et aux observateurs.
    """

    @wraps(f)
    def decorated_function(*args: Any, **kwargs: Any) -> Response | Any:
        is_admin = getattr(current_user, "is_admin", False)
        is_dashboard_only = getattr(current_user, "is_dashboard_only", False)

        if not current_user.is_authenticated or not (is_admin or is_dashboard_only):
            flash(
                "Vous n'avez pas les permissions suffisantes pour accéder à cette page.",
                "error",
            )
            return redirect(url_for("views.index"))
        return f(*args, **kwargs)

    return decorated_function


def dashboard_api_access_required(f: Callable[..., Any]) -> Callable[..., Any]:
    """
    Décorateur pour les API du tableau de bord.
    Autorise l'accès aux administrateurs et aux observateurs.
    """

    @wraps(f)
    def decorated_function(*args: Any, **kwargs: Any) -> tuple[Response, int] | Any:
        if not current_user.is_authenticated:
            return jsonify({"success": False, "message": "Authentification requise."}), 401

        is_admin = getattr(current_user, "is_admin", False)
        is_dashboard_only = getattr(current_user, "is_dashboard_only", False)

        if not (is_admin or is_dashboard_only):
            return (
                jsonify({"success": False, "message": "Permissions insuffisantes."}),
                403,
            )
        return f(*args, **kwargs)

    return decorated_function
