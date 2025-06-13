# mon_application/admin.py
"""
Ce module contient le Blueprint pour les routes réservées aux administrateurs.

Il inclut les pages HTML de l'interface d'administration et les points d'API RESTful
pour les opérations qui nécessitent des privilèges d'administrateur.
Toutes les opérations sont désormais dépendantes de l'année scolaire active.
"""

from typing import Any, cast

import openpyxl
import psycopg2
import psycopg2.extras
from flask import (
    Blueprint,
    Response,
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
from openpyxl.utils.exceptions import InvalidFileException
from openpyxl.worksheet.worksheet import Worksheet
from psycopg2.extensions import connection
from werkzeug.security import generate_password_hash

from . import database as db
from . import exports
from .utils import admin_api_required, admin_required

# Crée un Blueprint 'admin' avec un préfixe d'URL.
bp = Blueprint("admin", __name__, url_prefix="/admin")


# --- Fonctions utilitaires pour le sommaire (maintenant dépendantes de l'année) ---
def calculer_donnees_sommaire(
    annee_id: int,
) -> tuple[
    list[dict[str, Any]], dict[str, dict[str, Any]], float, float, dict[str, float]
]:
    """
    Calcule les données agrégées pour la page sommaire globale pour une année donnée.

    Cette fonction adopte une approche "centrée sur le champ" pour garantir que tous
    les champs sont listés, même ceux sans enseignant pour l'année active.

    Args:
        annee_id: L'ID de l'année scolaire pour laquelle calculer les données.

    Returns:
        Un tuple contenant :
        - La liste des enseignants groupés par champ (pour la page de détail).
        - Un dictionnaire des moyennes et totaux par champ, incluant les statuts.
        - La moyenne générale des périodes pour les enseignants à temps plein.
        - La moyenne "Préliminaire confirmée" (enseignants TP des champs confirmés).
        - Un dictionnaire contenant les totaux globaux pour le pied de tableau.
    """
    # Étape 1 : Récupérer toutes les données brutes nécessaires.
    tous_les_champs = db.get_all_champs()
    statuts_champs = db.get_all_champ_statuses_for_year(annee_id)
    tous_enseignants_details = db.get_all_enseignants_avec_details(annee_id)

    # Étape 2 : Initialiser les structures de données en se basant sur TOUS les champs.
    moyennes_par_champ_calculees: dict[str, Any] = {}
    for champ in tous_les_champs:
        champ_no = str(champ["champno"])
        statut = statuts_champs.get(
            champ_no, {"est_verrouille": False, "est_confirme": False}
        )
        moyennes_par_champ_calculees[champ_no] = {
            "champ_nom": champ["champnom"],
            "est_verrouille": statut["est_verrouille"],
            "est_confirme": statut["est_confirme"],
            "nb_enseignants_tp": 0,
            "periodes_choisies_tp": 0.0,
            "moyenne": 0.0,
            "periodes_magiques": 0.0,
        }

    enseignants_par_champ_temp: dict[str, Any] = {
        str(champ["champno"]): {
            "champno": str(champ["champno"]),
            "champnom": champ["champnom"],
            "enseignants": [],
            "est_verrouille": moyennes_par_champ_calculees[str(champ["champno"])][
                "est_verrouille"
            ],
            "est_confirme": moyennes_par_champ_calculees[str(champ["champno"])][
                "est_confirme"
            ],
        }
        for champ in tous_les_champs
    }

    # Étape 3 : Parcourir les enseignants pour peupler les structures initialisées.
    for ens in tous_enseignants_details:
        champ_no = ens["champno"]
        if champ_no in enseignants_par_champ_temp:
            enseignants_par_champ_temp[champ_no]["enseignants"].append(ens)

        if ens["compte_pour_moyenne_champ"] and champ_no in moyennes_par_champ_calculees:
            moyennes_par_champ_calculees[champ_no]["nb_enseignants_tp"] += 1
            moyennes_par_champ_calculees[champ_no]["periodes_choisies_tp"] += ens[
                "total_periodes"
            ]

    # Étape 4 : Calculer les moyennes, totaux et agrégats finaux.
    total_periodes_global_tp = 0.0
    nb_enseignants_tp_global = 0
    total_periodes_confirme_tp = 0.0
    nb_enseignants_confirme_tp = 0
    total_enseignants_tp_etablissement = 0
    total_periodes_choisies_tp_etablissement = 0.0
    total_periodes_magiques_etablissement = 0.0

    for data in moyennes_par_champ_calculees.values():
        nb_ens_tp = data["nb_enseignants_tp"]
        periodes_choisies_tp = data["periodes_choisies_tp"]

        data["moyenne"] = (periodes_choisies_tp / nb_ens_tp) if nb_ens_tp > 0 else 0.0
        data["periodes_magiques"] = periodes_choisies_tp - (nb_ens_tp * 24)

        total_enseignants_tp_etablissement += nb_ens_tp
        total_periodes_choisies_tp_etablissement += periodes_choisies_tp
        total_periodes_magiques_etablissement += data["periodes_magiques"]

        if nb_ens_tp > 0:
            total_periodes_global_tp += periodes_choisies_tp
            nb_enseignants_tp_global += nb_ens_tp
            if data["est_confirme"]:
                total_periodes_confirme_tp += periodes_choisies_tp
                nb_enseignants_confirme_tp += nb_ens_tp

    moyenne_generale_calculee = (
        (total_periodes_global_tp / nb_enseignants_tp_global)
        if nb_enseignants_tp_global > 0
        else 0.0
    )
    moyenne_prelim_conf = (
        (total_periodes_confirme_tp / nb_enseignants_confirme_tp)
        if nb_enseignants_confirme_tp > 0
        else 0.0
    )

    grand_totals = {
        "total_enseignants_tp": total_enseignants_tp_etablissement,
        "total_periodes_choisies_tp": total_periodes_choisies_tp_etablissement,
        "total_periodes_magiques": total_periodes_magiques_etablissement,
    }

    return (
        list(enseignants_par_champ_temp.values()),
        moyennes_par_champ_calculees,
        moyenne_generale_calculee,
        moyenne_prelim_conf,
        grand_totals,
    )


# --- ROUTES DES PAGES D'ADMINISTRATION (HTML) ---


@bp.route("/sommaire")
@admin_required
def page_sommaire() -> str:
    """Affiche la page du sommaire global des moyennes pour l'année active."""
    if not g.annee_active:
        flash(
            "Aucune année scolaire n'est disponible. Veuillez en créer une "
            "dans la section 'Données'.",
            "warning",
        )
        return render_template(
            "page_sommaire.html",
            moyennes_par_champ={},
            moyenne_generale=0.0,
            moyenne_preliminaire_confirmee=0.0,
            grand_totals={
                "total_enseignants_tp": 0,
                "total_periodes_choisies_tp": 0.0,
                "total_periodes_magiques": 0.0,
            },
        )

    annee_id = g.annee_active["annee_id"]
    _, moyennes_champs, moyenne_gen, moyenne_prelim_conf, grand_totals_data = (
        calculer_donnees_sommaire(annee_id)
    )

    return render_template(
        "page_sommaire.html",
        moyennes_par_champ=moyennes_champs,
        moyenne_generale=moyenne_gen,
        moyenne_preliminaire_confirmee=moyenne_prelim_conf,
        grand_totals=grand_totals_data,
    )


@bp.route("/detail_taches")
@admin_required
def page_detail_taches() -> str:
    """Affiche la page de détail des tâches par enseignant pour l'année active."""
    if not g.annee_active:
        flash(
            "Aucune année scolaire n'est disponible. Les détails ne peuvent "
            "être affichés.",
            "warning",
        )
        return render_template("detail_taches.html", enseignants_par_champ=[])

    annee_id = g.annee_active["annee_id"]
    enseignants_par_champ_data, _, _, _, _ = calculer_donnees_sommaire(annee_id)

    return render_template(
        "detail_taches.html", enseignants_par_champ=enseignants_par_champ_data
    )


@bp.route("/donnees")
@admin_required
def page_administration_donnees() -> str:
    """Affiche la page d'administration des données pour l'année active."""
    cours_par_champ_data = {}
    enseignants_par_champ_data = {}

    if g.annee_active:
        annee_id = g.annee_active["annee_id"]
        cours_par_champ_data = db.get_all_cours_grouped_by_champ(annee_id)
        enseignants_par_champ_data = db.get_all_enseignants_grouped_by_champ(annee_id)
    else:
        flash(
            "Aucune année scolaire active. Veuillez en créer une pour gérer les données.",
            "warning",
        )

    return render_template(
        "administration_donnees.html",
        cours_par_champ=cours_par_champ_data,
        enseignants_par_champ=enseignants_par_champ_data,
        tous_les_champs=db.get_all_champs(),
        tous_les_financements=db.get_all_financements(),
    )


@bp.route("/utilisateurs")
@admin_required
def page_administration_utilisateurs() -> str:
    """Affiche la page d'administration des utilisateurs (indépendante de l'année)."""
    return render_template(
        "administration_utilisateurs.html",
        users=db.get_all_users_with_access_info(),
        all_champs=db.get_all_champs(),
    )


# --- API ENDPOINTS (JSON) ---

# --- API pour la gestion des années scolaires ---


@bp.route("/api/annees/creer", methods=["POST"])
@admin_api_required
def api_creer_annee() -> Any:
    """API pour créer une nouvelle année scolaire."""
    data = request.get_json()
    if not data or not (libelle := data.get("libelle", "").strip()):
        return (
            jsonify({"success": False, "message": "Le libellé de l'année est requis."}),
            400,
        )

    new_annee = db.create_annee_scolaire(libelle)
    if new_annee:
        if not g.annee_courante:
            db.set_annee_courante(new_annee["annee_id"])
            new_annee["est_courante"] = True
        current_app.logger.info(
            f"Année scolaire '{libelle}' créée avec ID {new_annee['annee_id']}."
        )
        return (
            jsonify(
                {"success": True, "message": f"Année '{libelle}' créée.", "annee": new_annee}
            ),
            201,
        )

    return (
        jsonify({"success": False, "message": f"L'année '{libelle}' existe déjà."}),
        409,
    )


@bp.route("/api/annees/changer_active", methods=["POST"])
@admin_api_required
def api_changer_annee_active() -> Any:
    """API pour changer l'année de travail de l'admin (stockée en session)."""
    data = request.get_json()
    if not data or not (annee_id := data.get("annee_id")):
        return jsonify({"success": False, "message": "ID de l'année manquant."}), 400

    session["annee_scolaire_id"] = annee_id
    annee_selectionnee = next(
        (annee for annee in g.toutes_les_annees if annee["annee_id"] == annee_id),
        None,
    )
    if annee_selectionnee:
        current_app.logger.info(
            f"Année de travail changée pour l'admin '{current_user.username}' : "
            f"'{annee_selectionnee['libelle_annee']}'."
        )
    return jsonify({"success": True, "message": "Année de travail changée."})


@bp.route("/api/annees/set_courante", methods=["POST"])
@admin_api_required
def api_set_annee_courante() -> Any:
    """API pour définir l'année courante pour toute l'application."""
    data = request.get_json()
    if not data or not (annee_id := data.get("annee_id")):
        return jsonify({"success": False, "message": "ID de l'année manquant."}), 400

    if db.set_annee_courante(annee_id):
        annee_maj = next(
            (annee for annee in g.toutes_les_annees if annee["annee_id"] == annee_id),
            None,
        )
        if annee_maj:
            current_app.logger.info(
                "Année courante de l'application définie sur : "
                f"'{annee_maj['libelle_annee']}'."
            )
        return jsonify({"success": True, "message": "Nouvelle année courante définie."})

    return (
        jsonify({"success": False, "message": "Erreur lors de la mise à jour."}),
        500,
    )


# --- API adaptées pour l'année scolaire ---


@bp.route("/api/sommaire/donnees", methods=["GET"])
@admin_api_required
def api_get_donnees_sommaire() -> Any:
    """API pour récupérer les données du sommaire pour l'année active."""
    if not g.annee_active:
        current_app.logger.warning(
            "API sommaire: Aucune année active, retour de données vides."
        )
        return jsonify(
            enseignants_par_champ=[],
            moyennes_par_champ={},
            moyenne_generale=0.0,
            moyenne_preliminaire_confirmee=0.0,
            grand_totals={
                "total_enseignants_tp": 0,
                "total_periodes_choisies_tp": 0.0,
                "total_periodes_magiques": 0.0,
            },
        )

    annee_id = g.annee_active["annee_id"]
    (
        enseignants_groupes,
        moyennes_champs,
        moyenne_gen,
        moyenne_prelim_conf,
        grand_totals_data,
    ) = calculer_donnees_sommaire(annee_id)
    return jsonify(
        enseignants_par_champ=enseignants_groupes,
        moyennes_par_champ=moyennes_champs,
        moyenne_generale=moyenne_gen,
        moyenne_preliminaire_confirmee=moyenne_prelim_conf,
        grand_totals=grand_totals_data,
    )


@bp.route("/api/champs/<string:champ_no>/basculer_verrou", methods=["POST"])
@admin_api_required
def api_basculer_verrou_champ(champ_no: str) -> Any:
    """Bascule le statut de verrouillage d'un champ pour l'année active."""
    if not g.annee_active:
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Aucune année scolaire active pour effectuer cette action.",
                }
            ),
            400,
        )

    annee_id = g.annee_active["annee_id"]
    nouveau_statut = db.toggle_champ_annee_lock_status(champ_no, annee_id)

    if nouveau_statut is None:
        return (
            jsonify(
                {
                    "success": False,
                    "message": f"Impossible de modifier le verrou du champ {champ_no}.",
                }
            ),
            500,
        )

    verrou_text = "verrouillé" if nouveau_statut else "déverrouillé"
    message = f"Le champ {champ_no} a été {verrou_text} pour l'année en cours."
    current_app.logger.info(message)
    return jsonify(
        {"success": True, "message": message, "est_verrouille": nouveau_statut}
    )


@bp.route("/api/champs/<string:champ_no>/basculer_confirmation", methods=["POST"])
@admin_api_required
def api_basculer_confirmation_champ(champ_no: str) -> Any:
    """Bascule le statut de confirmation d'un champ pour l'année active."""
    if not g.annee_active:
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Aucune année scolaire active pour effectuer cette action.",
                }
            ),
            400,
        )

    annee_id = g.annee_active["annee_id"]
    nouveau_statut = db.toggle_champ_annee_confirm_status(champ_no, annee_id)

    if nouveau_statut is None:
        return (
            jsonify(
                {
                    "success": False,
                    "message": f"Impossible de modifier la confirmation du champ {champ_no}.",
                }
            ),
            500,
        )

    conf_text = "confirmé" if nouveau_statut else "non confirmé"
    message = (
        f"Le champ {champ_no} a été marqué comme {conf_text} pour l'année en cours."
    )
    current_app.logger.info(message)
    return jsonify(
        {"success": True, "message": message, "est_confirme": nouveau_statut}
    )


@bp.route("/api/cours/creer", methods=["POST"])
@admin_api_required
def api_create_cours() -> Any:
    """API pour créer un nouveau cours dans l'année active."""
    if not g.annee_active:
        return jsonify({"success": False, "message": "Aucune année scolaire active."}), 400
    data = request.get_json()
    required_keys = [
        "codecours",
        "champno",
        "coursdescriptif",
        "nbperiodes",
        "nbgroupeinitial",
        "estcoursautre",
    ]
    if not data or not all(k in data for k in required_keys):
        return jsonify({"success": False, "message": "Données manquantes."}), 400
    try:
        new_cours = db.create_cours(data, g.annee_active["annee_id"])
        current_app.logger.info(
            f"Cours '{data['codecours']}' créé pour l'année "
            f"ID {g.annee_active['annee_id']}."
        )
        return (
            jsonify({"success": True, "message": "Cours créé.", "cours": new_cours}),
            201,
        )
    except psycopg2.errors.UniqueViolation:
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Ce code de cours existe déjà pour cette année.",
                }
            ),
            409,
        )
    except psycopg2.Error as e:
        current_app.logger.error(f"Erreur DB création cours: {e}")
        return (
            jsonify({"success": False, "message": f"Erreur de base de données: {e}"}),
            500,
        )


@bp.route("/api/cours/<path:code_cours>", methods=["GET"])
@admin_api_required
def api_get_cours_details(code_cours: str) -> Any:
    """API pour récupérer les détails d'un cours de l'année active."""
    if not g.annee_active:
        return jsonify({"success": False, "message": "Aucune année scolaire active."}), 404
    cours = db.get_cours_details(code_cours, g.annee_active["annee_id"])
    if not cours:
        return (
            jsonify({"success": False, "message": "Cours non trouvé pour cette année."}),
            404,
        )
    return jsonify({"success": True, "cours": cours})


@bp.route("/api/cours/<path:code_cours>/modifier", methods=["POST"])
@admin_api_required
def api_update_cours(code_cours: str) -> Any:
    """API pour modifier un cours de l'année active."""
    if not g.annee_active:
        return jsonify({"success": False, "message": "Aucune année scolaire active."}), 400
    data = request.get_json()
    required_keys = [
        "champno",
        "coursdescriptif",
        "nbperiodes",
        "nbgroupeinitial",
        "estcoursautre",
    ]
    if not data or not all(k in data for k in required_keys):
        return jsonify({"success": False, "message": "Données manquantes."}), 400
    try:
        updated_cours = db.update_cours(code_cours, g.annee_active["annee_id"], data)
        if not updated_cours:
            return (
                jsonify(
                    {"success": False, "message": "Cours non trouvé pour cette année."}
                ),
                404,
            )
        current_app.logger.info(
            f"Cours '{code_cours}' modifié pour l'année "
            f"ID {g.annee_active['annee_id']}."
        )
        return jsonify(
            {"success": True, "message": "Cours mis à jour.", "cours": updated_cours}
        )
    except psycopg2.Error as e:
        current_app.logger.error(f"Erreur DB modification cours: {e}")
        return (
            jsonify({"success": False, "message": f"Erreur de base de données: {e}"}),
            500,
        )


@bp.route("/api/cours/<path:code_cours>/supprimer", methods=["POST"])
@admin_api_required
def api_delete_cours(code_cours: str) -> Any:
    """API pour supprimer un cours de l'année active."""
    if not g.annee_active:
        return jsonify({"success": False, "message": "Aucune année scolaire active."}), 400
    success, message = db.delete_cours(code_cours, g.annee_active["annee_id"])
    status_code = 200 if success else 400
    if success:
        current_app.logger.info(
            f"Cours '{code_cours}' supprimé pour l'année "
            f"ID {g.annee_active['annee_id']}."
        )
    return jsonify({"success": success, "message": message}), status_code


@bp.route("/api/enseignants/creer", methods=["POST"])
@admin_api_required
def api_create_enseignant() -> Any:
    """API pour créer un nouvel enseignant dans l'année active."""
    if not g.annee_active:
        return jsonify({"success": False, "message": "Aucune année scolaire active."}), 400
    data = request.get_json()
    if not data or not all(
        k in data for k in ["nom", "prenom", "champno", "esttempsplein"]
    ):
        return jsonify({"success": False, "message": "Données manquantes."}), 400
    try:
        new_enseignant = db.create_enseignant(data, g.annee_active["annee_id"])
        current_app.logger.info(
            f"Enseignant '{data['nom']}' créé pour l'année "
            f"ID {g.annee_active['annee_id']}."
        )
        return (
            jsonify(
                {
                    "success": True,
                    "message": "Enseignant créé.",
                    "enseignant": new_enseignant,
                }
            ),
            201,
        )
    except psycopg2.errors.UniqueViolation:
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Cet enseignant (nom/prénom) existe déjà pour cette année.",
                }
            ),
            409,
        )
    except psycopg2.Error as e:
        current_app.logger.error(f"Erreur DB création enseignant: {e}")
        return (
            jsonify({"success": False, "message": f"Erreur de base de données: {e}"}),
            500,
        )


@bp.route("/api/enseignants/<int:enseignant_id>", methods=["GET"])
@admin_api_required
def api_get_enseignant_details(enseignant_id: int) -> Any:
    """API pour récupérer les détails d'un enseignant (ID est unique globalement)."""
    enseignant = db.get_enseignant_details(enseignant_id)
    # Les enseignants fictifs ne sont pas gérés via cette interface de modification
    if not enseignant or enseignant["estfictif"]:
        return (
            jsonify(
                {"success": False, "message": "Enseignant non trouvé ou non modifiable."}
            ),
            404,
        )
    return jsonify({"success": True, "enseignant": enseignant})


@bp.route("/api/enseignants/<int:enseignant_id>/modifier", methods=["POST"])
@admin_api_required
def api_update_enseignant(enseignant_id: int) -> Any:
    """API pour modifier un enseignant existant."""
    data = request.get_json()
    if not data or not all(
        k in data for k in ["nom", "prenom", "champno", "esttempsplein"]
    ):
        return jsonify({"success": False, "message": "Données manquantes."}), 400
    try:
        updated_enseignant = db.update_enseignant(enseignant_id, data)
        if not updated_enseignant:
            return (
                jsonify(
                    {
                        "success": False,
                        "message": "Enseignant non trouvé ou non modifiable.",
                    }
                ),
                404,
            )
        current_app.logger.info(f"Enseignant ID {enseignant_id} modifié.")
        return jsonify(
            {
                "success": True,
                "message": "Enseignant mis à jour.",
                "enseignant": updated_enseignant,
            }
        )
    except psycopg2.errors.UniqueViolation:
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Un enseignant avec ce nom/prénom existe déjà "
                    "pour l'année de cet enseignant.",
                }
            ),
            409,
        )
    except psycopg2.Error as e:
        current_app.logger.error(
            f"Erreur DB modification enseignant {enseignant_id}: {e}"
        )
        return (
            jsonify({"success": False, "message": f"Erreur de base de données: {e}"}),
            500,
        )


@bp.route("/api/enseignants/<int:enseignant_id>/supprimer", methods=["POST"])
@admin_api_required
def api_delete_enseignant(enseignant_id: int) -> Any:
    """API pour supprimer un enseignant (et ses attributions par CASCADE)."""
    enseignant = db.get_enseignant_details(enseignant_id)
    if not enseignant:
        return jsonify({"success": False, "message": "Enseignant non trouvé."}), 404
    if enseignant["estfictif"]:
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Impossible de supprimer un enseignant fictif.",
                }
            ),
            403,
        )

    if db.delete_enseignant(enseignant_id):
        current_app.logger.info(f"Enseignant ID {enseignant_id} supprimé.")
        return jsonify(
            {"success": True, "message": "Enseignant et ses attributions supprimés."}
        )
    return jsonify({"success": False, "message": "Échec de la suppression."}), 500


@bp.route("/importer_cours_excel", methods=["POST"])
@admin_required
def api_importer_cours_excel() -> Any:
    """Importe les cours depuis Excel pour l'année active, en écrasant les données."""
    if not g.annee_active:
        flash("Importation impossible : aucune année scolaire n'est active.", "error")
        return redirect(url_for("admin.page_administration_donnees"))

    annee_id = g.annee_active["annee_id"]
    annee_libelle = g.annee_active["libelle_annee"]

    if "fichier_cours" not in request.files:
        flash("Aucun fichier sélectionné.", "warning")
        return redirect(url_for("admin.page_administration_donnees"))

    file = request.files["fichier_cours"]
    if not file or not file.filename:
        flash("Aucun fichier valide sélectionné.", "warning")
        return redirect(url_for("admin.page_administration_donnees"))

    if not file.filename.endswith((".xlsx", ".xls")):
        flash("Format de fichier invalide. Utilisez un fichier .xlsx.", "error")
        return redirect(url_for("admin.page_administration_donnees"))

    nouveaux_cours = []
    try:
        workbook = openpyxl.load_workbook(file.stream)
        sheet = cast(Worksheet, workbook.active)
        if sheet.max_row <= 1:
            raise ValueError("Fichier Excel vide ou ne contenant que l'en-tête.")

        for row_idx, row in enumerate(sheet.iter_rows(min_row=2), start=2):
            values = [cell.value for cell in row]
            # Colonnes: 0:champ, 1:code, 2:N/A, 3:desc, 4:grp, 5:per, 6:autre, 7:financement
            if not any(v is not None and str(v).strip() != "" for v in values[:7]):
                continue

            (
                champ_no_raw,
                code_cours_raw,
                desc_raw,
                nb_grp_raw,
                nb_per_raw,
            ) = (values[0], values[1], values[3], values[4], values[5])
            est_autre_raw = values[6] if len(values) > 6 else None
            financement_code_raw = values[7] if len(values) > 7 else None

            if not all([champ_no_raw, code_cours_raw, desc_raw, nb_grp_raw, nb_per_raw]):
                flash(f"Ligne {row_idx}: Données manquantes.", "warning")
                continue

            try:
                est_autre = str(est_autre_raw).strip().upper() in (
                    "VRAI",
                    "TRUE",
                    "OUI",
                    "YES",
                    "1",
                )
                financement_code = (
                    str(financement_code_raw).strip() if financement_code_raw else None
                )

                nouveaux_cours.append(
                    {
                        "codecours": str(code_cours_raw).strip(),
                        "champno": str(champ_no_raw).strip(),
                        "coursdescriptif": str(desc_raw).strip(),
                        "nbperiodes": float(str(nb_per_raw).replace(",", ".")),
                        "nbgroupeinitial": int(float(str(nb_grp_raw).replace(",", "."))),
                        "estcoursautre": est_autre,
                        "financement_code": financement_code,
                    }
                )
            except (ValueError, TypeError) as ve:
                flash(f"Ligne {row_idx}: Erreur de type de données ({ve}).", "warning")
                continue

    except InvalidFileException:
        flash("Fichier Excel corrompu ou invalide.", "error")
        return redirect(url_for("admin.page_administration_donnees"))
    except ValueError as e_val:
        flash(str(e_val), "error")
        return redirect(url_for("admin.page_administration_donnees"))
    except Exception as e_gen:
        current_app.logger.error(
            f"Erreur imprévue lecture Excel cours: {e_gen}", exc_info=True
        )
        flash(f"Erreur inattendue: {e_gen}", "error")
        return redirect(url_for("admin.page_administration_donnees"))

    if not nouveaux_cours:
        flash("Aucun cours valide trouvé dans le fichier.", "warning")
        return redirect(url_for("admin.page_administration_donnees"))

    conn = cast(connection | None, db.get_db())
    if not conn:
        flash("Erreur de connexion à la base de données.", "error")
        return redirect(url_for("admin.page_administration_donnees"))

    try:
        with conn.cursor():
            nb_attr_supp = db.delete_all_attributions_for_year(annee_id)
            nb_cours_supp = db.delete_all_cours_for_year(annee_id)
            for cours in nouveaux_cours:
                # La création se fait via la fonction DAO pour centraliser la logique
                db.create_cours(cours, annee_id)
            conn.commit()
        flash(
            f"{len(nouveaux_cours)} cours importés pour '{annee_libelle}'. "
            f"Anciens cours ({nb_cours_supp}) et attributions ({nb_attr_supp}) "
            "supprimés.",
            "success",
        )
    except psycopg2.Error as e_db:
        conn.rollback()
        current_app.logger.error(f"Erreur DB importation cours: {e_db}", exc_info=True)
        flash(f"Erreur base de données: {e_db}. Importation annulée.", "error")

    return redirect(url_for("admin.page_administration_donnees"))


@bp.route("/importer_enseignants_excel", methods=["POST"])
@admin_required
def api_importer_enseignants_excel() -> Any:
    """Importe les enseignants depuis Excel pour l'année active, en écrasant les données."""
    if not g.annee_active:
        flash("Importation impossible : aucune année scolaire n'est active.", "error")
        return redirect(url_for("admin.page_administration_donnees"))

    annee_id = g.annee_active["annee_id"]
    annee_libelle = g.annee_active["libelle_annee"]

    if "fichier_enseignants" not in request.files:
        flash("Aucun fichier sélectionné.", "warning")
        return redirect(url_for("admin.page_administration_donnees"))

    file = request.files["fichier_enseignants"]
    if not file or not file.filename:
        flash("Aucun fichier valide sélectionné.", "warning")
        return redirect(url_for("admin.page_administration_donnees"))

    if not file.filename.endswith((".xlsx", ".xls")):
        flash("Format de fichier invalide. Utilisez un fichier .xlsx.", "error")
        return redirect(url_for("admin.page_administration_donnees"))

    nouveaux_enseignants = []
    try:
        workbook = openpyxl.load_workbook(file.stream)
        sheet = cast(Worksheet, workbook.active)
        if sheet.max_row <= 1:
            raise ValueError("Fichier Excel vide ou ne contenant que l'en-tête.")

        for row_idx, row in enumerate(sheet.iter_rows(min_row=2), start=2):
            values = [cell.value for cell in row]
            if not any(v is not None and str(v).strip() != "" for v in values[:4]):
                continue

            champ_no_raw, nom_raw, prenom_raw, temps_plein_raw = (
                values[0],
                values[1],
                values[2],
                values[3],
            )

            if not all([champ_no_raw, nom_raw, prenom_raw, temps_plein_raw is not None]):
                flash(f"Ligne enseignant {row_idx}: Données manquantes.", "warning")
                continue

            try:
                nom_clean, prenom_clean = str(nom_raw).strip(), str(prenom_raw).strip()
                if not nom_clean or not prenom_clean:
                    continue
                nouveaux_enseignants.append(
                    {
                        "nomcomplet": f"{prenom_clean} {nom_clean}",
                        "nom": nom_clean,
                        "prenom": prenom_clean,
                        "champno": str(champ_no_raw).strip(),
                        "esttempsplein": str(temps_plein_raw).strip().upper()
                        in ("VRAI", "TRUE", "OUI", "YES", "1"),
                    }
                )
            except (ValueError, TypeError) as ve_ens:
                flash(f"Ligne {row_idx}: Erreur de conversion ({ve_ens}).", "warning")
                continue

    except InvalidFileException:
        flash("Fichier Excel des enseignants corrompu ou invalide.", "error")
        return redirect(url_for("admin.page_administration_donnees"))
    except ValueError as e_val_ens:
        flash(str(e_val_ens), "error")
        return redirect(url_for("admin.page_administration_donnees"))
    except Exception as e_gen_ens:
        current_app.logger.error(f"Erreur lecture Excel: {e_gen_ens}", exc_info=True)
        flash(f"Erreur inattendue: {e_gen_ens}", "error")
        return redirect(url_for("admin.page_administration_donnees"))

    if not nouveaux_enseignants:
        flash("Aucun enseignant valide trouvé dans le fichier.", "warning")
        return redirect(url_for("admin.page_administration_donnees"))

    conn = cast(connection | None, db.get_db())
    if not conn:
        flash("Erreur de connexion à la base de données.", "error")
        return redirect(url_for("admin.page_administration_donnees"))

    try:
        with conn.cursor():
            nb_attr_supp_ens = db.delete_all_attributions_for_year(annee_id)
            nb_ens_supp = db.delete_all_enseignants_for_year(annee_id)
            for ens in nouveaux_enseignants:
                db.create_enseignant(ens, annee_id)
            conn.commit()
        flash(
            f"{len(nouveaux_enseignants)} enseignants importés pour '{annee_libelle}'. "
            f"Anciens enseignants ({nb_ens_supp}) et attributions ({nb_attr_supp_ens}) "
            "supprimés.",
            "success",
        )
    except psycopg2.Error as e_db_ens:
        conn.rollback()
        current_app.logger.error(
            f"Erreur DB importation enseignants: {e_db_ens}", exc_info=True
        )
        flash(f"Erreur base de données: {e_db_ens}. Importation annulée.", "error")

    return redirect(url_for("admin.page_administration_donnees"))


@bp.route("/exporter_taches_excel")
@admin_required
def exporter_taches_excel() -> Any:
    """Exporte toutes les tâches attribuées pour l'année active dans un fichier Excel."""
    if not g.annee_active:
        flash("Exportation impossible : aucune année scolaire n'est active.", "error")
        return redirect(url_for("admin.page_sommaire"))

    annee_id = g.annee_active["annee_id"]
    annee_libelle = g.annee_active["libelle_annee"]
    attributions_raw = db.get_all_attributions_for_export(annee_id)

    if not attributions_raw:
        flash(f"Aucune tâche attribuée pour '{annee_libelle}'.", "warning")
        return redirect(url_for("admin.page_sommaire"))

    attributions_par_champ: dict[str, dict[str, Any]] = {}
    for attr in attributions_raw:
        champ_no = attr["champno"]
        if champ_no not in attributions_par_champ:
            attributions_par_champ[champ_no] = {
                "nom": attr["champnom"],
                "attributions": [],
            }
        attributions_par_champ[champ_no]["attributions"].append(attr)

    mem_file = exports.generer_export_taches(attributions_par_champ)
    filename = f"export_taches_{annee_libelle}.xlsx"
    current_app.logger.info(f"Génération du fichier d'export '{filename}'.")

    return Response(
        mem_file,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@bp.route("/exporter_periodes_restantes_excel")
@admin_required
def exporter_periodes_restantes_excel() -> Any:
    """Exporte les périodes non attribuées (restantes) pour l'année active."""
    if not g.annee_active:
        flash("Exportation impossible : aucune année scolaire n'est active.", "error")
        return redirect(url_for("admin.page_sommaire"))

    annee_id = g.annee_active["annee_id"]
    annee_libelle = g.annee_active["libelle_annee"]
    periodes_restantes_raw = db.get_periodes_restantes_for_export(annee_id)

    if not periodes_restantes_raw:
        flash(f"Aucune période restante pour '{annee_libelle}'.", "warning")
        return redirect(url_for("admin.page_sommaire"))

    periodes_par_champ: dict[str, dict[str, Any]] = {}
    for periode in periodes_restantes_raw:
        champ_no = periode["champno"]
        if champ_no not in periodes_par_champ:
            periodes_par_champ[champ_no] = {
                "nom": periode["champnom"],
                "periodes": [],
            }
        periodes_par_champ[champ_no]["periodes"].append(periode)

    mem_file = exports.generer_export_periodes_restantes(periodes_par_champ)
    filename = f"export_periodes_restantes_{annee_libelle}.xlsx"
    current_app.logger.info(f"Génération de l'export '{filename}'.")

    return Response(
        mem_file,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@bp.route("/exporter_org_scolaire_excel")
@admin_required
def exporter_org_scolaire_excel() -> Any:
    """Exporte les données pour l'organisation scolaire pour l'année active."""
    if not g.annee_active:
        flash("Exportation impossible : aucune année scolaire n'est active.", "error")
        return redirect(url_for("admin.page_sommaire"))

    annee_id = g.annee_active["annee_id"]
    annee_libelle = g.annee_active["libelle_annee"]

    # Étape 1: Récupérer les types de financement pour les en-têtes
    tous_les_financements = db.get_all_financements()
    headers_financement = [(f["code"], f["libelle"]) for f in tous_les_financements]
    codes_financement_valides = {code for code, _libelle in headers_financement}

    # Étape 2: Récupérer les données brutes
    donnees_raw = db.get_data_for_org_scolaire_export(annee_id)
    if not donnees_raw:
        flash(f"Aucune donnée à exporter pour '{annee_libelle}'.", "warning")
        return redirect(url_for("admin.page_sommaire"))

    # Étape 3: Pivoter les données en Python
    pivot_data: dict[str, dict[str, Any]] = {}

    for item in donnees_raw:
        champ_no = item["champno"]
        # Clé unique pour chaque enseignant/tâche au sein d'un champ
        enseignant_key = (
            f"fictif-{item['nomcomplet']}"
            if item["estfictif"]
            else f"reel-{item['nom']}-{item['prenom']}"
        )

        if champ_no not in pivot_data:
            pivot_data[champ_no] = {}
        if enseignant_key not in pivot_data[champ_no]:
            pivot_data[champ_no][enseignant_key] = {
                "nom": item["nom"],
                "prenom": item["prenom"],
                "nomcomplet": item["nomcomplet"],
                "estfictif": item["estfictif"],
                "champnom": item["champnom"],
                "periodes": {code: 0.0 for code, _libelle in headers_financement},
                "soutien_se": 0.0,
                "ressource_autre": 0.0,
                "enseignant_ressource": 0.0,
                "autres": 0.0,
            }

        # Distribution des périodes dans les bonnes "colonnes"
        total_p = float(item["total_periodes"] or 0.0)
        code_cours = item["codecours"]
        if item["financement_code"] in codes_financement_valides:
            pivot_data[champ_no][enseignant_key]["periodes"][item["financement_code"]] += total_p
        elif code_cours and code_cours.startswith("SOU"):
            pivot_data[champ_no][enseignant_key]["soutien_se"] += total_p
        elif code_cours and code_cours.startswith("RESSA"):
            pivot_data[champ_no][enseignant_key]["ressource_autre"] += total_p
        elif code_cours and code_cours.startswith("RESS_"):
            pivot_data[champ_no][enseignant_key]["enseignant_ressource"] += total_p
        else:
            pivot_data[champ_no][enseignant_key]["autres"] += total_p

    # Conversion de la structure pivotée vers le format attendu par la fonction d'export
    donnees_par_champ: dict[str, dict[str, Any]] = {}
    for champ_no, enseignants in pivot_data.items():
        if champ_no not in donnees_par_champ:
            donnees_par_champ[champ_no] = {
                "nom": next(iter(enseignants.values()))["champnom"],
                "donnees": [],
            }
        donnees_par_champ[champ_no]["donnees"] = list(enseignants.values())

    # Étape 4: Générer le fichier Excel
    mem_file = exports.generer_export_org_scolaire(donnees_par_champ, headers_financement)
    filename = f"export_org_scolaire_{annee_libelle}.xlsx"
    current_app.logger.info(f"Génération de l'export '{filename}'.")

    return Response(
        mem_file,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


# --- API pour la gestion des Types de Financement ---


@bp.route("/api/financements", methods=["GET"])
@admin_api_required
def api_get_all_financements() -> Any:
    """Récupère tous les types de financement."""
    financements = db.get_all_financements()
    return jsonify(financements)


@bp.route("/api/financements/creer", methods=["POST"])
@admin_api_required
def api_create_financement() -> Any:
    """Crée un nouveau type de financement."""
    data = request.get_json()
    if (
        not data
        or not (code := data.get("code", "").strip())
        or not (libelle := data.get("libelle", "").strip())
    ):
        return jsonify({"success": False, "message": "Code et libellé requis."}), 400

    try:
        new_financement = db.create_financement(code, libelle)
        current_app.logger.info(f"Type de financement '{code}' créé.")
        return (
            jsonify(
                {
                    "success": True,
                    "message": "Type de financement créé.",
                    "financement": new_financement,
                }
            ),
            201,
        )
    except psycopg2.errors.UniqueViolation:
        return (
            jsonify({"success": False, "message": "Ce code de financement existe déjà."}),
            409,
        )
    except psycopg2.Error as e:
        current_app.logger.error(f"Erreur DB création financement: {e}")
        return jsonify({"success": False, "message": "Erreur de base de données."}), 500


@bp.route("/api/financements/<code>/modifier", methods=["POST"])
@admin_api_required
def api_update_financement(code: str) -> Any:
    """Met à jour le libellé d'un type de financement (le code est immuable)."""
    data = request.get_json()
    if not data or not (libelle := data.get("libelle", "").strip()):
        return jsonify({"success": False, "message": "Libellé requis."}), 400

    try:
        updated = db.update_financement(code, libelle)
        if not updated:
            return (
                jsonify({"success": False, "message": "Financement non trouvé."}),
                404,
            )
        current_app.logger.info(f"Type de financement '{code}' mis à jour.")
        return jsonify(
            {
                "success": True,
                "message": "Type de financement mis à jour.",
                "financement": updated,
            }
        )
    except psycopg2.Error as e:
        db_conn = db.get_db()
        if db_conn:
            db_conn.rollback()
        current_app.logger.error(f"Erreur DB modif. financement: {e}", exc_info=True)
        return jsonify({"success": False, "message": "Erreur de base de données."}), 500


@bp.route("/api/financements/<code>/supprimer", methods=["POST"])
@admin_api_required
def api_delete_financement(code: str) -> Any:
    """Supprime un type de financement."""
    success, message = db.delete_financement(code)
    status_code = 200 if success else 400
    if success:
        current_app.logger.info(f"Type de financement '{code}' supprimé.")
    return jsonify({"success": success, "message": message}), status_code


# --- API non modifiées car indépendantes de l'année ---
@bp.route("/api/utilisateurs", methods=["GET"])
@admin_api_required
def api_get_all_users() -> Any:
    """Récupère tous les utilisateurs avec des informations sur leur nombre."""
    return jsonify(
        users=db.get_all_users_with_access_info(), admin_count=db.get_admin_count()
    )


@bp.route("/api/utilisateurs/creer", methods=["POST"])
@admin_api_required
def api_create_user() -> Any:
    """Crée un nouvel utilisateur."""
    data = request.get_json()
    if (
        not data
        or not (username := data.get("username", "").strip())
        or not (password := data.get("password", "").strip())
    ):
        return (
            jsonify(
                {"success": False, "message": "Nom d'utilisateur et mdp requis."}
            ),
            400,
        )
    if len(password) < 6:
        return (
            jsonify(
                {"success": False, "message": "Le mdp doit faire >= 6 caractères."}
            ),
            400,
        )

    is_admin = data.get("is_admin", False)
    allowed_champs = data.get("allowed_champs", [])
    user = db.create_user(username, generate_password_hash(password), is_admin)

    if not user:
        return (
            jsonify({"success": False, "message": "Ce nom d'utilisateur est déjà pris."}),
            409,
        )

    if not is_admin and allowed_champs:
        if not db.update_user_champ_access(user["id"], allowed_champs):
            db.delete_user_data(user["id"])
            current_app.logger.error(f"Échec droits pour nouvel user {username}.")
            return (
                jsonify({"success": False, "message": "Erreur d'attribution des accès."}),
                500,
            )

    current_app.logger.info(f"Utilisateur '{username}' créé avec ID {user['id']}.")
    return (
        jsonify(
            {"success": True, "message": f"Utilisateur '{username}' créé!", "user_id": user["id"]}
        ),
        201,
    )


@bp.route("/api/utilisateurs/<int:user_id>/update_access", methods=["POST"])
@admin_api_required
def api_update_user_access(user_id: int) -> Any:
    """Met à jour les accès aux champs pour un utilisateur non-admin."""
    data = request.get_json()
    if not data or not isinstance(champ_nos := data.get("champ_nos"), list):
        return jsonify({"success": False, "message": "Données invalides."}), 400

    target_user = db.get_user_by_id(user_id)
    if not target_user:
        return jsonify({"success": False, "message": "Utilisateur non trouvé."}), 404
    if target_user["is_admin"]:
        return (
            jsonify({"success": False, "message": "Accès admin non modifiables ici."}),
            403,
        )

    if db.update_user_champ_access(user_id, champ_nos):
        current_app.logger.info(f"Accès mis à jour pour l'utilisateur ID {user_id}.")
        return jsonify({"success": True, "message": "Accès mis à jour."})

    current_app.logger.error(f"Échec MAJ accès pour l'utilisateur ID {user_id}.")
    return jsonify({"success": False, "message": "Erreur lors de la mise à jour."}), 500


@bp.route("/api/utilisateurs/<int:user_id>/delete", methods=["POST"])
@admin_api_required
def api_delete_user(user_id: int) -> Any:
    """Supprime un utilisateur."""
    if user_id == current_user.id:
        return (
            jsonify({"success": False, "message": "Vous ne pouvez pas vous supprimer."}),
            403,
        )

    target_user = db.get_user_by_id(user_id)
    if not target_user:
        return jsonify({"success": False, "message": "Utilisateur non trouvé."}), 404

    if target_user["is_admin"] and db.get_admin_count() <= 1:
        return (
            jsonify(
                {"success": False, "message": "Impossible de supprimer le dernier admin."}
            ),
            403,
        )

    if db.delete_user_data(user_id):
        current_app.logger.info(
            f"User ID {user_id} ('{target_user['username']}') supprimé par '{current_user.username}'."
        )
        return jsonify({"success": True, "message": "Utilisateur supprimé."})

    current_app.logger.error(f"Échec suppression user ID {user_id}.")
    return jsonify({"success": False, "message": "Échec de la suppression."}), 500


@bp.route("/api/cours/reassigner_champ", methods=["POST"])
@admin_api_required
def api_reassigner_cours_champ() -> Any:
    """API pour réassigner un cours à un nouveau champ, pour l'année active."""
    if not g.annee_active:
        return jsonify({"success": False, "message": "Aucune année scolaire active."}), 400

    data = request.get_json()
    if (
        not data
        or not (code_cours := data.get("code_cours"))
        or not (nouveau_champ_no := data.get("nouveau_champ_no"))
    ):
        return jsonify({"success": False, "message": "Données manquantes."}), 400

    result = db.reassign_cours_to_champ(
        code_cours, g.annee_active["annee_id"], nouveau_champ_no
    )
    if result:
        current_app.logger.info(
            f"Cours '{code_cours}' réassigné au champ '{nouveau_champ_no}' "
            f"pour l'année ID {g.annee_active['annee_id']}."
        )
        return jsonify(
            success=True,
            message=f"Cours '{code_cours}' réassigné au champ '{nouveau_champ_no}'.",
            **result,
        )

    current_app.logger.warning(
        f"Échec réassignation cours '{code_cours}' vers champ '{nouveau_champ_no}'."
    )
    return (
        jsonify({"success": False, "message": "Impossible de réassigner le cours."}),
        500,
    )


@bp.route("/api/cours/reassigner_financement", methods=["POST"])
@admin_api_required
def api_reassigner_cours_financement() -> Any:
    """API pour réassigner un cours à un nouveau type de financement, pour l'année active."""
    if not g.annee_active:
        return jsonify({"success": False, "message": "Aucune année scolaire active."}), 400

    data = request.get_json()
    if not data or not (code_cours := data.get("code_cours")):
        return jsonify({"success": False, "message": "Données manquantes."}), 400

    # nouveau_financement_code peut être une chaîne vide, ce qui est valide (pour 'Aucun')
    nouveau_financement_code = data.get("nouveau_financement_code")
    # Une chaîne vide en JS doit devenir NULL en base de données.
    financement_a_stocker = nouveau_financement_code if nouveau_financement_code else None

    result = db.reassign_cours_to_financement(
        code_cours, g.annee_active["annee_id"], financement_a_stocker
    )
    if result:
        current_app.logger.info(
            f"Cours '{code_cours}' réassigné au financement '{financement_a_stocker}' "
            f"pour l'année ID {g.annee_active['annee_id']}."
        )
        return jsonify(
            success=True,
            message=f"Financement du cours '{code_cours}' mis à jour.",
        )

    current_app.logger.warning(
        f"Échec réassignation financement pour cours '{code_cours}'."
    )
    return (
        jsonify(
            {"success": False, "message": "Impossible de réassigner le financement."}
        ),
        500,
    )