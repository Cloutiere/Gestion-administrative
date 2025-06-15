# mon_application/admin.py
"""
Ce module contient le Blueprint pour les routes d'administration des données.

Il inclut les pages HTML et les points d'API RESTful pour les opérations de
création, modification et suppression des entités fondamentales de l'application
(années, utilisateurs, cours, enseignants, etc.). L'accès est restreint aux
utilisateurs avec des privilèges d'administrateur via les décorateurs
`admin_required` et `admin_api_required`.
"""

from typing import Any, cast

import psycopg2
import psycopg2.extras
from flask import (
    Blueprint,
    current_app,
    flash,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user
from openpyxl.utils.exceptions import InvalidFileException
from werkzeug.security import generate_password_hash
from werkzeug.wrappers import Response

from . import database as db
from . import services
from .utils import admin_api_required, admin_required

# Crée un Blueprint 'admin' avec un préfixe d'URL.
bp = Blueprint("admin", __name__, url_prefix="/admin")


# --- ROUTES DES PAGES (HTML) ---


@bp.route("/donnees")
@admin_required
def page_administration_donnees() -> str:
    """Affiche la page d'administration des données pour l'année active."""
    cours_par_champ_data: dict[str, dict[str, Any]] = {}
    enseignants_par_champ_data: dict[str, dict[str, Any]] = {}

    annee_active = cast(dict[str, Any] | None, getattr(g, "annee_active", None))
    if annee_active:
        annee_id = annee_active["annee_id"]
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
def api_creer_annee() -> tuple[Response, int]:
    """API pour créer une nouvelle année scolaire."""
    data = request.get_json()
    if not data or not (libelle := data.get("libelle", "").strip()):
        return (
            jsonify({"success": False, "message": "Le libellé de l'année est requis."}),
            400,
        )

    annee_courante_existante = db.get_annee_courante()

    new_annee = db.create_annee_scolaire(libelle)
    if new_annee:
        if not annee_courante_existante:
            db.set_annee_courante(new_annee["annee_id"])
            new_annee["est_courante"] = True
        current_app.logger.info(
            f"Année scolaire '{libelle}' créée avec ID {new_annee['annee_id']}."
        )
        return (
            jsonify(
                {
                    "success": True,
                    "message": f"Année '{libelle}' créée.",
                    "annee": new_annee,
                }
            ),
            201,
        )

    return (
        jsonify({"success": False, "message": f"L'année '{libelle}' existe déjà."}),
        409,
    )


@bp.route("/api/annees/set_courante", methods=["POST"])
@admin_api_required
def api_set_annee_courante() -> tuple[Response, int]:
    """API pour définir l'année courante pour toute l'application."""
    data = request.get_json()
    if not data or not (annee_id := data.get("annee_id")):
        return (
            jsonify({"success": False, "message": "ID de l'année manquant."}),
            400,
        )

    if db.set_annee_courante(annee_id):
        annee_maj = db.get_annee_by_id(annee_id)
        if annee_maj:
            current_app.logger.info(
                "Année courante de l'application définie sur : "
                f"'{annee_maj['libelle_annee']}'."
            )
        return (
            jsonify({"success": True, "message": "Nouvelle année courante définie."}),
            200,
        )

    return (
        jsonify({"success": False, "message": "Erreur lors de la mise à jour."}),
        500,
    )


# --- API pour la gestion des données (année-dépendantes, admin seulement) ---


@bp.route("/api/champs/<string:champ_no>/basculer_verrou", methods=["POST"])
@admin_api_required
def api_basculer_verrou_champ(champ_no: str) -> tuple[Response, int]:
    """Bascule le statut de verrouillage d'un champ pour l'année active."""
    annee_active = cast(dict[str, Any] | None, getattr(g, "annee_active", None))
    if not annee_active:
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Aucune année scolaire active pour effectuer cette action.",
                }
            ),
            400,
        )

    annee_id = annee_active["annee_id"]
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
    return (
        jsonify(
            {"success": True, "message": message, "est_verrouille": nouveau_statut}
        ),
        200,
    )


@bp.route("/api/champs/<string:champ_no>/basculer_confirmation", methods=["POST"])
@admin_api_required
def api_basculer_confirmation_champ(champ_no: str) -> tuple[Response, int]:
    """Bascule le statut de confirmation d'un champ pour l'année active."""
    annee_active = cast(dict[str, Any] | None, getattr(g, "annee_active", None))
    if not annee_active:
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Aucune année scolaire active pour effectuer cette action.",
                }
            ),
            400,
        )

    annee_id = annee_active["annee_id"]
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
    return (
        jsonify(
            {"success": True, "message": message, "est_confirme": nouveau_statut}
        ),
        200,
    )


@bp.route("/api/cours/creer", methods=["POST"])
@admin_api_required
def api_create_cours() -> tuple[Response, int]:
    """API pour créer un nouveau cours dans l'année active."""
    annee_active = cast(dict[str, Any] | None, getattr(g, "annee_active", None))
    if not annee_active:
        return (
            jsonify({"success": False, "message": "Aucune année scolaire active."}),
            400,
        )
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
        new_cours = db.create_cours(data, annee_active["annee_id"])
        current_app.logger.info(
            f"Cours '{data['codecours']}' créé pour l'année "
            f"ID {annee_active['annee_id']}."
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
def api_get_cours_details(code_cours: str) -> tuple[Response, int]:
    """API pour récupérer les détails d'un cours de l'année active."""
    annee_active = cast(dict[str, Any] | None, getattr(g, "annee_active", None))
    if not annee_active:
        return (
            jsonify({"success": False, "message": "Aucune année scolaire active."}),
            404,
        )
    cours = db.get_cours_details(code_cours, annee_active["annee_id"])
    if not cours:
        return (
            jsonify(
                {"success": False, "message": "Cours non trouvé pour cette année."}
            ),
            404,
        )
    return jsonify({"success": True, "cours": cours}), 200


@bp.route("/api/cours/<path:code_cours>/modifier", methods=["POST"])
@admin_api_required
def api_update_cours(code_cours: str) -> tuple[Response, int]:
    """API pour modifier un cours de l'année active."""
    annee_active = cast(dict[str, Any] | None, getattr(g, "annee_active", None))
    if not annee_active:
        return (
            jsonify({"success": False, "message": "Aucune année scolaire active."}),
            400,
        )
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
        updated_cours = db.update_cours(code_cours, annee_active["annee_id"], data)
        if not updated_cours:
            return (
                jsonify(
                    {"success": False, "message": "Cours non trouvé pour cette année."}
                ),
                404,
            )
        current_app.logger.info(
            f"Cours '{code_cours}' modifié pour l'année "
            f"ID {annee_active['annee_id']}."
        )
        return (
            jsonify(
                {"success": True, "message": "Cours mis à jour.", "cours": updated_cours}
            ),
            200,
        )
    except psycopg2.Error as e:
        current_app.logger.error(f"Erreur DB modification cours: {e}")
        return (
            jsonify({"success": False, "message": f"Erreur de base de données: {e}"}),
            500,
        )


@bp.route("/api/cours/<path:code_cours>/supprimer", methods=["POST"])
@admin_api_required
def api_delete_cours(code_cours: str) -> tuple[Response, int]:
    """API pour supprimer un cours de l'année active."""
    annee_active = cast(dict[str, Any] | None, getattr(g, "annee_active", None))
    if not annee_active:
        return (
            jsonify({"success": False, "message": "Aucune année scolaire active."}),
            400,
        )
    success, message = db.delete_cours(code_cours, annee_active["annee_id"])
    status_code = 200 if success else 400
    if success:
        current_app.logger.info(
            f"Cours '{code_cours}' supprimé pour l'année "
            f"ID {annee_active['annee_id']}."
        )
    return jsonify({"success": success, "message": message}), status_code


@bp.route("/api/enseignants/creer", methods=["POST"])
@admin_api_required
def api_create_enseignant() -> tuple[Response, int]:
    """API pour créer un nouvel enseignant dans l'année active."""
    annee_active = cast(dict[str, Any] | None, getattr(g, "annee_active", None))
    if not annee_active:
        return (
            jsonify({"success": False, "message": "Aucune année scolaire active."}),
            400,
        )
    data = request.get_json()
    if not data or not all(
        k in data for k in ["nom", "prenom", "champno", "esttempsplein"]
    ):
        return jsonify({"success": False, "message": "Données manquantes."}), 400
    try:
        new_enseignant = db.create_enseignant(data, annee_active["annee_id"])
        current_app.logger.info(
            f"Enseignant '{data['nom']}' créé pour l'année "
            f"ID {annee_active['annee_id']}."
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
def api_get_enseignant_details(enseignant_id: int) -> tuple[Response, int]:
    """API pour récupérer les détails d'un enseignant (ID est unique globalement)."""
    enseignant = db.get_enseignant_details(enseignant_id)
    if not enseignant or enseignant["estfictif"]:
        return (
            jsonify(
                {"success": False, "message": "Enseignant non trouvé ou non modifiable."}
            ),
            404,
        )
    return jsonify({"success": True, "enseignant": enseignant}), 200


@bp.route("/api/enseignants/<int:enseignant_id>/modifier", methods=["POST"])
@admin_api_required
def api_update_enseignant(enseignant_id: int) -> tuple[Response, int]:
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
        return (
            jsonify(
                {
                    "success": True,
                    "message": "Enseignant mis à jour.",
                    "enseignant": updated_enseignant,
                }
            ),
            200,
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
def api_delete_enseignant(enseignant_id: int) -> tuple[Response, int]:
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
        return (
            jsonify(
                {"success": True, "message": "Enseignant et ses attributions supprimés."}
            ),
            200,
        )
    return jsonify({"success": False, "message": "Échec de la suppression."}), 500


# --- ROUTES DE GESTION DE FORMULAIRES (HTML) ---


@bp.route("/importer_cours_excel", methods=["POST"])
@admin_required
def importer_cours_excel() -> Response:
    """
    Traite l'upload d'un fichier Excel de cours.
    La logique de parsing et de sauvegarde est déléguée à la couche de services.
    """
    annee_active = cast(dict[str, Any] | None, getattr(g, "annee_active", None))
    if not annee_active:
        flash("Importation impossible : aucune année scolaire n'est active.", "error")
        return redirect(url_for("admin.page_administration_donnees"))

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

    try:
        cours_data = services.process_courses_excel(file.stream)
        stats = services.save_imported_courses(cours_data, annee_active["annee_id"])

        flash(
            f"{stats.imported_count} cours importés pour '{annee_active['libelle_annee']}'. "
            f"Anciens cours ({stats.deleted_main_entities_count}) et "
            f"attributions ({stats.deleted_attributions_count}) supprimés.",
            "success",
        )

    except (InvalidFileException, ValueError) as e:
        flash(str(e), "error")
    except psycopg2.Error as e_db:
        current_app.logger.error(f"Erreur DB importation cours: {e_db}", exc_info=True)
        flash(f"Erreur base de données: {e_db}. Importation annulée.", "error")
    except Exception as e_gen:
        current_app.logger.error(
            f"Erreur imprévue importation cours: {e_gen}", exc_info=True
        )
        flash(f"Erreur inattendue: {e_gen}", "error")

    return redirect(url_for("admin.page_administration_donnees"))


@bp.route("/importer_enseignants_excel", methods=["POST"])
@admin_required
def importer_enseignants_excel() -> Response:
    """
    Traite l'upload d'un fichier Excel d'enseignants.
    La logique de parsing et de sauvegarde est déléguée à la couche de services.
    """
    annee_active = cast(dict[str, Any] | None, getattr(g, "annee_active", None))
    if not annee_active:
        flash("Importation impossible : aucune année scolaire n'est active.", "error")
        return redirect(url_for("admin.page_administration_donnees"))

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

    try:
        enseignants_data = services.process_teachers_excel(file.stream)
        stats = services.save_imported_teachers(
            enseignants_data, annee_active["annee_id"]
        )

        flash(
            f"{stats.imported_count} enseignants importés pour '{annee_active['libelle_annee']}'. "
            f"Anciens enseignants ({stats.deleted_main_entities_count}) et "
            f"attributions ({stats.deleted_attributions_count}) supprimés.",
            "success",
        )

    except (InvalidFileException, ValueError) as e:
        flash(str(e), "error")
    except psycopg2.Error as e_db:
        current_app.logger.error(
            f"Erreur DB importation enseignants: {e_db}", exc_info=True
        )
        flash(f"Erreur base de données: {e_db}. Importation annulée.", "error")
    except Exception as e_gen:
        current_app.logger.error(
            f"Erreur imprévue importation enseignants: {e_gen}", exc_info=True
        )
        flash(f"Erreur inattendue: {e_gen}", "error")

    return redirect(url_for("admin.page_administration_donnees"))


# --- API pour la gestion des Types de Financement (admin seulement) ---


@bp.route("/api/financements", methods=["GET"])
@admin_api_required
def api_get_all_financements() -> tuple[Response, int]:
    """Récupère tous les types de financement."""
    financements = db.get_all_financements()
    return jsonify(financements), 200


@bp.route("/api/financements/creer", methods=["POST"])
@admin_api_required
def api_create_financement() -> tuple[Response, int]:
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
            jsonify(
                {"success": False, "message": "Ce code de financement existe déjà."}
            ),
            409,
        )
    except psycopg2.Error as e:
        current_app.logger.error(f"Erreur DB création financement: {e}")
        return (
            jsonify({"success": False, "message": "Erreur de base de données."}),
            500,
        )


@bp.route("/api/financements/<code>/modifier", methods=["POST"])
@admin_api_required
def api_update_financement(code: str) -> tuple[Response, int]:
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
        return (
            jsonify(
                {
                    "success": True,
                    "message": "Type de financement mis à jour.",
                    "financement": updated,
                }
            ),
            200,
        )
    except psycopg2.Error as e:
        db_conn = db.get_db()
        if db_conn:
            db_conn.rollback()
        current_app.logger.error(f"Erreur DB modif. financement: {e}", exc_info=True)
        return (
            jsonify({"success": False, "message": "Erreur de base de données."}),
            500,
        )


@bp.route("/api/financements/<code>/supprimer", methods=["POST"])
@admin_api_required
def api_delete_financement(code: str) -> tuple[Response, int]:
    """Supprime un type de financement."""
    success, message = db.delete_financement(code)
    status_code = 200 if success else 400
    if success:
        current_app.logger.info(f"Type de financement '{code}' supprimé.")
    return jsonify({"success": success, "message": message}), status_code


# --- API de gestion des utilisateurs (admin seulement) ---
@bp.route("/api/utilisateurs", methods=["GET"])
@admin_api_required
def api_get_all_users() -> tuple[Response, int]:
    """Récupère tous les utilisateurs avec des informations sur leur nombre."""
    return (
        jsonify(
            users=db.get_all_users_with_access_info(), admin_count=db.get_admin_count()
        ),
        200,
    )


@bp.route("/api/utilisateurs/creer", methods=["POST"])
@admin_api_required
def api_create_user() -> tuple[Response, int]:
    """Crée un nouvel utilisateur avec un rôle défini."""
    data = request.get_json()
    if (
        not data
        or not (username := data.get("username", "").strip())
        or not (password := data.get("password", "").strip())
        or "role" not in data
    ):
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Nom d'utilisateur, mdp et rôle requis.",
                }
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

    user = db.create_user(username, generate_password_hash(password))
    if not user:
        return (
            jsonify(
                {"success": False, "message": "Ce nom d'utilisateur est déjà pris."}
            ),
            409,
        )

    role = data.get("role")
    is_admin = role == "admin"
    is_dashboard_only = role == "dashboard_only"
    allowed_champs = (
        data.get("allowed_champs", []) if role == "specific_champs" else []
    )

    if not db.update_user_role_and_access(
        user["id"], is_admin, is_dashboard_only, allowed_champs
    ):
        db.delete_user_data(user["id"])
        current_app.logger.error(
            "Échec de l'attribution du rôle/accès pour le nouvel utilisateur "
            f"{username}."
        )
        return (
            jsonify(
                {"success": False, "message": "Erreur lors de la définition du rôle."}
            ),
            500,
        )

    current_app.logger.info(
        f"Utilisateur '{username}' (rôle: {role}) créé avec ID {user['id']}."
    )
    return (
        jsonify(
            {
                "success": True,
                "message": f"Utilisateur '{username}' créé!",
                "user_id": user["id"],
            }
        ),
        201,
    )


@bp.route("/api/utilisateurs/<int:user_id>/update_role", methods=["POST"])
@admin_api_required
def api_update_user_role(user_id: int) -> tuple[Response, int]:
    """Met à jour le rôle et les accès d'un utilisateur."""
    data = request.get_json()
    if not data or "role" not in data:
        return jsonify({"success": False, "message": "Données invalides."}), 400

    target_user = db.get_user_by_id(user_id)
    if not target_user:
        return jsonify({"success": False, "message": "Utilisateur non trouvé."}), 404

    role = data["role"]
    is_admin = role == "admin"
    is_dashboard_only = role == "dashboard_only"
    allowed_champs = (
        data.get("allowed_champs", []) if role == "specific_champs" else []
    )

    if db.update_user_role_and_access(
        user_id, is_admin, is_dashboard_only, allowed_champs
    ):
        current_app.logger.info(f"Rôle et accès mis à jour pour l'user ID {user_id}.")
        return jsonify({"success": True, "message": "Rôle et accès mis à jour."}), 200

    current_app.logger.error(f"Échec MAJ rôle/accès pour l'user ID {user_id}.")
    return (
        jsonify({"success": False, "message": "Erreur lors de la mise à jour."}),
        500,
    )


@bp.route("/api/utilisateurs/<int:user_id>/delete", methods=["POST"])
@admin_api_required
def api_delete_user(user_id: int) -> tuple[Response, int]:
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
                {
                    "success": False,
                    "message": "Impossible de supprimer le dernier admin.",
                }
            ),
            403,
        )

    if db.delete_user_data(user_id):
        current_app.logger.info(
            f"User ID {user_id} ('{target_user['username']}') supprimé par "
            f"'{current_user.username}'."
        )
        return jsonify({"success": True, "message": "Utilisateur supprimé."}), 200

    current_app.logger.error(f"Échec suppression user ID {user_id}.")
    return jsonify({"success": False, "message": "Échec de la suppression."}), 500


@bp.route("/api/cours/reassigner_champ", methods=["POST"])
@admin_api_required
def api_reassigner_cours_champ() -> tuple[Response, int]:
    """API pour réassigner un cours à un nouveau champ, pour l'année active."""
    annee_active = cast(dict[str, Any] | None, getattr(g, "annee_active", None))
    if not annee_active:
        return (
            jsonify({"success": False, "message": "Aucune année scolaire active."}),
            400,
        )

    data = request.get_json()
    if (
        not data
        or not (code_cours := data.get("code_cours"))
        or not (nouveau_champ_no := data.get("nouveau_champ_no"))
    ):
        return jsonify({"success": False, "message": "Données manquantes."}), 400

    result = db.reassign_cours_to_champ(
        code_cours, annee_active["annee_id"], nouveau_champ_no
    )
    if result:
        current_app.logger.info(
            f"Cours '{code_cours}' réassigné au champ '{nouveau_champ_no}' "
            f"pour l'année ID {annee_active['annee_id']}."
        )
        return (
            jsonify(
                success=True,
                message=f"Cours '{code_cours}' réassigné au champ '{nouveau_champ_no}'.",
                **result,
            ),
            200,
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
def api_reassigner_cours_financement() -> tuple[Response, int]:
    """API pour réassigner un cours à un nouveau type de financement, pour l'année active."""
    annee_active = cast(dict[str, Any] | None, getattr(g, "annee_active", None))
    if not annee_active:
        return (
            jsonify({"success": False, "message": "Aucune année scolaire active."}),
            400,
        )

    data = request.get_json()
    if not data or not (code_cours := data.get("code_cours")):
        return jsonify({"success": False, "message": "Données manquantes."}), 400

    nouveau_financement_code = data.get("nouveau_financement_code")
    financement_a_stocker = nouveau_financement_code or None

    result = db.reassign_cours_to_financement(
        code_cours, annee_active["annee_id"], financement_a_stocker
    )
    if result:
        current_app.logger.info(
            f"Cours '{code_cours}' réassigné au financement '{financement_a_stocker}' "
            f"pour l'année ID {annee_active['annee_id']}."
        )
        return (
            jsonify(
                success=True,
                message=f"Financement du cours '{code_cours}' mis à jour.",
            ),
            200,
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