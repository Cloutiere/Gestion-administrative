# mon_application/api.py
"""
Ce module contient le Blueprint pour les API accessibles aux utilisateurs non-administrateurs.

Il agit comme une couche de contrôle, déléguant toute la logique métier à la
couche de services. Il gère la réception des requêtes API, la validation des
permissions de base et le formatage des réponses JSON.
"""

from typing import Any

from flask import Blueprint, current_app, jsonify, request
from flask_login import current_user, login_required
from werkzeug.wrappers import Response

from . import services
from .services import (
    BusinessRuleValidationError,
    EntityNotFoundError,
    ServiceException,
)
from .utils import annee_active_required

# Crée un Blueprint 'api' avec un préfixe d'URL.
bp = Blueprint("api", __name__, url_prefix="/api")


@bp.route("/attributions/ajouter", methods=["POST"])
@login_required
def api_ajouter_attribution() -> tuple[Response, int]:
    """API pour ajouter une attribution de cours à un enseignant pour l'année active."""
    data = request.get_json()
    if not data or not (eid := data.get("enseignant_id")) or not (cc := data.get("code_cours")):
        return jsonify({"success": False, "message": "Données manquantes."}), 400

    try:
        # La dépendance à l'année active est maintenant explicite via un service.
        annee_active = services.get_active_year_service()

        # L'autorisation est vérifiée dans le contrôleur avant d'appeler le service.
        # On utilise get_teacher_details_service pour s'assurer que l'enseignant est modifiable (non fictif).
        enseignant_details = services.get_teacher_details_service(eid)
        if not current_user.can_access_champ(enseignant_details["champno"]):
            return jsonify({"success": False, "message": "Accès non autorisé à ce champ."}), 403

        # Appel à la couche de service qui contient la logique métier
        nouvelle_attribution_id = services.add_attribution_service(eid, cc, annee_active["annee_id"])

        # Récupération des données mises à jour via les services
        teacher_payload = services.get_teacher_update_payload_service(eid)
        groupes_restants = services.get_remaining_groups_for_course_service(cc, annee_active["annee_id"])

        # Assemblage de la réponse pour le client
        return jsonify(
            {
                "success": True,
                "message": "Cours attribué avec succès!",
                "attribution_id": nouvelle_attribution_id,
                "enseignant_id": eid,
                "code_cours": cc,
                "annee_id_cours": annee_active["annee_id"],
                "periodes_enseignant": teacher_payload["periodes_enseignant"],
                "groupes_restants_cours": groupes_restants,
                "attributions_enseignant": teacher_payload["attributions_enseignant"],
            }
        ), 201

    except EntityNotFoundError as e:
        return jsonify({"success": False, "message": e.message}), 404
    except BusinessRuleValidationError as e:
        return jsonify({"success": False, "message": e.message}), 409
    except ServiceException as e:
        current_app.logger.error(f"Erreur inattendue dans api_ajouter_attribution: {e}", exc_info=True)
        return jsonify({"success": False, "message": "Erreur interne du serveur."}), 500


@bp.route("/attributions/supprimer", methods=["POST"])
@login_required
def api_supprimer_attribution() -> tuple[Response, int]:
    """API pour supprimer une attribution de cours."""
    data = request.get_json()
    if not data or not (attr_id := data.get("attribution_id")):
        return jsonify({"success": False, "message": "Données invalides."}), 400

    try:
        # Étape 1: Vérifier la permission AVANT d'agir.
        # On récupère les détails de l'attribution pour connaître son champ.
        attr_details = services.get_attribution_details_service(attr_id)
        if not current_user.can_access_champ(attr_details["champno"]):
            return jsonify({"success": False, "message": "Accès non autorisé à ce champ."}), 403

        # Étape 2: Appeler le service de suppression.
        deleted_attr_info = services.delete_attribution_service(attr_id)
        enseignant_id = deleted_attr_info["enseignantid"]
        code_cours = deleted_attr_info["codecours"]
        annee_id_cours = deleted_attr_info["annee_id_cours"]

        # Étape 3: Récupération des données mises à jour pour la réponse.
        teacher_payload = services.get_teacher_update_payload_service(enseignant_id)
        groupes_restants = services.get_remaining_groups_for_course_service(code_cours, annee_id_cours)

        # Assemblage de la réponse pour le client
        return jsonify(
            {
                "success": True,
                "message": "Attribution supprimée!",
                "enseignant_id": enseignant_id,
                "code_cours": code_cours,
                "annee_id_cours": annee_id_cours,
                "periodes_enseignant": teacher_payload["periodes_enseignant"],
                "groupes_restants_cours": groupes_restants,
                "attributions_enseignant": teacher_payload["attributions_enseignant"],
            }
        ), 200

    except EntityNotFoundError as e:
        return jsonify({"success": False, "message": e.message}), 404
    except BusinessRuleValidationError as e:  # Capturera les erreurs de verrouillage
        return jsonify({"success": False, "message": e.message}), 403
    except ServiceException as e:
        current_app.logger.error(f"Erreur inattendue dans api_supprimer_attribution: {e}", exc_info=True)
        return jsonify({"success": False, "message": "Erreur interne du serveur."}), 500


@bp.route("/champs/<string:champ_no>/taches_restantes/creer", methods=["POST"])
@login_required
@annee_active_required
def api_creer_tache_restante(champ_no: str, annee_active: dict[str, Any]) -> tuple[Response, int]:
    """API pour créer une nouvelle tâche restante (enseignant fictif) pour l'année active."""
    if not current_user.can_access_champ(champ_no):
        return jsonify({"success": False, "message": "Accès non autorisé à ce champ."}), 403

    try:
        # Appel à la couche de service
        nouveau_fictif = services.create_fictitious_teacher_service(champ_no, annee_active["annee_id"])

        return jsonify(
            {
                "success": True,
                "message": "Tâche restante créée avec succès!",
                "enseignant": {**nouveau_fictif, "attributions": []},
                "periodes_actuelles": {"periodes_cours": 0.0, "periodes_autres": 0.0, "total_periodes": 0.0},
            }
        ), 201

    except ServiceException as e:
        current_app.logger.error(f"Erreur inattendue dans api_creer_tache_restante: {e}", exc_info=True)
        return jsonify({"success": False, "message": "Erreur interne du serveur."}), 500


@bp.route("/enseignants/<int:enseignant_id>/supprimer", methods=["POST"])
@login_required
def api_supprimer_enseignant(enseignant_id: int) -> tuple[Response, int]:
    """API pour supprimer un enseignant (principalement pour les tâches fictives)."""
    try:
        # L'autorisation est vérifiée avant d'appeler le service.
        # On utilise le service général qui trouve n'importe quel enseignant.
        enseignant_info = services.get_any_teacher_by_id_service(enseignant_id)
        if not current_user.can_access_champ(enseignant_info["champno"]):
            return jsonify({"success": False, "message": "Accès non autorisé à ce champ."}), 403

        # Appel à la couche de service
        cours_affectes = services.delete_teacher_service(enseignant_id)

        cours_liberes_details = [
            {
                "code_cours": c["codecours"],
                "annee_id_cours": c["annee_id_cours"],
                "nouveaux_groupes_restants": services.get_remaining_groups_for_course_service(c["codecours"], c["annee_id_cours"]),
            }
            for c in cours_affectes
        ]

        return jsonify(
            {
                "success": True,
                "message": "Enseignant supprimé avec succès.",
                "enseignant_id": enseignant_id,
                "cours_liberes_details": cours_liberes_details,
            }
        ), 200

    except EntityNotFoundError as e:
        return jsonify({"success": False, "message": e.message}), 404
    except ServiceException as e:
        current_app.logger.error(f"Erreur inattendue dans api_supprimer_enseignant: {e}", exc_info=True)
        return jsonify({"success": False, "message": "Erreur interne du serveur."}), 500
