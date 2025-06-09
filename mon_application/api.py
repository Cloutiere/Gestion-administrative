# mon_application/api.py
"""
Ce module contient le Blueprint pour les API accessibles aux utilisateurs non-administrateurs.

Il regroupe les points d'API RESTful pour les opérations sur les champs.
Chaque opération est désormais dépendante de l'année scolaire active, qui est déterminée
globalement pour la requête en cours et accessible via `g.annee_active`.
"""

from typing import Any

from flask import Blueprint, g, jsonify, request
from flask_login import current_user, login_required

from . import database as db

# Crée un Blueprint 'api' avec un préfixe d'URL.
bp = Blueprint("api", __name__, url_prefix="/api")


@bp.route("/attributions/ajouter", methods=["POST"])
@login_required
def api_ajouter_attribution() -> Any:
    """
    API pour ajouter une attribution de cours à un enseignant pour l'année active.
    """
    if not g.annee_active:
        return jsonify({"success": False, "message": "Aucune année scolaire active."}), 400

    data = request.get_json()
    if not data or not (enseignant_id := data.get("enseignant_id")) or not (code_cours := data.get("code_cours")):
        return jsonify({"success": False, "message": "Données manquantes."}), 400

    annee_id = g.annee_active["annee_id"]

    # Étape 1: Vérifier les permissions
    verrou_info = db.get_verrou_info_enseignant(enseignant_id)
    if not verrou_info:
        return jsonify({"success": False, "message": "Enseignant non trouvé."}), 404
    if not current_user.can_access_champ(verrou_info["champno"]):
        return jsonify({"success": False, "message": "Accès non autorisé à ce champ."}), 403

    # Étape 2: Vérifier les règles métier (champ verrouillé, groupes restants pour l'année)
    if verrou_info["estverrouille"] and not verrou_info["estfictif"]:
        return jsonify({"success": False, "message": "Les modifications sont désactivées car le champ est verrouillé."}), 403
    if db.get_groupes_restants_pour_cours(code_cours, annee_id) < 1:
        return jsonify({"success": False, "message": "Plus de groupes disponibles pour ce cours cette année."}), 409

    # Étape 3: Exécuter l'action
    nouvelle_attribution_id = db.add_attribution(enseignant_id, code_cours, annee_id)
    if nouvelle_attribution_id is None:
        return jsonify({"success": False, "message": "Erreur de base de données lors de l'attribution."}), 500

    return (
        jsonify(
            {
                "success": True,
                "message": "Cours attribué avec succès!",
                "attribution_id": nouvelle_attribution_id,
                "enseignant_id": enseignant_id,
                "code_cours": code_cours,
                "annee_id_cours": annee_id,
                "periodes_enseignant": db.calculer_periodes_enseignant(enseignant_id),
                "groupes_restants_cours": db.get_groupes_restants_pour_cours(code_cours, annee_id),
                "attributions_enseignant": db.get_attributions_enseignant(enseignant_id),
            }
        ),
        201,
    )


@bp.route("/attributions/supprimer", methods=["POST"])
@login_required
def api_supprimer_attribution() -> Any:
    """
    API pour supprimer une attribution de cours.
    L'année est déduite de l'attribution elle-même.
    """
    data = request.get_json()
    if not data or not (attr_id := data.get("attribution_id")):
        return jsonify({"success": False, "message": "Données invalides."}), 400

    # Étape 1: Récupérer les informations et vérifier les permissions
    attr_info = db.get_attribution_info(attr_id)
    if not attr_info:
        return jsonify({"success": False, "message": "Attribution non trouvée."}), 404
    if not current_user.can_access_champ(attr_info["champno"]):
        return jsonify({"success": False, "message": "Accès non autorisé à ce champ."}), 403

    # Étape 2: Vérifier les règles métier (champ verrouillé)
    if attr_info["estverrouille"] and not attr_info["estfictif"]:
        return jsonify({"success": False, "message": "Les modifications sont désactivées car le champ est verrouillé."}), 403

    # Étape 3: Exécuter l'action
    enseignant_id = attr_info["enseignantid"]
    code_cours = attr_info["codecours"]
    annee_id_cours = attr_info["annee_id_cours"]
    if not db.delete_attribution(attr_id):
        return jsonify({"success": False, "message": "Échec de la suppression de l'attribution."}), 500

    return (
        jsonify(
            {
                "success": True,
                "message": "Attribution supprimée!",
                "enseignant_id": enseignant_id,
                "code_cours": code_cours,
                "annee_id_cours": annee_id_cours,
                "periodes_enseignant": db.calculer_periodes_enseignant(enseignant_id),
                "groupes_restants_cours": db.get_groupes_restants_pour_cours(code_cours, annee_id_cours),
                "attributions_enseignant": db.get_attributions_enseignant(enseignant_id),
            }
        ),
        200,
    )


@bp.route("/champs/<string:champ_no>/taches_restantes/creer", methods=["POST"])
@login_required
def api_creer_tache_restante(champ_no: str) -> Any:
    """
    API pour créer une nouvelle tâche restante (enseignant fictif) dans un champ pour l'année active.
    """
    if not g.annee_active:
        return jsonify({"success": False, "message": "Aucune année scolaire active."}), 400

    # Étape 1: Vérifier les permissions
    if not current_user.can_access_champ(champ_no):
        return jsonify({"success": False, "message": "Accès non autorisé à ce champ."}), 403

    # Étape 2: Exécuter l'action
    annee_id = g.annee_active["annee_id"]
    nouveau_fictif = db.create_fictif_enseignant(champ_no, annee_id)
    if not nouveau_fictif:
        return jsonify({"success": False, "message": "Erreur lors de la création de la tâche restante."}), 500

    return (
        jsonify(
            {
                "success": True,
                "message": "Tâche restante créée avec succès!",
                "enseignant": {**nouveau_fictif, "attributions": []},
                "periodes_actuelles": {"periodes_cours": 0.0, "periodes_autres": 0.0, "total_periodes": 0.0},
            }
        ),
        201,
    )


@bp.route("/enseignants/<int:enseignant_id>/supprimer", methods=["POST"])
@login_required
def api_supprimer_enseignant(enseignant_id: int) -> Any:
    """
    API pour supprimer un enseignant (principalement pour les tâches fictives).
    """
    # Étape 1: Récupérer les informations et vérifier les permissions
    enseignant_info = db.get_enseignant_details(enseignant_id)
    if not enseignant_info:
        return jsonify({"success": False, "message": "Enseignant non trouvé."}), 404
    if not current_user.can_access_champ(enseignant_info["champno"]):
        return jsonify({"success": False, "message": "Accès non autorisé à ce champ."}), 403

    # Étape 2: Exécuter l'action
    cours_affectes = db.get_affected_cours_for_enseignant(enseignant_id)
    if not db.delete_enseignant(enseignant_id):
        return jsonify({"success": False, "message": "Échec de la suppression de l'enseignant."}), 500

    cours_liberes_details = [
        {
            "code_cours": c["codecours"],
            "annee_id_cours": c["annee_id_cours"],
            "nouveaux_groupes_restants": db.get_groupes_restants_pour_cours(c["codecours"], c["annee_id_cours"]),
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
    )
