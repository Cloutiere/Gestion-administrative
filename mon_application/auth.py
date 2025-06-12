# mon_application/auth.py
"""
Ce module contient le Blueprint pour les routes d'authentification.

Il gère la connexion, la déconnexion et l'inscription des utilisateurs.
"""

from typing import Any

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_user, logout_user
from werkzeug.security import check_password_hash, generate_password_hash

from . import database as db
from .models import User

# Crée un Blueprint nommé 'auth'.
bp = Blueprint("auth", __name__, url_prefix="/auth")


@bp.route("/login", methods=["GET", "POST"])
def login() -> Any:
    """Gère la connexion des utilisateurs."""
    if current_user.is_authenticated:
        flash("Vous êtes déjà connecté(e).", "info")
        # Redirige vers le tableau de bord si déjà connecté.
        return redirect(url_for("admin.page_sommaire"))

    # Vérifie si c'est le premier utilisateur pour afficher le lien d'inscription.
    first_user = db.get_users_count() == 0

    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"].strip()
        user_data = db.get_user_by_username(username)

        if user_data and check_password_hash(user_data["password_hash"], password):
            # Les données de l'utilisateur ont été trouvées, maintenant on charge l'objet User complet
            user_obj_data = db.get_user_by_id(user_data["id"])
            if user_obj_data:
                user = User(
                    _id=user_obj_data["id"],
                    username=user_obj_data["username"],
                    is_admin=user_obj_data["is_admin"],
                    allowed_champs=user_obj_data["allowed_champs"],
                )
                login_user(user)
                flash(f"Connexion réussie! Bienvenue, {user.username}.", "success")

                # Redirection systématique vers le tableau de bord global.
                next_page = request.args.get("next")
                return redirect(next_page or url_for("admin.page_sommaire"))

        flash("Nom d'utilisateur ou mot de passe invalide.", "error")

    return render_template("login.html", first_user=first_user)


@bp.route("/logout")
def logout() -> Any:
    """Déconnecte l'utilisateur actuel."""
    logout_user()
    flash("Vous avez été déconnecté(e).", "info")
    return redirect(url_for("auth.login"))


@bp.route("/register", methods=["GET", "POST"])
def register() -> Any:
    """Gère l'inscription, réservée au premier utilisateur."""
    user_count = db.get_users_count()

    # Si des utilisateurs existent déjà, l'inscription est désactivée.
    if user_count > 0 and not current_user.is_authenticated:
        flash("L'inscription directe est désactivée. Veuillez contacter un administrateur.", "error")
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
            hashed_pwd = generate_password_hash(password)
            # Le premier utilisateur est toujours admin.
            user = db.create_user(username, hashed_pwd, is_admin=True)
            if user:
                flash(f"Compte admin '{username}' créé avec succès! Vous pouvez vous connecter.", "success")
                return redirect(url_for("auth.login"))
            flash("Ce nom d'utilisateur est déjà pris.", "error")

    # Affiche le formulaire d'inscription pour le premier utilisateur.
    return render_template("register.html", first_user=(user_count == 0), username=request.form.get("username", ""))
