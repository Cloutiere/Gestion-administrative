# mon_application/utils.py
"""
Ce module contient des fonctions et décorateurs utilitaires partagés par l'application.

Le fait de les placer dans un module séparé permet d'éviter les problèmes
d'importation circulaire qui peuvent survenir lorsque les blueprints
et le paquet principal (__init__.py) dépendent les uns des autres.
"""

from functools import wraps

from flask import flash, jsonify, redirect, url_for
from flask_login import current_user


def api_login_required(f):
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


def admin_required(f):
    """
    Décorateur pour les routes de pages web nécessitant des privilèges d'administrateur.
    Si l'utilisateur n'est pas authentifié ou n'est pas administrateur, il est
    redirigé vers la page d'accueil avec un message flash.
    """

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not getattr(current_user, "is_admin", False):
            flash("Vous n'avez pas les permissions suffisantes pour accéder à cette page.", "error")
            return redirect(url_for("views.index"))
        return f(*args, **kwargs)

    return decorated_function


def admin_api_required(f):
    """
    Décorateur pour les routes d'API nécessitant des privilèges d'administrateur.
    Si l'utilisateur n'est pas authentifié ou n'est pas administrateur, il retourne
    une réponse JSON avec un code d'erreur HTTP approprié (401 ou 403).
    Ce décorateur vérifie d'abord l'authentification, donc @api_login_required
    n'est pas nécessaire en plus de celui-ci.
    """

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return jsonify({"success": False, "message": "Authentification requise."}), 401
        if not getattr(current_user, "is_admin", False):
            return jsonify({"success": False, "message": "Permissions insuffisantes."}), 403
        return f(*args, **kwargs)

    return decorated_function
