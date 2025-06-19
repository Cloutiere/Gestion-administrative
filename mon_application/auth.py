# mon_application/auth.py
"""
Ce module contient le Blueprint pour les routes d'authentification.
Il est instrumenté pour le débogage.
"""

from flask import (
    Blueprint, current_app, flash, redirect, render_template, request, url_for, session
)
from flask_login import current_user, login_user, logout_user
from werkzeug.wrappers import Response

from .extensions import db
from .models import User
from .services import (
    BusinessRuleValidationError, DuplicateEntityError, ServiceException, register_first_admin_service,
)

bp = Blueprint("auth", __name__, url_prefix="/auth")

# ... (les routes login et logout restent inchangées) ...
@bp.route("/login", methods=["GET", "POST"])
def login() -> str | Response:
    """Gère la connexion des utilisateurs."""
    if current_user.is_authenticated:
        flash("Vous êtes déjà connecté(e).", "info")
        return redirect(url_for("dashboard.page_sommaire"))
    first_user = db.session.query(User).first() is None
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"].strip()
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            flash(f"Connexion réussie! Bienvenue, {user.username}.", "success")
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
    """Gère l'inscription du premier administrateur."""
    print("\n--- [DEBUG] Entrée dans la route /auth/register ---", flush=True)

    user_count = db.session.query(User.id).count()
    print(f"--- [DEBUG] Nombre d'utilisateurs trouvés : {user_count} ---", flush=True)

    # Note: en mode test, cette condition sera toujours fausse
    if user_count > 0 and not current_app.config.get("TESTING", False):
        flash("L'inscription publique est désactivée.", "warning")
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        print("--- [DEBUG] Méthode POST détectée ---", flush=True)
        username = request.form["username"].strip()
        password = request.form["password"].strip()
        confirm_password = request.form["confirm_password"].strip()

        try:
            print("--- [DEBUG] Avant appel au service register_first_admin_service ---", flush=True)
            user = register_first_admin_service(username, password, confirm_password)
            print(f"--- [DEBUG] Service a retourné l'utilisateur : {user.username} ---", flush=True)

            db.session.commit()
            print("--- [DEBUG] db.session.commit() exécuté ---", flush=True)

            # L'étape critique
            print(f"--- [DEBUG] Avant flash. Session actuelle : {session.copy()} ---", flush=True)
            flash(f"Compte admin '{user.username}' créé avec succès! Vous pouvez maintenant vous connecter.", "success")
            print(f"--- [DEBUG] Après flash. Session modifiée : {session.copy()} ---", flush=True)

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