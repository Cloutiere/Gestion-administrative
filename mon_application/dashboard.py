# mon_application/dashboard.py
"""
Ce module contient le Blueprint pour les routes du tableau de bord.

Il regroupe les pages HTML et les points d'API RESTful destinés à la
visualisation des données et à leur exportation, accessibles aux administrateurs
et aux utilisateurs ayant le rôle "dashboard_only".
Les permissions sont gérées par les décorateurs `dashboard_access_required`
et `dashboard_api_access_required`.
"""

from typing import Any, cast

from flask import (
    Blueprint,
    current_app,
    flash,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_login import current_user

# AJOUT : Importation pour générer le jeton CSRF explicitement
from flask_wtf.csrf import generate_csrf
from werkzeug.wrappers import Response

from . import exports, services
from .services import BusinessRuleValidationError, ServiceException
from .utils import dashboard_access_required, dashboard_api_access_required

# Crée un Blueprint 'dashboard'.
bp = Blueprint("dashboard", __name__, url_prefix="/admin")


# --- ROUTES DES PAGES (HTML) ---


@bp.route("/sommaire")
@dashboard_access_required
def page_sommaire() -> str:
    """Affiche la page du sommaire global des moyennes pour l'année active."""
    annee_active = cast(dict[str, Any] | None, getattr(g, "annee_active", None))
    summary_data = {}
    if not annee_active:
        flash("Aucune année scolaire n'est disponible. Veuillez en créer une dans la section 'Données'.", "warning")
    else:
        try:
            summary_data = services.get_dashboard_summary_service(annee_active["annee_id"])
        except ServiceException as e:
            flash(f"Erreur lors de la récupération du sommaire : {e.message}", "error")

    # MODIFICATION : Passer le jeton CSRF explicitement au template
    return render_template(
        "page_sommaire.html",
        moyennes_par_champ=summary_data.get("moyennes_par_champ", {}),
        moyenne_generale=summary_data.get("moyenne_generale", 0.0),
        moyenne_preliminaire_confirmee=summary_data.get("moyenne_preliminaire_confirmee", 0.0),
        grand_totals=summary_data.get("grand_totals", {}),
        csrf_token_value=generate_csrf(),  # Génère et passe le jeton
    )


@bp.route("/detail_taches")
@dashboard_access_required
def page_detail_taches() -> str:
    """Affiche la page de détail des tâches par enseignant pour l'année active."""
    annee_active = cast(dict[str, Any] | None, getattr(g, "annee_active", None))
    enseignants_par_champ = []
    if not annee_active:
        flash("Aucune année scolaire n'est disponible. Les détails ne peuvent être affichés.", "warning")
    else:
        try:
            enseignants_par_champ = services.get_detailed_tasks_data_service(annee_active["annee_id"])
        except ServiceException as e:
            flash(f"Erreur lors de la récupération des détails : {e.message}", "error")

    return render_template("detail_taches.html", enseignants_par_champ=enseignants_par_champ)


@bp.route("/preparation_horaire")
@dashboard_access_required
def page_preparation_horaire() -> str | Response:
    """Affiche la page de préparation de l'horaire."""
    annee_active = cast(dict[str, Any] | None, getattr(g, "annee_active", None))
    if not annee_active:
        flash("Impossible d'afficher la préparation : aucune année scolaire n'est active.", "error")
        return redirect(url_for("dashboard.page_sommaire"))

    try:
        annee_id = annee_active["annee_id"]
        preparation_data = services.get_preparation_horaire_data_service(annee_id)
        return render_template(
            "preparation_horaire.html",
            annee_active=annee_active,
            preparation_data=preparation_data,
        )
    except ServiceException as e:
        flash(f"Erreur lors du chargement des données de préparation : {e.message}", "error")
        return redirect(url_for("dashboard.page_sommaire"))


# --- API ENDPOINTS (JSON) ---


@bp.route("/api/annees/changer_active", methods=["POST"])
@dashboard_api_access_required
def api_changer_annee_active() -> tuple[Response, int]:
    """API pour changer l'année de travail (stockée en session)."""
    data = request.get_json()
    if not data or not (annee_id := data.get("annee_id")):
        return jsonify({"success": False, "message": "ID de l'année manquant."}), 400

    session["annee_scolaire_id"] = annee_id
    toutes_les_annees = cast(list[dict[str, Any]], getattr(g, "toutes_les_annees", []))
    annee_selectionnee = next((annee for annee in toutes_les_annees if annee["annee_id"] == annee_id), None)
    if annee_selectionnee:
        current_app.logger.info(
            f"Année de travail changée pour l'utilisateur '{current_user.username}' : " f"'{annee_selectionnee['libelle_annee']}'."
        )
    return jsonify({"success": True, "message": "Année de travail changée."}), 200


@bp.route("/api/sommaire/donnees", methods=["GET"])
@dashboard_api_access_required
def api_get_donnees_sommaire() -> tuple[Response, int]:
    """API pour récupérer les données du sommaire pour l'année active."""
    annee_active = cast(dict[str, Any] | None, getattr(g, "annee_active", None))
    if not annee_active:
        current_app.logger.warning("API sommaire: Aucune année active, retour de données vides.")
        return jsonify(
            moyennes_par_champ={},
            moyenne_generale=0.0,
            moyenne_preliminaire_confirmee=0.0,
            grand_totals={},
            enseignants_par_champ=[],
        ), 200

    try:
        annee_id = annee_active["annee_id"]
        summary_data = services.get_dashboard_summary_service(annee_id)
        details_data = services.get_detailed_tasks_data_service(annee_id)

        response_data = {**summary_data, "enseignants_par_champ": details_data}
        return jsonify(response_data), 200
    except ServiceException as e:
        return jsonify({"success": False, "message": e.message}), 500


@bp.route("/api/preparation_horaire/sauvegarder", methods=["POST"])
@dashboard_api_access_required
def api_sauvegarder_preparation_horaire() -> tuple[Response, int]:
    """API pour sauvegarder les données de la préparation de l'horaire."""
    annee_active = cast(dict[str, Any] | None, getattr(g, "annee_active", None))
    if not annee_active:
        return jsonify({"success": False, "message": "Aucune année scolaire active."}), 400

    data = request.get_json()
    if not data or "assignments" not in data:
        return jsonify({"success": False, "message": "Données de sauvegarde manquantes."}), 400

    try:
        annee_id = annee_active["annee_id"]
        services.save_preparation_horaire_service(annee_id, data["assignments"])
        current_app.logger.info(f"Préparation de l'horaire sauvegardée pour l'année {annee_id} par l'utilisateur '{current_user.username}'.")
        return jsonify({"success": True, "message": "Préparation sauvegardée avec succès."}), 200
    except (ServiceException, BusinessRuleValidationError) as e:
        current_app.logger.error(f"Erreur lors de la sauvegarde de la préparation: {e.message}")
        return jsonify({"success": False, "message": e.message}), 400
    except Exception as e:
        current_app.logger.error(f"Erreur inattendue lors de la sauvegarde de la préparation: {e}", exc_info=True)
        return jsonify({"success": False, "message": "Une erreur serveur est survenue."}), 500


# --- ROUTES D'EXPORT ---


@bp.route("/exporter_taches_excel")
@dashboard_access_required
def exporter_taches_excel() -> Response:
    """Exporte toutes les tâches attribuées pour l'année active dans un fichier Excel."""
    annee_active = cast(dict[str, Any] | None, getattr(g, "annee_active", None))
    if not annee_active:
        flash("Exportation impossible : aucune année scolaire n'est active.", "error")
        return redirect(url_for("dashboard.page_sommaire"))

    try:
        annee_id = annee_active["annee_id"]
        annee_libelle = annee_active["libelle_annee"]
        attributions_par_champ = services.get_attributions_for_export_service(annee_id)

        if not attributions_par_champ:
            flash(f"Aucune tâche attribuée pour '{annee_libelle}'.", "warning")
            return redirect(url_for("dashboard.page_sommaire"))

        mem_file = exports.generer_export_taches(attributions_par_champ)
        filename = f"export_taches_{annee_libelle}.xlsx"
        current_app.logger.info(f"Génération du fichier d'export '{filename}'.")

        return Response(
            mem_file,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )
    except ServiceException as e:
        flash(f"Erreur lors de la génération de l'export : {e.message}", "error")
        return redirect(url_for("dashboard.page_sommaire"))


@bp.route("/exporter_periodes_restantes_excel")
@dashboard_access_required
def exporter_periodes_restantes_excel() -> Response:
    """Exporte les périodes non attribuées (restantes) pour l'année active."""
    annee_active = cast(dict[str, Any] | None, getattr(g, "annee_active", None))
    if not annee_active:
        flash("Exportation impossible : aucune année scolaire n'est active.", "error")
        return redirect(url_for("dashboard.page_sommaire"))

    try:
        annee_id = annee_active["annee_id"]
        annee_libelle = annee_active["libelle_annee"]
        periodes_par_champ = services.get_remaining_periods_for_export_service(annee_id)

        if not periodes_par_champ:
            flash(f"Aucune période restante pour '{annee_libelle}'.", "warning")
            return redirect(url_for("dashboard.page_sommaire"))

        mem_file = exports.generer_export_periodes_restantes(periodes_par_champ)
        filename = f"export_periodes_restantes_{annee_libelle}.xlsx"
        current_app.logger.info(f"Génération de l'export '{filename}'.")

        return Response(
            mem_file,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )
    except ServiceException as e:
        flash(f"Erreur lors de la génération de l'export : {e.message}", "error")
        return redirect(url_for("dashboard.page_sommaire"))


@bp.route("/exporter_org_scolaire_excel")
@dashboard_access_required
def exporter_org_scolaire_excel() -> Response:
    """Exporte les données pour l'organisation scolaire pour l'année active."""
    annee_active = cast(dict[str, Any] | None, getattr(g, "annee_active", None))
    if not annee_active:
        flash("Exportation impossible : aucune année scolaire n'est active.", "error")
        return redirect(url_for("dashboard.page_sommaire"))

    try:
        annee_id = annee_active["annee_id"]
        annee_libelle = annee_active["libelle_annee"]
        donnees_par_champ = services.get_org_scolaire_export_data_service(annee_id)

        if not donnees_par_champ:
            flash(f"Aucune donnée à exporter pour '{annee_libelle}'.", "warning")
            return redirect(url_for("dashboard.page_sommaire"))

        mem_file = exports.generer_export_org_scolaire(donnees_par_champ)
        filename = f"export_org_scolaire_{annee_libelle}.xlsx"
        current_app.logger.info(f"Génération de l'export '{filename}'.")

        return Response(
            mem_file,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )
    except ServiceException as e:
        flash(f"Erreur lors de la génération de l'export : {e.message}", "error")
        return redirect(url_for("dashboard.page_sommaire"))
