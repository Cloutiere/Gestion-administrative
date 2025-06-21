# mon_application/views.py
"""
Ce module définit les vues principales (routes) de l'application qui ne sont pas
liées à l'administration, à l'authentification ou au tableau de bord.
"""

from flask import (
    Blueprint,
    abort,
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_login import current_user, login_required

# --- Imports des services refactorisés ---
from .services import (
    EntityNotFoundError,
    ServiceException,
    get_data_for_champ_page_service,
)

# L'import des fonctions d'export a été supprimé d'ici pour éviter les dépendances circulaires.
# Elles seront importées directement dans les routes qui les utilisent.

bp = Blueprint("views", __name__)


@bp.route("/")
def index():
    """Page d'accueil, redirige vers le tableau de bord ou la page de connexion."""
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.main"))
    return redirect(url_for("auth.login"))


@bp.route("/select_annee_scolaire", methods=["POST"])
@login_required
def select_annee_scolaire():
    """Permet à l'utilisateur de changer l'année scolaire affichée."""
    annee_id = request.form.get("annee_id")
    if annee_id:
        session["annee_scolaire_id"] = int(annee_id)
    return redirect(request.referrer or url_for("views.index"))


@bp.route("/champ/<champ_no>")
@login_required
def page_champ(champ_no):
    """Affiche la page de détail pour un champ spécifique."""
    if not g.annee_active:
        flash("Aucune année scolaire active. Impossible d'afficher la page.", "danger")
        return redirect(url_for("views.index"))

    # Vérification des autorisations
    if not current_user.can_access_champ(champ_no):
        abort(403)  # Accès interdit

    try:
        annee_id = g.annee_active["annee_id"]
        page_data = get_data_for_champ_page_service(champ_no, annee_id)
        return render_template("views/page_champ.html", **page_data)

    except EntityNotFoundError:
        abort(404)
    except ServiceException as e:
        flash(f"Une erreur est survenue lors du chargement de la page : {e.message}", "danger")
        return redirect(url_for("dashboard.main"))


@bp.route("/export/attributions")
@login_required
def page_export():
    """Génère et télécharge le fichier Excel des attributions."""
    if not g.annee_active:
        flash("Aucune année scolaire active. Impossible de générer l'export.", "danger")
        return redirect(url_for("dashboard.main"))

    try:
        # Import local pour éviter les dépendances circulaires
        from .exports import generate_attributions_excel

        return generate_attributions_excel(g.annee_active["annee_id"])
    except ServiceException as e:
        flash(f"Erreur lors de la génération de l'export des attributions: {e.message}", "danger")
        return redirect(request.referrer or url_for("dashboard.main"))


@bp.route("/export/periodes_restantes")
@login_required
def export_periodes_restantes():
    """Génère et télécharge le fichier Excel des périodes restantes (tâches)."""
    if not g.annee_active:
        flash("Aucune année scolaire active. Impossible de générer l'export.", "danger")
        return redirect(url_for("dashboard.main"))
    try:
        # Import local
        from .exports import generate_periodes_restantes_excel

        return generate_periodes_restantes_excel(g.annee_active["annee_id"])
    except ServiceException as e:
        flash(f"Erreur lors de la génération de l'export des périodes restantes: {e.message}", "danger")
        return redirect(request.referrer or url_for("dashboard.main"))


@bp.route("/export/organisation_scolaire")
@login_required
def export_organisation_scolaire():
    """Génère et télécharge le fichier Excel de l'organisation scolaire."""
    if not g.annee_active:
        flash("Aucune année scolaire active. Impossible de générer l'export.", "danger")
        return redirect(url_for("dashboard.main"))
    try:
        # Import local
        from .exports import generate_org_scolaire_excel

        return generate_org_scolaire_excel(g.annee_active["annee_id"])
    except ServiceException as e:
        flash(f"Erreur lors de la génération de l'export de l'organisation scolaire: {e.message}", "danger")
        return redirect(request.referrer or url_for("dashboard.main"))