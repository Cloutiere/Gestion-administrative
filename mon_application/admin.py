# mon_application/admin.py
"""
Ce module contient le Blueprint pour les routes d'administration des données.

Il inclut les pages HTML et les points d'API RESTful pour les opérations de
création, modification et suppression des entités fondamentales de l'application.
Il agit comme une couche de contrôle, déléguant toute la logique métier à la
couche de services.
"""

from typing import Any, cast

import psycopg2
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
from werkzeug.wrappers import Response

from . import database as db
from . import services
from .services import (
    BusinessRuleValidationError,
    DuplicateEntityError,
    EntityNotFoundError,
    ForeignKeyError,
    ServiceException,
)
from .utils import admin_api_required, admin_required, annee_active_required

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
        # Les opérations de lecture simple peuvent rester des appels DAO directs
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
    # REFACTOR: La logique est déplacée vers un service.
    # Note: ce service sera ajouté dans la prochaine mise à jour de services.py
    try:
        annee_courante_existante = db.get_annee_courante() is not None
        # Simule l'appel à un futur service, pour l'instant la logique reste simple.
        new_annee = db.create_annee_scolaire(libelle)
        if not new_annee:
             raise DuplicateEntityError(f"L'année '{libelle}' existe déjà.")

        if not annee_courante_existante:
            db.set_annee_courante(new_annee["annee_id"])
            new_annee["est_courante"] = True

        current_app.logger.info(
            f"Année scolaire '{libelle}' créée avec ID {new_annee['annee_id']}."
        )
        return jsonify({
            "success": True,
            "message": f"Année '{libelle}' créée.",
            "annee": new_annee,
        }), 201

    except DuplicateEntityError as e:
        return jsonify({"success": False, "message": e.message}), 409
    except ServiceException as e:
        return jsonify({"success": False, "message": e.message}), 500


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
    # REFACTOR: Cette opération est simple, on peut la laisser en appel direct pour l'instant
    if db.set_annee_courante(annee_id):
        annee_maj = db.get_annee_by_id(annee_id)
        if annee_maj:
            current_app.logger.info(
                f"Année courante de l'application définie sur : '{annee_maj['libelle_annee']}'."
            )
        return jsonify({"success": True, "message": "Nouvelle année courante définie."}), 200

    return jsonify({"success": False, "message": "Erreur lors de la mise à jour."}), 500


# --- API pour la gestion des données (année-dépendantes, admin seulement) ---


@bp.route("/api/champs/<string:champ_no>/basculer_verrou", methods=["POST"])
@admin_api_required
@annee_active_required
def api_basculer_verrou_champ(champ_no: str, annee_active: dict[str, Any]) -> tuple[Response, int]:
    """Bascule le statut de verrouillage d'un champ pour l'année active."""
    nouveau_statut = db.toggle_champ_annee_lock_status(champ_no, annee_active["annee_id"])

    if nouveau_statut is None:
        return jsonify({"success": False, "message": f"Impossible de modifier le verrou du champ {champ_no}."}), 500

    message = f"Le champ {champ_no} a été {'verrouillé' if nouveau_statut else 'déverrouillé'}."
    current_app.logger.info(message)
    return jsonify({"success": True, "message": message, "est_verrouille": nouveau_statut}), 200


@bp.route("/api/champs/<string:champ_no>/basculer_confirmation", methods=["POST"])
@admin_api_required
@annee_active_required
def api_basculer_confirmation_champ(champ_no: str, annee_active: dict[str, Any]) -> tuple[Response, int]:
    """Bascule le statut de confirmation d'un champ pour l'année active."""
    nouveau_statut = db.toggle_champ_annee_confirm_status(champ_no, annee_active["annee_id"])

    if nouveau_statut is None:
        return jsonify({"success": False, "message": f"Impossible de modifier la confirmation du champ {champ_no}."}), 500

    message = f"Le champ {champ_no} a été marqué comme {'confirmé' if nouveau_statut else 'non confirmé'}."
    current_app.logger.info(message)
    return jsonify({"success": True, "message": message, "est_confirme": nouveau_statut}), 200


@bp.route("/api/cours/creer", methods=["POST"])
@admin_api_required
@annee_active_required
def api_create_cours(annee_active: dict[str, Any]) -> tuple[Response, int]:
    """API pour créer un nouveau cours dans l'année active."""
    data = request.get_json()
    required_keys = ["codecours", "champno", "coursdescriptif", "nbperiodes", "nbgroupeinitial", "estcoursautre"]
    if not data or not all(k in data for k in required_keys):
        return jsonify({"success": False, "message": "Données manquantes."}), 400

    try:
        # REFACTOR: Appel à la couche de service
        new_cours = services.create_course_service(data, annee_active["annee_id"])
        current_app.logger.info(f"Cours '{data['codecours']}' créé pour l'année ID {annee_active['annee_id']}.")
        return jsonify({"success": True, "message": "Cours créé.", "cours": new_cours}), 201
    except DuplicateEntityError as e:
        return jsonify({"success": False, "message": e.message}), 409
    except ServiceException as e:
        return jsonify({"success": False, "message": e.message}), 500


@bp.route("/api/cours/<path:code_cours>", methods=["GET"])
@admin_api_required
@annee_active_required
def api_get_cours_details(code_cours: str, annee_active: dict[str, Any]) -> tuple[Response, int]:
    """API pour récupérer les détails d'un cours de l'année active."""
    cours = db.get_cours_details(code_cours, annee_active["annee_id"])
    if not cours:
        return jsonify({"success": False, "message": "Cours non trouvé pour cette année."}), 404
    return jsonify({"success": True, "cours": cours}), 200


@bp.route("/api/cours/<path:code_cours>/modifier", methods=["POST"])
@admin_api_required
@annee_active_required
def api_update_cours(code_cours: str, annee_active: dict[str, Any]) -> tuple[Response, int]:
    """API pour modifier un cours de l'année active."""
    data = request.get_json()
    required_keys = ["champno", "coursdescriptif", "nbperiodes", "nbgroupeinitial", "estcoursautre"]
    if not data or not all(k in data for k in required_keys):
        return jsonify({"success": False, "message": "Données manquantes."}), 400

    try:
        # REFACTOR: Appel à un futur service
        updated_cours = db.update_cours(code_cours, annee_active["annee_id"], data)
        if not updated_cours:
            raise EntityNotFoundError("Cours non trouvé pour cette année.")
        current_app.logger.info(f"Cours '{code_cours}' modifié pour l'année ID {annee_active['annee_id']}.")
        return jsonify({"success": True, "message": "Cours mis à jour.", "cours": updated_cours}), 200
    except EntityNotFoundError as e:
        return jsonify({"success": False, "message": e.message}), 404
    except ServiceException as e:
        return jsonify({"success": False, "message": e.message}), 500


@bp.route("/api/cours/<path:code_cours>/supprimer", methods=["POST"])
@admin_api_required
@annee_active_required
def api_delete_cours(code_cours: str, annee_active: dict[str, Any]) -> tuple[Response, int]:
    """API pour supprimer un cours de l'année active."""
    try:
        # REFACTOR: Appel à la couche de service
        services.delete_course_service(code_cours, annee_active["annee_id"])
        current_app.logger.info(f"Cours '{code_cours}' supprimé pour l'année ID {annee_active['annee_id']}.")
        return jsonify({"success": True, "message": "Cours supprimé."}), 200
    except ForeignKeyError as e:
        return jsonify({"success": False, "message": e.message}), 409
    except EntityNotFoundError as e:
        return jsonify({"success": False, "message": e.message}), 404
    except ServiceException as e:
        return jsonify({"success": False, "message": e.message}), 500


@bp.route("/api/enseignants/creer", methods=["POST"])
@admin_api_required
@annee_active_required
def api_create_enseignant(annee_active: dict[str, Any]) -> tuple[Response, int]:
    """API pour créer un nouvel enseignant dans l'année active."""
    data = request.get_json()
    if not data or not all(k in data for k in ["nom", "prenom", "champno", "esttempsplein"]):
        return jsonify({"success": False, "message": "Données manquantes."}), 400

    try:
        # REFACTOR: Appel à la couche de service
        new_enseignant = services.create_teacher_service(data, annee_active["annee_id"])
        current_app.logger.info(f"Enseignant '{data['nom']}' créé pour l'année ID {annee_active['annee_id']}.")
        return jsonify({"success": True, "message": "Enseignant créé.", "enseignant": new_enseignant}), 201
    except DuplicateEntityError as e:
        return jsonify({"success": False, "message": e.message}), 409
    except ServiceException as e:
        return jsonify({"success": False, "message": e.message}), 500


@bp.route("/api/enseignants/<int:enseignant_id>", methods=["GET"])
@admin_api_required
def api_get_enseignant_details(enseignant_id: int) -> tuple[Response, int]:
    """API pour récupérer les détails d'un enseignant (ID est unique globalement)."""
    enseignant = db.get_enseignant_details(enseignant_id)
    if not enseignant or enseignant["estfictif"]:
        return jsonify({"success": False, "message": "Enseignant non trouvé ou non modifiable."}), 404
    return jsonify({"success": True, "enseignant": enseignant}), 200


@bp.route("/api/enseignants/<int:enseignant_id>/modifier", methods=["POST"])
@admin_api_required
def api_update_enseignant(enseignant_id: int) -> tuple[Response, int]:
    """API pour modifier un enseignant existant."""
    data = request.get_json()
    if not data or not all(k in data for k in ["nom", "prenom", "champno", "esttempsplein"]):
        return jsonify({"success": False, "message": "Données manquantes."}), 400

    try:
        # REFACTOR: Appel à la couche de service
        updated_enseignant = services.update_teacher_service(enseignant_id, data)
        current_app.logger.info(f"Enseignant ID {enseignant_id} modifié.")
        return jsonify({"success": True, "message": "Enseignant mis à jour.", "enseignant": updated_enseignant}), 200
    except DuplicateEntityError as e:
        return jsonify({"success": False, "message": e.message}), 409
    except EntityNotFoundError as e:
        return jsonify({"success": False, "message": e.message}), 404
    except ServiceException as e:
        return jsonify({"success": False, "message": e.message}), 500


@bp.route("/api/enseignants/<int:enseignant_id>/supprimer", methods=["POST"])
@admin_api_required
def api_delete_enseignant(enseignant_id: int) -> tuple[Response, int]:
    """API pour supprimer un enseignant (et ses attributions par CASCADE)."""
    try:
        # REFACTOR: Appel à la couche de service
        services.delete_teacher_service(enseignant_id)
        current_app.logger.info(f"Enseignant ID {enseignant_id} supprimé.")
        return jsonify({"success": True, "message": "Enseignant et ses attributions supprimés."}), 200
    except EntityNotFoundError as e:
        return jsonify({"success": False, "message": e.message}), 404
    except BusinessRuleValidationError as e:
        return jsonify({"success": False, "message": e.message}), 403
    except ServiceException as e:
        return jsonify({"success": False, "message": e.message}), 500


# --- ROUTES DE GESTION DE FORMULAIRES (HTML) ---


@bp.route("/importer_cours_excel", methods=["POST"])
@admin_required
def importer_cours_excel() -> Response:
    """Traite l'upload d'un fichier Excel de cours."""
    annee_active = cast(dict[str, Any] | None, getattr(g, "annee_active", None))
    if not annee_active:
        flash("Importation impossible : aucune année scolaire n'est active.", "error")
        return redirect(url_for("admin.page_administration_donnees"))
    if "fichier_cours" not in request.files or not request.files["fichier_cours"].filename:
        flash("Aucun fichier sélectionné.", "warning")
        return redirect(url_for("admin.page_administration_donnees"))
    file = request.files["fichier_cours"]
    if not file.filename.endswith((".xlsx", ".xls")):
        flash("Format de fichier invalide. Utilisez un fichier .xlsx.", "error")
        return redirect(url_for("admin.page_administration_donnees"))
    try:
        cours_data = services.process_courses_excel(file.stream)
        stats = services.save_imported_courses(cours_data, annee_active["annee_id"])
        flash(
            f"{stats.imported_count} cours importés pour '{annee_active['libelle_annee']}'. "
            f"Anciens cours ({stats.deleted_main_entities_count}) et "
            f"attributions ({stats.deleted_attributions_count}) supprimés.", "success")
    except (InvalidFileException, ValueError, ServiceException) as e:
        flash(str(e), "error")
    except Exception as e_gen:
        current_app.logger.error(f"Erreur imprévue importation cours: {e_gen}", exc_info=True)
        flash(f"Erreur inattendue: {e_gen}", "error")

    return redirect(url_for("admin.page_administration_donnees"))


@bp.route("/importer_enseignants_excel", methods=["POST"])
@admin_required
def importer_enseignants_excel() -> Response:
    """Traite l'upload d'un fichier Excel d'enseignants."""
    annee_active = cast(dict[str, Any] | None, getattr(g, "annee_active", None))
    if not annee_active:
        flash("Importation impossible : aucune année scolaire n'est active.", "error")
        return redirect(url_for("admin.page_administration_donnees"))
    if "fichier_enseignants" not in request.files or not request.files["fichier_enseignants"].filename:
        flash("Aucun fichier sélectionné.", "warning")
        return redirect(url_for("admin.page_administration_donnees"))
    file = request.files["fichier_enseignants"]
    if not file.filename.endswith((".xlsx", ".xls")):
        flash("Format de fichier invalide. Utilisez un fichier .xlsx.", "error")
        return redirect(url_for("admin.page_administration_donnees"))
    try:
        enseignants_data = services.process_teachers_excel(file.stream)
        stats = services.save_imported_teachers(enseignants_data, annee_active["annee_id"])
        flash(
            f"{stats.imported_count} enseignants importés pour '{annee_active['libelle_annee']}'. "
            f"Anciens enseignants ({stats.deleted_main_entities_count}) et "
            f"attributions ({stats.deleted_attributions_count}) supprimés.", "success")
    except (InvalidFileException, ValueError, ServiceException) as e:
        flash(str(e), "error")
    except Exception as e_gen:
        current_app.logger.error(f"Erreur imprévue importation enseignants: {e_gen}", exc_info=True)
        flash(f"Erreur inattendue: {e_gen}", "error")

    return redirect(url_for("admin.page_administration_donnees"))


# --- API pour la gestion des Types de Financement (admin seulement) ---

@bp.route("/api/financements", methods=["GET"])
@admin_api_required
def api_get_all_financements() -> tuple[Response, int]:
    """Récupère tous les types de financement."""
    return jsonify(db.get_all_financements()), 200


@bp.route("/api/financements/creer", methods=["POST"])
@admin_api_required
def api_create_financement() -> tuple[Response, int]:
    """Crée un nouveau type de financement."""
    data = request.get_json()
    if not data or not (code := data.get("code", "").strip()) or not (libelle := data.get("libelle", "").strip()):
        return jsonify({"success": False, "message": "Code et libellé requis."}), 400
    try:
        # REFACTOR: Appel à un futur service
        new_financement = db.create_financement(code, libelle)
        if not new_financement:
            raise DuplicateEntityError("Ce code de financement existe déjà.")
        current_app.logger.info(f"Type de financement '{code}' créé.")
        return jsonify({"success": True, "message": "Type de financement créé.", "financement": new_financement}), 201
    except DuplicateEntityError as e:
        return jsonify({"success": False, "message": e.message}), 409
    except ServiceException as e:
        return jsonify({"success": False, "message": e.message}), 500


@bp.route("/api/financements/<code>/modifier", methods=["POST"])
@admin_api_required
def api_update_financement(code: str) -> tuple[Response, int]:
    """Met à jour le libellé d'un type de financement."""
    data = request.get_json()
    if not data or not (libelle := data.get("libelle", "").strip()):
        return jsonify({"success": False, "message": "Libellé requis."}), 400
    try:
        # REFACTOR: Appel à un futur service
        updated = db.update_financement(code, libelle)
        if not updated:
            raise EntityNotFoundError("Financement non trouvé.")
        current_app.logger.info(f"Type de financement '{code}' mis à jour.")
        return jsonify({"success": True, "message": "Type de financement mis à jour.", "financement": updated}), 200
    except EntityNotFoundError as e:
        return jsonify({"success": False, "message": e.message}), 404
    except ServiceException as e:
        return jsonify({"success": False, "message": e.message}), 500


@bp.route("/api/financements/<code>/supprimer", methods=["POST"])
@admin_api_required
def api_delete_financement(code: str) -> tuple[Response, int]:
    """Supprime un type de financement."""
    try:
        # REFACTOR: Appel à la couche de service
        services.delete_financement_service(code)
        current_app.logger.info(f"Type de financement '{code}' supprimé.")
        return jsonify({"success": True, "message": "Type de financement supprimé."}), 200
    except ForeignKeyError as e:
        return jsonify({"success": False, "message": e.message}), 409
    except EntityNotFoundError as e:
        return jsonify({"success": False, "message": e.message}), 404
    except ServiceException as e:
        return jsonify({"success": False, "message": e.message}), 500


# --- API de gestion des utilisateurs (admin seulement) ---
@bp.route("/api/utilisateurs", methods=["GET"])
@admin_api_required
def api_get_all_users() -> tuple[Response, int]:
    """Récupère tous les utilisateurs avec des informations sur leur nombre."""
    return jsonify(users=db.get_all_users_with_access_info(), admin_count=db.get_admin_count()), 200


@bp.route("/api/utilisateurs/creer", methods=["POST"])
@admin_api_required
def api_create_user() -> tuple[Response, int]:
    """Crée un nouvel utilisateur avec un rôle défini."""
    data = request.get_json()
    if not data or not (u := data.get("username", "").strip()) or not (p := data.get("password", "").strip()) or "role" not in data:
        return jsonify({"success": False, "message": "Nom d'utilisateur, mdp et rôle requis."}), 400

    try:
        # REFACTOR: Toute la logique complexe est maintenant dans le service.
        user = services.create_user_service(
            username=u,
            password=p,
            role=data["role"],
            allowed_champs=data.get("allowed_champs", []),
        )
        current_app.logger.info(f"Utilisateur '{u}' (rôle: {data['role']}) créé avec ID {user['id']}.")
        return jsonify({"success": True, "message": f"Utilisateur '{u}' créé!", "user_id": user["id"]}), 201
    except (DuplicateEntityError, BusinessRuleValidationError) as e:
        return jsonify({"success": False, "message": e.message}), 409
    except ServiceException as e:
        return jsonify({"success": False, "message": e.message}), 500


@bp.route("/api/utilisateurs/<int:user_id>/update_role", methods=["POST"])
@admin_api_required
def api_update_user_role(user_id: int) -> tuple[Response, int]:
    """Met à jour le rôle et les accès d'un utilisateur."""
    data = request.get_json()
    if not data or "role" not in data:
        return jsonify({"success": False, "message": "Données invalides."}), 400
    try:
        # REFACTOR: Appel à la couche de service
        services.update_user_role_service(
            user_id=user_id,
            role=data["role"],
            allowed_champs=data.get("allowed_champs", []),
        )
        current_app.logger.info(f"Rôle et accès mis à jour pour l'user ID {user_id}.")
        return jsonify({"success": True, "message": "Rôle et accès mis à jour."}), 200
    except EntityNotFoundError as e:
        return jsonify({"success": False, "message": e.message}), 404
    except ServiceException as e:
        return jsonify({"success": False, "message": e.message}), 500


@bp.route("/api/utilisateurs/<int:user_id>/delete", methods=["POST"])
@admin_api_required
def api_delete_user(user_id: int) -> tuple[Response, int]:
    """Supprime un utilisateur."""
    try:
        # REFACTOR: Appel à la couche de service
        target_username = (db.get_user_by_id(user_id) or {}).get('username', 'inconnu')
        services.delete_user_service(user_id, current_user.id)
        current_app.logger.info(f"User ID {user_id} ('{target_username}') supprimé par '{current_user.username}'.")
        return jsonify({"success": True, "message": "Utilisateur supprimé."}), 200
    except EntityNotFoundError as e:
        return jsonify({"success": False, "message": e.message}), 404
    except BusinessRuleValidationError as e:
        return jsonify({"success": False, "message": e.message}), 403
    except ServiceException as e:
        return jsonify({"success": False, "message": e.message}), 500


@bp.route("/api/cours/reassigner_champ", methods=["POST"])
@admin_api_required
@annee_active_required
def api_reassigner_cours_champ(annee_active: dict[str, Any]) -> tuple[Response, int]:
    """API pour réassigner un cours à un nouveau champ, pour l'année active."""
    data = request.get_json()
    if not data or not (code_cours := data.get("code_cours")) or not (nouveau_champ_no := data.get("nouveau_champ_no")):
        return jsonify({"success": False, "message": "Données manquantes."}), 400
    try:
        # REFACTOR: Appel à un futur service
        result = db.reassign_cours_to_champ(code_cours, annee_active["annee_id"], nouveau_champ_no)
        if not result:
            raise ServiceException("Impossible de réassigner le cours (champ invalide ou cours non trouvé).")
        current_app.logger.info(f"Cours '{code_cours}' réassigné au champ '{nouveau_champ_no}'.")
        return jsonify(success=True, message=f"Cours réassigné.", **result), 200
    except ServiceException as e:
        return jsonify({"success": False, "message": e.message}), 500


@bp.route("/api/cours/reassigner_financement", methods=["POST"])
@admin_api_required
@annee_active_required
def api_reassigner_cours_financement(annee_active: dict[str, Any]) -> tuple[Response, int]:
    """API pour réassigner un cours à un nouveau type de financement, pour l'année active."""
    data = request.get_json()
    if not data or not (code_cours := data.get("code_cours")):
        return jsonify({"success": False, "message": "Données manquantes."}), 400
    nouveau_financement_code = data.get("nouveau_financement_code") or None
    try:
        # REFACTOR: Appel à un futur service
        success = db.reassign_cours_to_financement(code_cours, annee_active["annee_id"], nouveau_financement_code)
        if not success:
            raise ServiceException("Impossible de réassigner le financement.")
        current_app.logger.info(f"Financement du cours '{code_cours}' mis à jour.")
        return jsonify(success=True, message="Financement du cours mis à jour."), 200
    except ServiceException as e:
        return jsonify({"success": False, "message": e.message}), 500