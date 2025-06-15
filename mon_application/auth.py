# mon_application/auth.py
"""
Ce module contient le Blueprint pour les routes d'authentification.

Il gère la connexion, la déconnexion et l'inscription des utilisateurs.
"""

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_user, logout_user
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.wrappers import Response

from . import database as db

# Crée un Blueprint nommé 'auth'.
bp = Blueprint("auth", __name__, url_prefix="/auth")


@bp.route("/login", methods=["GET", "POST"])
def login() -> str | Response:
    """Gère la connexion des utilisateurs."""
    if current_user.is_authenticated:
        flash("Vous êtes déjà connecté(e).", "info")
        return redirect(url_for("dashboard.page_sommaire"))

    first_user = db.get_users_count() == 0

    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"].strip()
        user_data = db.get_user_by_username(username)

        if user_data and check_password_hash(user_data["password_hash"], password):
            # Utilisation de la factory centralisée pour créer l'objet User
            user_obj = db.get_user_obj_by_id(user_data["id"])
            if user_obj:
                login_user(user_obj)
                flash(f"Connexion réussie! Bienvenue, {user_obj.username}.", "success")

                next_page = request.args.get("next")
                return redirect(next_page or url_for("dashboard.page_sommaire"))

        flash("Nom d'utilisateur ou mot de passe invalide.", "error")

    return render_template("login.html", first_user=first_user)


@bp.route("/logout")
def logout() -> Response:
    """Déconnecte l'utilisateur actuel."""
    logout_user()
    flash("Vous avez été déconnecté(e).", "info")
    return redirect(url_for("auth.login"))


@bp.route("/register", methods=["GET", "POST"])
def register() -> str | Response:
    """Gère l'inscription.

    L'inscription est automatiquement autorisée pour le premier utilisateur, qui
    sera créé en tant qu'administrateur. Pour les utilisateurs suivants,
    l'inscription doit être gérée par un administrateur via l'interface dédiée.
    """
    user_count = db.get_users_count()

    if user_count > 0:
        flash(
            "L'inscription publique est désactivée. " "Un administrateur doit créer les nouveaux comptes.",
            "warning",
        )
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"].strip()
        confirm_password = request.form["confirm_password"].strip()

        if not all([username, password, confirm_password]):
            flash("Tous les champs sont requis.", "error")
        elif password != confirm_password:
            flash("Les mots de passe ne correspondent pas.", "error")
        elif len(password) < 6:
            flash("Le mot de passe doit contenir au moins 6 caractères.", "error")
        else:
            user = db.create_user(username, generate_password_hash(password), is_admin=True)
            if user:
                flash(
                    f"Compte admin '{username}' créé avec succès! " "Vous pouvez maintenant vous connecter.",
                    "success",
                )
                return redirect(url_for("auth.login"))
            flash("Ce nom d'utilisateur est déjà pris.", "error")

    return render_template(
        "register.html",
        first_user=(user_count == 0),
        username=request.form.get("username", ""),
    )