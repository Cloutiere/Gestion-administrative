# mon_application/api.py
"""
Ce module contient le Blueprint pour les API accessibles aux utilisateurs non-administrateurs.

Il regroupe les points d'API RESTful pour les opérations sur les champs.
Chaque opération est désormais dépendante de l'année scolaire active, qui est déterminée
globalement pour la requête en cours et accessible via `g.annee_active`.
"""

from typing import Any, cast

from flask import Blueprint, current_app, g, jsonify, request
from flask_login import current_user, login_required
from werkzeug.wrappers import Response

from . import database as db

# Crée un Blueprint 'api' avec un préfixe d'URL.
bp = Blueprint("api", __name__, url_prefix="/api")


@bp.route("/attributions/ajouter", methods=["POST"])
@login_required
def api_ajouter_attribution() -> tuple[Response, int]:
    """
    API pour ajouter une attribution de cours à un enseignant pour l'année active.
    """
    try:
        annee_active = cast(dict[str, Any] | None, getattr(g, "annee_active", None))
        if not annee_active:
            return (
                jsonify({"success": False, "message": "Aucune année scolaire active."}),
                400,
            )

        data = request.get_json()
        if (
            not data
            or not (enseignant_id := data.get("enseignant_id"))
            or not (code_cours := data.get("code_cours"))
        ):
            return jsonify({"success": False, "message": "Données manquantes."}), 400

        annee_id = annee_active["annee_id"]

        verrou_info = db.get_verrou_info_enseignant(enseignant_id)
        if not verrou_info:
            return jsonify({"success": False, "message": "Enseignant non trouvé."}), 404

        if "champno" not in verrou_info or not current_user.can_access_champ(
            verrou_info["champno"]
        ):
            return (
                jsonify({"success": False, "message": "Accès non autorisé à ce champ."}),
                403,
            )

        if verrou_info.get("est_verrouille") and not verrou_info.get("estfictif"):
            return (
                jsonify(
                    {
                        "success": False,
                        "message": "Les modifications sont désactivées car le champ est verrouillé.",
                    }
                ),
                403,
            )
        if db.get_groupes_restants_pour_cours(code_cours, annee_id) < 1:
            return (
                jsonify(
                    {
                        "success": False,
                        "message": "Plus de groupes disponibles pour ce cours cette année.",
                    }
                ),
                409,
            )

        nouvelle_attribution_id = db.add_attribution(
            enseignant_id, code_cours, annee_id
        )
        if nouvelle_attribution_id is None:
            return (
                jsonify(
                    {
                        "success": False,
                        "message": "Erreur de base de données lors de l'attribution.",
                    }
                ),
                500,
            )

        return (
            jsonify(
                {
                    "success": True,
                    "message": "Cours attribué avec succès!",
                    "attribution_id": nouvelle_attribution_id,
                    "enseignant_id": enseignant_id,
                    "code_cours": code_cours,
                    "annee_id_cours": annee_id,
                    "periodes_enseignant": db.calculer_periodes_enseignant(
                        enseignant_id
                    ),
                    "groupes_restants_cours": db.get_groupes_restants_pour_cours(
                        code_cours, annee_id
                    ),
                    "attributions_enseignant": db.get_attributions_enseignant(
                        enseignant_id
                    ),
                }
            ),
            201,
        )
    except Exception as e:
        current_app.logger.error(
            f"Erreur inattendue dans api_ajouter_attribution: {str(e)}", exc_info=True
        )
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Une erreur interne est survenue lors de l'ajout de l'attribution.",
                }
            ),
            500,
        )


@bp.route("/attributions/supprimer", methods=["POST"])
@login_required
def api_supprimer_attribution() -> tuple[Response, int]:
    """
    API pour supprimer une attribution de cours.
    L'année est déduite de l'attribution elle-même.
    """
    try:
        data = request.get_json()
        if not data or not (attr_id := data.get("attribution_id")):
            return jsonify({"success": False, "message": "Données invalides."}), 400

        attr_info = db.get_attribution_info(attr_id)
        if not attr_info:
            return jsonify({"success": False, "message": "Attribution non trouvée."}), 404
        if not current_user.can_access_champ(attr_info["champno"]):
            return (
                jsonify({"success": False, "message": "Accès non autorisé à ce champ."}),
                403,
            )

        if attr_info.get("est_verrouille") and not attr_info.get("estfictif"):
            return (
                jsonify(
                    {
                        "success": False,
                        "message": "Les modifications sont désactivées car le champ est verrouillé.",
                    }
                ),
                403,
            )

        enseignant_id = attr_info["enseignantid"]
        code_cours = attr_info["codecours"]
        annee_id_cours = attr_info["annee_id_cours"]
        if not db.delete_attribution(attr_id):
            return (
                jsonify(
                    {"success": False, "message": "Échec de la suppression de l'attribution."}
                ),
                500,
            )

        return (
            jsonify(
                {
                    "success": True,
                    "message": "Attribution supprimée!",
                    "enseignant_id": enseignant_id,
                    "code_cours": code_cours,
                    "annee_id_cours": annee_id_cours,
                    "periodes_enseignant": db.calculer_periodes_enseignant(
                        enseignant_id
                    ),
                    "groupes_restants_cours": db.get_groupes_restants_pour_cours(
                        code_cours, annee_id_cours
                    ),
                    "attributions_enseignant": db.get_attributions_enseignant(
                        enseignant_id
                    ),
                }
            ),
            200,
        )
    except Exception as e:
        current_app.logger.error(
            f"Erreur inattendue dans api_supprimer_attribution: {str(e)}",
            exc_info=True,
        )
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Une erreur interne est survenue lors de la suppression de l'attribution.",
                }
            ),
            500,
        )


@bp.route("/champs/<string:champ_no>/taches_restantes/creer", methods=["POST"])
@login_required
def api_creer_tache_restante(champ_no: str) -> tuple[Response, int]:
    """
    API pour créer une nouvelle tâche restante (enseignant fictif) dans un champ pour l'année active.
    """
    try:
        annee_active = cast(dict[str, Any] | None, getattr(g, "annee_active", None))
        if not annee_active:
            return (
                jsonify({"success": False, "message": "Aucune année scolaire active."}),
                400,
            )

        if not current_user.can_access_champ(champ_no):
            return (
                jsonify({"success": False, "message": "Accès non autorisé à ce champ."}),
                403,
            )

        annee_id = annee_active["annee_id"]
        nouveau_fictif = db.create_fictif_enseignant(champ_no, annee_id)
        if not nouveau_fictif:
            return (
                jsonify(
                    {
                        "success": False,
                        "message": "Erreur lors de la création de la tâche restante.",
                    }
                ),
                500,
            )

        return (
            jsonify(
                {
                    "success": True,
                    "message": "Tâche restante créée avec succès!",
                    "enseignant": {
                        **nouveau_fictif,
                        "attributions": [],
                    },
                    "periodes_actuelles": {
                        "periodes_cours": 0.0,
                        "periodes_autres": 0.0,
                        "total_periodes": 0.0,
                    },
                }
            ),
            201,
        )
    except Exception as e:
        current_app.logger.error(
            f"Erreur inattendue dans api_creer_tache_restante pour champ {champ_no}: {str(e)}",
            exc_info=True,
        )
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Une erreur interne est survenue lors de la création de la tâche restante.",
                }
            ),
            500,
        )


@bp.route("/enseignants/<int:enseignant_id>/supprimer", methods=["POST"])
@login_required
def api_supprimer_enseignant(enseignant_id: int) -> tuple[Response, int]:
    """
    API pour supprimer un enseignant (principalement pour les tâches fictives).
    L'année de l'enseignant est intrinsèque à son `enseignant_id`.
    """
    try:
        enseignant_info = db.get_enseignant_details(enseignant_id)
        if not enseignant_info:
            return jsonify({"success": False, "message": "Enseignant non trouvé."}), 404
        if not current_user.can_access_champ(enseignant_info["champno"]):
            return (
                jsonify({"success": False, "message": "Accès non autorisé à ce champ."}),
                403,
            )

        cours_affectes = db.get_affected_cours_for_enseignant(enseignant_id)
        if not db.delete_enseignant(enseignant_id):
            return (
                jsonify(
                    {"success": False, "message": "Échec de la suppression de l'enseignant."}
                ),
                500,
            )

        cours_liberes_details = [
            {
                "code_cours": c["codecours"],
                "annee_id_cours": c["annee_id_cours"],
                "nouveaux_groupes_restants": db.get_groupes_restants_pour_cours(
                    c["codecours"], c["annee_id_cours"]
                ),
            }
            for c in cours_affectes
        ]
        return (
            jsonify(
                {
                    "success": True,
                    "message": "Enseignant supprimé avec succès.",
                    "enseignant_id": enseignant_id,
                    "cours_liberes_details": cours_liberes_details,
                }
            ),
            200,
        )
    except Exception as e:
        current_app.logger.error(
            f"Erreur inattendue dans api_supprimer_enseignant pour ID {enseignant_id}: {str(e)}",
            exc_info=True,
        )
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Une erreur interne est survenue lors de la suppression de l'enseignant.",
                }
            ),
            500,
        )