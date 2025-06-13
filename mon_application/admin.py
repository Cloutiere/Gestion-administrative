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

    Cette fonction adopte une approche "centrée sur le champ" :
    1. Récupère tous les champs définis dans l'établissement.
    2. Initialise une structure de données pour chaque champ avec des statistiques à zéro.
    3. Met à jour ces statistiques en parcourant les enseignants de l'année active.
    Cela garantit que tous les champs sont présents dans le résultat, même ceux
    sans enseignant assigné pour l'année en cours.

    Retourne:
        Un tuple contenant :
        - La liste des enseignants groupés par champ (pour la page de détail).
        - Un dictionnaire des moyennes et totaux par champ, incluant les statuts.
        - La moyenne générale des périodes pour les enseignants à temps plein.
        - La moyenne "Préliminaire confirmée" (enseignants TP des champs confirmés).
        - Un dictionnaire contenant les totaux globaux pour le pied de tableau.
    """
    # Étape 1 : Récupérer toutes les données brutes nécessaires de la base de données.
    tous_les_champs = db.get_all_champs()
    statuts_champs = db.get_all_champ_statuses_for_year(annee_id)
    tous_enseignants_details = db.get_all_enseignants_avec_details(annee_id)

    # Étape 2 : Initialiser les structures de données en se basant sur TOUS les champs.
    # C'est le cœur de la correction pour garantir que chaque champ soit listé.
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

    # Structure pour la page de détail des tâches (doit aussi inclure tous les champs).
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

        # Mettre à jour les statistiques uniquement pour les enseignants pertinents.
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

    # Cette boucle s'exécute maintenant sur TOUS les champs.
    for data in moyennes_par_champ_calculees.values():
        nb_ens_tp = data["nb_enseignants_tp"]
        periodes_choisies_tp = data["periodes_choisies_tp"]

        data["moyenne"] = (
            (periodes_choisies_tp / nb_ens_tp) if nb_ens_tp > 0 else 0.0
        )
        data["periodes_magiques"] = periodes_choisies_tp - (nb_ens_tp * 24)

        # Agrégation pour les totaux du tableau
        total_enseignants_tp_etablissement += nb_ens_tp
        total_periodes_choisies_tp_etablissement += periodes_choisies_tp
        total_periodes_magiques_etablissement += data["periodes_magiques"]

        # Agrégation pour les moyennes générales
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
            "Aucune année scolaire n'est disponible. Veuillez en créer une dans la section 'Données'.",
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
    # La liste des enseignants n'est plus directement utilisée par ce template, mais est calculée pour d'autres usages.
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
            "Aucune année scolaire n'est disponible. Les détails ne peuvent être affichés.",
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
            jsonify({"success": True, "message": f"Année '{libelle}' créée.", "annee": new_annee}),
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
            f"Année de travail changée pour l'admin '{current_user.username}' : '{annee_selectionnee['libelle_annee']}'."
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
                f"Année courante de l'application définie sur : '{annee_maj['libelle_annee']}'."
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

    message = f"Le champ {champ_no} a été {'verrouillé' if nouveau_statut else 'déverrouillé'} pour l'année en cours."
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

    message = f"Le champ {champ_no} a été marqué comme {'confirmé' if nouveau_statut else 'non confirmé'} pour l'année en cours."
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
    if not data or not all(
        k in data
        for k in [
            "codecours",
            "champno",
            "coursdescriptif",
            "nbperiodes",
            "nbgroupeinitial",
        ]
    ):
        return jsonify({"success": False, "message": "Données manquantes."}), 400
    try:
        new_cours = db.create_cours(data, g.annee_active["annee_id"])
        current_app.logger.info(
            f"Cours '{data['codecours']}' créé pour l'année ID {g.annee_active['annee_id']}."
        )
        return jsonify({"success": True, "message": "Cours créé.", "cours": new_cours}), 201
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
        return jsonify({"success": False, "message": f"Erreur de base de données: {e}"}), 500


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
    if not data or not all(
        k in data
        for k in ["champno", "coursdescriptif", "nbperiodes", "nbgroupeinitial"]
    ):
        return jsonify({"success": False, "message": "Données manquantes."}), 400
    try:
        updated_cours = db.update_cours(
            code_cours, g.annee_active["annee_id"], data
        )
        if not updated_cours:
            return (
                jsonify(
                    {"success": False, "message": "Cours non trouvé pour cette année."}
                ),
                404,
            )
        current_app.logger.info(
            f"Cours '{code_cours}' modifié pour l'année ID {g.annee_active['annee_id']}."
        )
        return jsonify(
            {"success": True, "message": "Cours mis à jour.", "cours": updated_cours}
        )
    except psycopg2.Error as e:
        current_app.logger.error(f"Erreur DB modification cours: {e}")
        return jsonify({"success": False, "message": f"Erreur de base de données: {e}"}), 500


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
            f"Cours '{code_cours}' supprimé pour l'année ID {g.annee_active['annee_id']}."
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
            f"Enseignant '{data['nom']}' créé pour l'année ID {g.annee_active['annee_id']}."
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
        return jsonify({"success": False, "message": f"Erreur de base de données: {e}"}), 500


@bp.route("/api/enseignants/<int:enseignant_id>", methods=["GET"])
@admin_api_required
def api_get_enseignant_details(enseignant_id: int) -> Any:
    """API pour récupérer les détails d'un enseignant (ID est unique globalement)."""
    enseignant = db.get_enseignant_details(enseignant_id)
    # Les enseignants fictifs ne sont pas gérés via cette interface de modification standard
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
                        "message": "Enseignant non trouvé ou non modifiable (ex: fictif).",
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
                    "message": "Un enseignant avec ce nom/prénom existe déjà pour l'année de cet enseignant.",
                }
            ),
            409,
        )
    except psycopg2.Error as e:
        current_app.logger.error(f"Erreur DB modification enseignant {enseignant_id}: {e}")
        return jsonify({"success": False, "message": f"Erreur de base de données: {e}"}), 500


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
                    "message": "Impossible de supprimer un enseignant fictif via cette interface.",
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
    """Importe les cours depuis Excel pour l'année active, en écrasant les données existantes pour cette année."""
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
        flash("Aucun fichier valide sélectionné ou nom de fichier manquant.", "warning")
        return redirect(url_for("admin.page_administration_donnees"))

    if not file.filename.endswith((".xlsx", ".xls")):
        flash(
            "Format de fichier invalide. Veuillez utiliser un fichier Excel (.xlsx ou .xls).",
            "error",
        )
        return redirect(url_for("admin.page_administration_donnees"))

    nouveaux_cours = []
    try:
        workbook = openpyxl.load_workbook(file.stream)
        sheet = cast(Worksheet, workbook.active)
        if sheet.max_row <= 1:
            raise ValueError("Fichier Excel vide ou ne contient que l'en-tête.")

        for row_idx, row in enumerate(sheet.iter_rows(min_row=2), start=2):
            values = [cell.value for cell in row]
            if not any(v is not None and str(v).strip() != "" for v in values[:6]):
                current_app.logger.debug(
                    f"Ligne {row_idx} ignorée (vide ou non pertinente)."
                )
                continue

            champ_no_raw = values[0]
            code_cours_raw = values[1]
            desc_raw = values[3]
            nb_grp_raw = values[4]
            nb_per_raw = values[5]
            est_autre_raw = values[7] if len(values) > 7 else None

            if not all(
                [
                    champ_no_raw,
                    code_cours_raw,
                    desc_raw,
                    nb_grp_raw is not None,
                    nb_per_raw is not None,
                ]
            ):
                flash(
                    f"Ligne {row_idx}: Données manquantes. Vérifiez ChampNo, CodeCours, Descriptif, NbGroupes, NbPériodes.",
                    "warning",
                )
                continue

            try:
                champ_no = str(champ_no_raw).strip()
                code_cours = str(code_cours_raw).strip()
                desc = str(desc_raw).strip()
                nb_grp = int(float(str(nb_grp_raw).replace(",", ".")))
                nb_per = float(str(nb_per_raw).replace(",", "."))
                est_autre = (
                    str(est_autre_raw).strip().upper()
                    in ("VRAI", "TRUE", "OUI", "YES", "1")
                    if est_autre_raw is not None
                    else False
                )
            except (ValueError, TypeError) as ve:
                flash(
                    f"Ligne {row_idx}: Erreur de type de données ({ve}). Vérifiez les nombres et le format 'VRAI/FAUX'.",
                    "warning",
                )
                continue

            nouveaux_cours.append(
                {
                    "codecours": code_cours,
                    "champno": champ_no,
                    "coursdescriptif": desc,
                    "nbperiodes": nb_per,
                    "nbgroupeinitial": nb_grp,
                    "estcoursautre": est_autre,
                }
            )

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
        flash(
            f"Erreur inattendue lors de la lecture du fichier Excel : {e_gen}", "error"
        )
        return redirect(url_for("admin.page_administration_donnees"))

    if not nouveaux_cours:
        flash(
            "Aucun cours valide trouvé dans le fichier après traitement. Vérifiez le contenu et les messages d'avertissement.",
            "warning",
        )
        return redirect(url_for("admin.page_administration_donnees"))

    conn = cast(connection, db.get_db())
    if not conn:
        flash("Erreur de connexion à la base de données.", "error")
        return redirect(url_for("admin.page_administration_donnees"))

    try:
        with conn.cursor() as cur:
            current_app.logger.info(
                f"Début transaction importation cours pour l'année ID {annee_id}."
            )
            nb_attr_supp = db.delete_all_attributions_for_year(annee_id)
            current_app.logger.info(f"{nb_attr_supp} attributions supprimées.")

            nb_cours_supp = db.delete_all_cours_for_year(annee_id)
            current_app.logger.info(f"{nb_cours_supp} cours supprimés.")

            current_app.logger.info(
                f"Insertion de {len(nouveaux_cours)} nouveaux cours..."
            )
            for cours in nouveaux_cours:
                cur.execute(
                    """INSERT INTO Cours (annee_id, CodeCours, ChampNo, CoursDescriptif, NbPeriodes, NbGroupeInitial, EstCoursAutre)
                       VALUES (%(annee_id)s, %(codecours)s, %(champno)s, %(coursdescriptif)s, %(nbperiodes)s, %(nbgroupeinitial)s,
                       %(estcoursautre)s);""",
                    {**cours, "annee_id": annee_id},
                )
            conn.commit()
        flash(
            f"{len(nouveaux_cours)} cours importés pour l'année '{annee_libelle}'. "
            f"Anciens cours ({nb_cours_supp}) et attributions ({nb_attr_supp}) de cette année supprimés.",
            "success",
        )
    except psycopg2.Error as e_db:
        conn.rollback()
        current_app.logger.error(f"Erreur DB importation cours: {e_db}", exc_info=True)
        flash(
            f"Erreur base de données: {e_db}. L'importation a été annulée.", "error"
        )
    except Exception as e_final:
        conn.rollback()
        current_app.logger.error(
            f"Erreur inconnue durant transaction d'importation cours: {e_final}",
            exc_info=True,
        )
        flash(f"Erreur inconnue: {e_final}. L'importation a été annulée.", "error")

    return redirect(url_for("admin.page_administration_donnees"))


@bp.route("/importer_enseignants_excel", methods=["POST"])
@admin_required
def api_importer_enseignants_excel() -> Any:
    """Importe les enseignants depuis Excel pour l'année active, en écrasant les données existantes pour cette année."""
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
        flash("Aucun fichier valide sélectionné ou nom de fichier manquant.", "warning")
        return redirect(url_for("admin.page_administration_donnees"))

    if not file.filename.endswith((".xlsx", ".xls")):
        flash(
            "Format de fichier invalide. Veuillez utiliser un fichier Excel (.xlsx ou .xls).",
            "error",
        )
        return redirect(url_for("admin.page_administration_donnees"))

    nouveaux_enseignants = []
    try:
        workbook = openpyxl.load_workbook(file.stream)
        sheet = cast(Worksheet, workbook.active)
        if sheet.max_row <= 1:
            raise ValueError("Fichier Excel vide ou ne contient que l'en-tête.")

        for row_idx, row in enumerate(sheet.iter_rows(min_row=2), start=2):
            values = [cell.value for cell in row]
            if not any(v is not None and str(v).strip() != "" for v in values[:4]):
                current_app.logger.debug(f"Ligne enseignant {row_idx} ignorée (vide).")
                continue

            champ_no_raw, nom_raw, prenom_raw, temps_plein_raw = (
                values[0],
                values[1],
                values[2],
                values[3],
            )

            if not all([champ_no_raw, nom_raw, prenom_raw, temps_plein_raw is not None]):
                flash(
                    f"Ligne enseignant {row_idx}: Données manquantes. Vérifiez ChampNo, Nom, Prénom, EstTempsPlein.",
                    "warning",
                )
                continue

            try:
                champ_no = str(champ_no_raw).strip()
                nom_clean = str(nom_raw).strip()
                prenom_clean = str(prenom_raw).strip()
                est_temps_plein = str(temps_plein_raw).strip().upper() in (
                    "VRAI",
                    "TRUE",
                    "OUI",
                    "YES",
                    "1",
                )
            except (ValueError, TypeError) as ve_ens:
                flash(
                    f"Ligne enseignant {row_idx}: Erreur de conversion de données ({ve_ens}).",
                    "warning",
                )
                continue

            if not nom_clean or not prenom_clean:
                flash(
                    f"Ligne enseignant {row_idx}: Nom ou Prénom vide après nettoyage.",
                    "warning",
                )
                continue

            nouveaux_enseignants.append(
                {
                    "nomcomplet": f"{prenom_clean} {nom_clean}",
                    "nom": nom_clean,
                    "prenom": prenom_clean,
                    "champno": champ_no,
                    "esttempsplein": est_temps_plein,
                }
            )

    except InvalidFileException:
        flash("Fichier Excel des enseignants corrompu ou invalide.", "error")
        return redirect(url_for("admin.page_administration_donnees"))
    except ValueError as e_val_ens:
        flash(str(e_val_ens), "error")
        return redirect(url_for("admin.page_administration_donnees"))
    except Exception as e_gen_ens:
        current_app.logger.error(
            f"Erreur imprévue lecture Excel enseignants: {e_gen_ens}", exc_info=True
        )
        flash(
            f"Erreur inattendue lors de la lecture du fichier Excel des enseignants : {e_gen_ens}",
            "error",
        )
        return redirect(url_for("admin.page_administration_donnees"))

    if not nouveaux_enseignants:
        flash(
            "Aucun enseignant valide trouvé dans le fichier après traitement. Vérifiez le contenu et les messages d'avertissement.",
            "warning",
        )
        return redirect(url_for("admin.page_administration_donnees"))

    conn = cast(connection, db.get_db())
    if not conn:
        flash("Erreur de connexion à la base de données.", "error")
        return redirect(url_for("admin.page_administration_donnees"))

    try:
        with conn.cursor() as cur:
            current_app.logger.info(
                f"Début transaction importation enseignants pour l'année ID {annee_id}."
            )
            nb_attr_supp_ens = db.delete_all_attributions_for_year(annee_id)
            current_app.logger.info(f"{nb_attr_supp_ens} attributions supprimées.")

            nb_ens_supp = db.delete_all_enseignants_for_year(annee_id)
            current_app.logger.info(f"{nb_ens_supp} enseignants supprimés.")

            current_app.logger.info(
                f"Insertion de {len(nouveaux_enseignants)} nouveaux enseignants..."
            )
            for ens in nouveaux_enseignants:
                cur.execute(
                    """INSERT INTO Enseignants (annee_id, NomComplet, Nom, Prenom, ChampNo, EstTempsPlein, EstFictif, PeutChoisirHorsChampPrincipal)
                       VALUES (%(annee_id)s, %(nomcomplet)s, %(nom)s, %(prenom)s, %(champno)s, %(esttempsplein)s, FALSE, FALSE);""",
                    {**ens, "annee_id": annee_id},
                )
            conn.commit()
        flash(
            f"{len(nouveaux_enseignants)} enseignants importés pour l'année '{annee_libelle}'. "
            f"Anciens enseignants ({nb_ens_supp}) et attributions ({nb_attr_supp_ens}) de cette année supprimés.",
            "success",
        )
    except psycopg2.Error as e_db_ens:
        conn.rollback()
        current_app.logger.error(
            f"Erreur DB importation enseignants: {e_db_ens}", exc_info=True
        )
        flash(
            f"Erreur base de données: {e_db_ens}. L'importation a été annulée.",
            "error",
        )
    except Exception as e_final_ens:
        conn.rollback()
        current_app.logger.error(
            f"Erreur inconnue durant transaction d'importation enseignants: {e_final_ens}",
            exc_info=True,
        )
        flash(f"Erreur inconnue: {e_final_ens}. L'importation a été annulée.", "error")

    return redirect(url_for("admin.page_administration_donnees"))


@bp.route("/exporter_taches_excel")
@admin_required
def exporter_taches_excel() -> Any:
    """
    Exporte toutes les tâches attribuées pour l'année active dans un fichier Excel.

    Cette route récupère les données via la base de données, puis appelle le
    module d'export pour générer le fichier Excel, qui est ensuite servi
    en tant que réponse HTTP.
    """
    if not g.annee_active:
        flash("Exportation impossible : aucune année scolaire n'est active.", "error")
        return redirect(url_for("admin.page_sommaire"))

    annee_id = g.annee_active["annee_id"]
    annee_libelle = g.annee_active["libelle_annee"]

    attributions = db.get_all_attributions_for_export(annee_id)

    if not attributions:
        flash(
            f"Aucune tâche attribuée à exporter pour l'année '{annee_libelle}'.",
            "warning",
        )
        return redirect(url_for("admin.page_sommaire"))

    # Appel de la fonction de génération déportée dans le module exports
    mem_file = exports.generer_export_taches(attributions)

    filename = f"export_taches_{annee_libelle}.xlsx"
    current_app.logger.info(
        f"Génération du fichier d'export formaté et agrégé '{filename}' pour l'année ID {annee_id}."
    )

    return Response(
        mem_file,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@bp.route("/exporter_periodes_restantes_excel")
@admin_required
def exporter_periodes_restantes_excel() -> Any:
    """
    Exporte les périodes non attribuées (restantes) pour l'année active.

    Récupère les données des périodes restantes, les transforme au format attendu,
    puis appelle le module d'export pour générer un fichier Excel avec une
    feuille par champ.
    """
    if not g.annee_active:
        flash("Exportation impossible : aucune année scolaire n'est active.", "error")
        return redirect(url_for("admin.page_sommaire"))

    annee_id = g.annee_active["annee_id"]
    annee_libelle = g.annee_active["libelle_annee"]

    # 1. Récupérer les données brutes (probablement une liste de dictionnaires)
    periodes_restantes_raw = db.get_periodes_restantes_for_export(annee_id)

    if not periodes_restantes_raw:
        flash(
            f"Aucune période restante à exporter pour l'année '{annee_libelle}'.",
            "warning",
        )
        return redirect(url_for("admin.page_sommaire"))

    # 2. Transformer les données dans la structure attendue par la fonction d'export
    #    Ceci corrige l'incompatibilité de format qui causait l'erreur.
    periodes_par_champ_transformees: dict[str, dict[str, Any]] = {}
    for periode in periodes_restantes_raw:
        champ_no = periode["champno"]
        if champ_no not in periodes_par_champ_transformees:
            periodes_par_champ_transformees[champ_no] = {
                "nom": periode["champnom"],
                "periodes": [],
            }
        periodes_par_champ_transformees[champ_no]["periodes"].append(periode)

    # 3. Appel de la fonction de génération avec les données correctement formatées
    mem_file = exports.generer_export_periodes_restantes(periodes_par_champ_transformees)

    filename = f"export_periodes_restantes_{annee_libelle}.xlsx"
    current_app.logger.info(
        f"Génération du fichier d'export des périodes restantes '{filename}' pour l'année ID {annee_id}."
    )

    return Response(
        mem_file,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


# --- API non modifiées car indépendantes de l'année ---
@bp.route("/api/utilisateurs", methods=["GET"])
@admin_api_required
def api_get_all_users() -> Any:
    """Récupère tous les utilisateurs avec des informations sur leur nombre (admin/total)."""
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
                {"success": False, "message": "Nom d'utilisateur et mot de passe requis."}
            ),
            400,
        )
    if len(password) < 6:
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Le mot de passe doit faire au moins 6 caractères.",
                }
            ),
            400,
        )

    is_admin = data.get("is_admin", False)
    allowed_champs = data.get("allowed_champs", [])
    hashed_pwd = generate_password_hash(password)
    user = db.create_user(username, hashed_pwd, is_admin)

    if not user:
        return (
            jsonify({"success": False, "message": "Ce nom d'utilisateur est déjà pris."}),
            409,
        )

    if not is_admin and allowed_champs:
        if not db.update_user_champ_access(user["id"], allowed_champs):
            db.delete_user_data(user["id"])
            current_app.logger.error(
                f"Échec de l'attribution des droits pour le nouvel utilisateur {username}, création annulée."
            )
            return (
                jsonify(
                    {
                        "success": False,
                        "message": "Erreur lors de l'attribution des accès aux champs.",
                    }
                ),
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
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Données invalides (champ_nos doit être une liste).",
                }
            ),
            400,
        )

    target_user = db.get_user_by_id(user_id)
    if not target_user:
        return jsonify({"success": False, "message": "Utilisateur non trouvé."}), 404
    if target_user["is_admin"]:
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Les accès d'un administrateur ne peuvent pas être modifiés via cette interface.",
                }
            ),
            403,
        )

    if db.update_user_champ_access(user_id, champ_nos):
        current_app.logger.info(
            f"Accès aux champs mis à jour pour l'utilisateur ID {user_id}."
        )
        return jsonify({"success": True, "message": "Accès mis à jour."})
    current_app.logger.error(
        f"Échec de la mise à jour des accès pour l'utilisateur ID {user_id}."
    )
    return (
        jsonify({"success": False, "message": "Erreur lors de la mise à jour des accès."}),
        500,
    )


@bp.route("/api/utilisateurs/<int:user_id>/delete", methods=["POST"])
@admin_api_required
def api_delete_user(user_id: int) -> Any:
    """Supprime un utilisateur."""
    if user_id == current_user.id:
        return (
            jsonify({"success": False, "message": "Vous ne pouvez pas supprimer votre propre compte."}),
            403,
        )

    target_user = db.get_user_by_id(user_id)
    if not target_user:
        return jsonify({"success": False, "message": "Utilisateur non trouvé."}), 404

    if target_user["is_admin"] and db.get_admin_count() <= 1:
        return (
            jsonify(
                {"success": False, "message": "Impossible de supprimer le dernier administrateur."}
            ),
            403,
        )

    if db.delete_user_data(user_id):
        current_app.logger.info(
            f"Utilisateur ID {user_id} ('{target_user['username']}') supprimé par '{current_user.username}'."
        )
        return jsonify({"success": True, "message": "Utilisateur supprimé."})

    current_app.logger.error(
        f"Échec de la suppression de l'utilisateur ID {user_id} ('{target_user['username']}')."
    )
    return (
        jsonify({"success": False, "message": "Échec de la suppression de l'utilisateur."}),
        500,
    )


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
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Données manquantes : 'code_cours' et 'nouveau_champ_no' requis.",
                }
            ),
            400,
        )

    result = db.reassign_cours_to_champ(
        code_cours, g.annee_active["annee_id"], nouveau_champ_no
    )
    if result:
        current_app.logger.info(
            f"Cours '{code_cours}' réassigné au champ '{nouveau_champ_no}' pour l'année ID {g.annee_active['annee_id']}."
        )
        return jsonify(
            success=True,
            message=f"Cours '{code_cours}' réassigné au champ '{nouveau_champ_no}'.",
            **result,
        )

    current_app.logger.warning(
        f"Échec de la réassignation du cours '{code_cours}' au champ '{nouveau_champ_no}' pour l'année ID {g.annee_active['annee_id']}."
    )
    return (
        jsonify(
            {
                "success": False,
                "message": "Impossible de réassigner le cours. Vérifiez que le cours et le nouveau champ existent pour cette année scolaire.",
            }
        ),
        500,
    )