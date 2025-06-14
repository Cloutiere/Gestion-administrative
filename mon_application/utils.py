# mon_application/utils.py
"""
Ce module contient des fonctions et décorateurs utilitaires partagés par l'application.

Le fait de les placer dans un module séparé permet d'éviter les problèmes
d'importation circulaire qui peuvent survenir lorsque les blueprints
et le paquet principal (__init__.py) dépendent les uns des autres.
"""

from functools import wraps
from typing import Callable

from flask import flash, jsonify, redirect, url_for
from flask_login import current_user


def api_login_required(f: Callable) -> Callable:
    """
    Décorateur pour les routes d'API qui nécessitent une authentification.
    Si l'utilisateur n'est pas connecté, retourne une réponse JSON avec un
    code d'erreur 401 (Unauthorized) au lieu d'une redirection HTML.
    """

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return jsonify({"success": False, "message": "Authentification requise."}), 401
        return f(*args, **kwargs)

    return decorated_function


def admin_required(f: Callable) -> Callable:
    """
    Décorateur pour les routes de pages web nécessitant des privilèges d'administrateur.
    Si l'utilisateur n'est pas authentifié ou n'est pas administrateur (`is_admin`),
    il est redirigé vers la page d'accueil avec un message flash.
    """

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not getattr(
            current_user, "is_admin", False
        ):
            flash(
                "Vous n'avez pas les permissions suffisantes pour accéder à cette page.",
                "error",
            )
            return redirect(url_for("views.index"))
        return f(*args, **kwargs)

    return decorated_function


def admin_api_required(f: Callable) -> Callable:
    """
    Décorateur pour les routes d'API nécessitant des privilèges d'administrateur.
    Si l'utilisateur n'est pas authentifié ou n'est pas administrateur, il retourne
    une réponse JSON avec un code d'erreur HTTP approprié (401 ou 403).
    Ce décorateur vérifie d'abord l'authentification.
    """

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return jsonify({"success": False, "message": "Authentification requise."}), 401
        if not getattr(current_user, "is_admin", False):
            return (
                jsonify({"success": False, "message": "Permissions d'administrateur requises."}),
                403,
            )
        return f(*args, **kwargs)

    return decorated_function


def dashboard_access_required(f: Callable) -> Callable:
    """
    Décorateur pour les pages web du tableau de bord.
    Autorise l'accès si l'utilisateur est authentifié ET est soit administrateur
    (`is_admin`), soit un observateur de tableau de bord (`is_dashboard_only`).
    Sinon, redirige avec un message d'erreur.
    """

    @wraps(f)
    def decorated_function(*args, **kwargs):
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


def dashboard_api_access_required(f: Callable) -> Callable:
    """
    Décorateur pour les API du tableau de bord.
    Autorise l'accès si l'utilisateur est authentifié ET est soit administrateur
    (`is_admin`), soit un observateur de tableau de bord (`is_dashboard_only`).
    Sinon, retourne une erreur JSON 401 ou 403.
    """

    @wraps(f)
    def decorated_function(*args, **kwargs):
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