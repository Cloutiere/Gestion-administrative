# mon_application/auth.py
"""
Ce module contient le Blueprint pour les routes d'authentification.
VERSION CORRIGÉE.
"""

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_user, logout_user
from werkzeug.wrappers import Response

from .extensions import db
from .models import User
from .services import (
    BusinessRuleValidationError,
    DuplicateEntityError,
    ServiceException,
    register_first_admin_service,
)

bp = Blueprint("auth", __name__, url_prefix="/auth")


@bp.route("/login", methods=["GET", "POST"])
def login() -> str | Response:
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.page_sommaire"))
    first_user = db.session.query(User).first() is None
    if request.method == "POST":
        user = User.query.filter_by(username=request.form["username"].strip()).first()
        if user and user.check_password(request.form["password"].strip()):
            login_user(user)
            flash(f"Connexion réussie! Bienvenue, {user.username}.", "success")
            return redirect(request.args.get("next") or url_for("dashboard.page_sommaire"))
        flash("Nom d'utilisateur ou mot de passe invalide.", "error")
    return render_template("login.html", first_user=first_user)


@bp.route("/logout")
def logout() -> Response:
    logout_user()
    flash("Vous avez été déconnecté(e).", "info")
    return redirect(url_for("auth.login"))


@bp.route("/register", methods=["GET", "POST"])
def register() -> str | Response:
    """Gère l'inscription du premier administrateur."""
    user_count = db.session.query(User.id).count()

    # CORRECTION : La condition est simplifiée. Si des utilisateurs existent,
    # on bloque toujours l'accès, peu importe l'environnement.
    if user_count > 0:
        flash("L'inscription publique est désactivée. Un administrateur doit créer les nouveaux comptes.", "warning")
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        try:
            user = register_first_admin_service(request.form["username"].strip(), request.form["password"].strip(), request.form["confirm_password"].strip())
            db.session.commit()
            flash(f"Compte admin '{user.username}' créé avec succès! Vous pouvez maintenant vous connecter.", "success")
            return redirect(url_for("auth.login"))
        except (BusinessRuleValidationError, DuplicateEntityError) as e:
            db.session.rollback()
            flash(e.message, "error")
        except ServiceException as e:
            db.session.rollback()
            current_app.logger.error(f"Erreur de service lors de l'inscription: {e}")
            flash("Une erreur inattendue est survenue.", "error")

    return render_template(
        "register.html",
        first_user=(user_count == 0),
        username=request.form.get("username", ""),
    )
