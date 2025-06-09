# mon_application/admin.py
"""
Ce module contient le Blueprint pour les routes réservées aux administrateurs.

Il inclut les pages HTML de l'interface d'administration (données, utilisateurs, sommaire)
ainsi que les points d'API RESTful pour les opérations qui nécessitent des privilèges
d'administrateur, comme la gestion des utilisateurs, l'importation de données,
et le verrouillage des champs.
Toutes les routes de ce blueprint sont protégées par les décorateurs `@admin_required`
ou `@admin_api_required`.
"""

from typing import Any, cast

import openpyxl
import psycopg2
import psycopg2.extras
from flask import Blueprint, current_app, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from openpyxl.utils.exceptions import InvalidFileException
from openpyxl.worksheet.worksheet import Worksheet
from psycopg2.extensions import connection
from werkzeug.security import generate_password_hash

from . import database as db
from .utils import admin_api_required, admin_required

# Crée un Blueprint 'admin' avec un préfixe d'URL.
# Toutes les routes ici commenceront par /admin (ex: /admin/sommaire).
bp = Blueprint("admin", __name__, url_prefix="/admin")


# --- Fonctions utilitaires pour le sommaire ---
def calculer_donnees_sommaire() -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]], float]:
    """Calcule les données agrégées pour la page sommaire globale."""
    tous_enseignants_details = db.get_all_enseignants_avec_details()
    enseignants_par_champ_temp: dict[str, Any] = {}
    moyennes_par_champ_calculees: dict[str, Any] = {}
    total_periodes_global_tp = 0.0
    nb_enseignants_tp_global = 0

    for ens in tous_enseignants_details:
        champ_no = ens["champno"]
        if champ_no not in enseignants_par_champ_temp:
            enseignants_par_champ_temp[champ_no] = {"champno": champ_no, "champnom": ens["champnom"], "enseignants": []}
        enseignants_par_champ_temp[champ_no]["enseignants"].append(ens)

    for champ_no, data in enseignants_par_champ_temp.items():
        _enseignants = data.get("enseignants", [])
        if _enseignants:
            total_periodes_champ = sum(e["total_periodes"] for e in _enseignants if e["compte_pour_moyenne_champ"])
            nb_enseignants_champ = sum(1 for e in _enseignants if e["compte_pour_moyenne_champ"])

            if nb_enseignants_champ > 0:
                moyennes_par_champ_calculees[champ_no] = {
                    "champ_nom": data["champnom"],
                    "moyenne": total_periodes_champ / nb_enseignants_champ,
                    "est_verrouille": _enseignants[0]["estverrouille"],
                }
                total_periodes_global_tp += total_periodes_champ
                nb_enseignants_tp_global += nb_enseignants_champ

    moyenne_generale_calculee = (total_periodes_global_tp / nb_enseignants_tp_global) if nb_enseignants_tp_global > 0 else 0.0
    return list(enseignants_par_champ_temp.values()), moyennes_par_champ_calculees, moyenne_generale_calculee


# --- ROUTES DES PAGES D'ADMINISTRATION (HTML) ---
# Ces routes sont protégées par le décorateur 'admin_required' qui gère la redirection.


@bp.route("/sommaire")
@login_required
@admin_required
def page_sommaire() -> str:
    """Affiche la page du sommaire global (accessible aux admins)."""
    enseignants_par_champ_data, moyennes_champs, moyenne_gen = calculer_donnees_sommaire()
    return render_template(
        "page_sommaire.html",
        enseignants_par_champ=enseignants_par_champ_data,
        moyennes_par_champ=moyennes_champs,
        moyenne_generale=moyenne_gen,
    )


@bp.route("/donnees")
@login_required
@admin_required
def page_administration_donnees() -> str:
    """Affiche la page d'administration des données (imports, etc.)."""
    return render_template(
        "administration_donnees.html",
        cours_a_reassigner=db.get_all_cours_avec_details_champ(),
        champs_destination=db.get_all_champs(),
    )


@bp.route("/utilisateurs")
@login_required
@admin_required
def page_administration_utilisateurs() -> str:
    """Affiche la page d'administration des utilisateurs."""
    return render_template(
        "administration_utilisateurs.html",
        users=db.get_all_users_with_access_info(),
        all_champs=db.get_all_champs(),
    )


# --- API ENDPOINTS (JSON) - Fonctions réservées aux administrateurs ---
# Ces routes sont protégées par le décorateur 'admin_api_required' qui gère
# à la fois l'authentification et les permissions admin en renvoyant du JSON.


@bp.route("/api/sommaire/donnees", methods=["GET"])
@admin_api_required
def api_get_donnees_sommaire() -> Any:
    """API pour récupérer les données actualisées du sommaire global."""
    enseignants_groupes, moyennes_champs, moyenne_gen = calculer_donnees_sommaire()
    return jsonify(enseignants_par_champ=enseignants_groupes, moyennes_par_champ=moyennes_champs, moyenne_generale=moyenne_gen)


@bp.route("/api/champs/<string:champ_no>/basculer_verrou", methods=["POST"])
@admin_api_required
def api_basculer_verrou_champ(champ_no: str) -> Any:
    """API pour basculer le statut de verrouillage d'un champ."""
    nouveau_statut = db.toggle_champ_lock_status(champ_no)
    if nouveau_statut is None:
        return jsonify({"success": False, "message": f"Impossible de modifier le verrou du champ {champ_no}."}), 500
    message = f"Le champ {champ_no} a été {'verrouillé' if nouveau_statut else 'déverrouillé'}."
    return jsonify({"success": True, "message": message, "est_verrouille": nouveau_statut})


@bp.route("/api/utilisateurs", methods=["GET"])
@admin_api_required
def api_get_all_users() -> Any:
    """API pour lister tous les utilisateurs (pour la page d'admin)."""
    return jsonify(users=db.get_all_users_with_access_info(), admin_count=db.get_admin_count())


@bp.route("/api/utilisateurs/creer", methods=["POST"])
@admin_api_required
def api_create_user() -> Any:
    """API pour créer un nouvel utilisateur (depuis la page d'admin)."""
    data = request.get_json()
    if not data or not (username := data.get("username", "").strip()) or not (password := data.get("password", "").strip()):
        return jsonify({"success": False, "message": "Nom d'utilisateur et mot de passe requis."}), 400
    if len(password) < 6:
        return jsonify({"success": False, "message": "Le mot de passe doit faire au moins 6 caractères."}), 400

    is_admin = data.get("is_admin", False)
    allowed_champs = data.get("allowed_champs", [])
    hashed_pwd = generate_password_hash(password)
    user = db.create_user(username, hashed_pwd, is_admin)

    if not user:
        return jsonify({"success": False, "message": "Ce nom d'utilisateur est déjà pris."}), 409
    if not is_admin and allowed_champs:
        if not db.update_user_champ_access(user["id"], allowed_champs):
            db.delete_user_data(user["id"])
            return jsonify({"success": False, "message": "Erreur lors de l'attribution des accès."}), 500

    return jsonify({"success": True, "message": f"Utilisateur '{username}' créé!", "user_id": user["id"]}), 201


@bp.route("/api/utilisateurs/<int:user_id>/update_access", methods=["POST"])
@admin_api_required
def api_update_user_access(user_id: int) -> Any:
    """API pour mettre à jour les accès d'un utilisateur."""
    data = request.get_json()
    if not data or not isinstance(champ_nos := data.get("champ_nos"), list):
        return jsonify({"success": False, "message": "Données invalides."}), 400

    target_user = db.get_user_by_id(user_id)
    if not target_user:
        return jsonify({"success": False, "message": "Utilisateur non trouvé."}), 404
    if target_user["is_admin"]:
        return jsonify({"success": False, "message": "Les accès d'un admin ne peuvent être modifiés via cette interface."}), 403

    if db.update_user_champ_access(user_id, champ_nos):
        return jsonify({"success": True, "message": "Accès mis à jour."})
    return jsonify({"success": False, "message": "Erreur lors de la mise à jour."}), 500


@bp.route("/api/utilisateurs/<int:user_id>/delete", methods=["POST"])
@admin_api_required
def api_delete_user(user_id: int) -> Any:
    """API pour supprimer un utilisateur."""
    if user_id == current_user.id:
        return jsonify({"success": False, "message": "Vous ne pouvez pas supprimer votre propre compte."}), 403

    target_user = db.get_user_by_id(user_id)
    if not target_user:
        return jsonify({"success": False, "message": "Utilisateur non trouvé."}), 404
    if target_user["is_admin"] and db.get_admin_count() <= 1:
        return jsonify({"success": False, "message": "Impossible de supprimer le dernier admin."}), 403
    if db.delete_user_data(user_id):
        return jsonify({"success": True, "message": "Utilisateur supprimé."})
    return jsonify({"success": False, "message": "Échec de la suppression."}), 500


# --- Fonctions et routes pour l'importation de données Excel ---
def allowed_file(filename: str) -> bool:
    """Vérifie si l'extension du fichier est autorisée."""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in current_app.config["ALLOWED_EXTENSIONS"]


@bp.route("/importer_cours_excel", methods=["POST"])
@login_required
@admin_required
def api_importer_cours_excel() -> Any:
    """Importe les données des cours depuis un fichier Excel."""
    if "fichier_cours" not in request.files or not (file := request.files["fichier_cours"]) or not file.filename:
        flash("Aucun fichier valide sélectionné.", "warning")
        return redirect(url_for("admin.page_administration_donnees"))
    if not allowed_file(file.filename):
        flash("Type de fichier non autorisé (.xlsx seulement).", "error")
        return redirect(url_for("admin.page_administration_donnees"))

    nouveaux_cours = []
    try:
        sheet = openpyxl.load_workbook(file.stream).active
        if not isinstance(sheet, Worksheet) or sheet.max_row <= 1:
            raise ValueError("Fichier Excel vide ou invalide.")

        for row_idx, row in enumerate(iter(sheet.rows), 1):
            if row_idx == 1:
                continue
            values = [cell.value for cell in row]
            if not any(values):
                continue
            if len(values) < 8:
                values.extend([None] * (8 - len(values)))
            champ_no, code_cours, desc, nb_grp, nb_per, est_autre = (values[0], values[1], values[3], values[4], values[5], values[7])
            if not all(str(v).strip() for v in [champ_no, code_cours, desc]) or nb_grp is None or nb_per is None:
                flash(
                    f"Ligne {row_idx} (Cours): Données essentielles manquantes (Champ, Code Cours, Descriptif, Groupes, Périodes), ligne ignorée.",
                    "warning",
                )
                continue
            try:
                num_periodes = float(str(nb_per).replace(",", "."))
                num_groupes = int(float(str(nb_grp).replace(",", ".")))
                is_autre_cours = str(est_autre).strip().upper() == "VRAI" if est_autre else False

                nouveaux_cours.append(
                    {
                        "codecours": str(code_cours).strip(),
                        "champno": str(champ_no).strip(),
                        "coursdescriptif": str(desc).strip(),
                        "nbperiodes": num_periodes,
                        "nbgroupeinitial": num_groupes,
                        "estcoursautre": is_autre_cours,
                    }
                )
            except (ValueError, TypeError) as conv_e:
                flash(
                    f"Ligne {row_idx} (Cours): Erreur de format de données ({conv_e}), ligne ignorée. Vérifiez les nombres et 'VRAI/FAUX'.", "warning"
                )
                continue

    except (InvalidFileException, ValueError, TypeError) as e:
        flash(
            f"Erreur lors de la lecture du fichier Excel: {e}. Assurez-vous qu'il s'agit d'un fichier .xlsx valide et que les \
            données sont au bon format.",
            "error",
        )
        return redirect(url_for("admin.page_administration_donnees"))

    if not nouveaux_cours:
        flash("Aucun cours valide trouvé dans le fichier après lecture.", "warning")
        return redirect(url_for("admin.page_administration_donnees"))

    conn = cast(connection, db.get_db())
    if not conn:
        flash("Erreur de connexion à la base de données. Impossible d'importer les cours.", "error")
        return redirect(url_for("admin.page_administration_donnees"))

    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM AttributionsCours;")
            cur.execute("DELETE FROM Cours;")
            for cours in nouveaux_cours:
                cur.execute(
                    """INSERT INTO Cours (CodeCours, ChampNo, CoursDescriptif, NbPeriodes, NbGroupeInitial, EstCoursAutre)
                       VALUES (%(codecours)s, %(champno)s, %(coursdescriptif)s, %(nbperiodes)s, %(nbgroupeinitial)s, %(estcoursautre)s);""",
                    cours,
                )
            conn.commit()
        flash(f"{len(nouveaux_cours)} cours importés avec succès. Les anciens cours et attributions ont été supprimés.", "success")
    except psycopg2.Error as e:
        conn.rollback()
        current_app.logger.error(f"Erreur DB lors de l'importation des cours: {e}")
        flash(f"Erreur de base de données lors de l'importation des cours: {e}. L'importation a été annulée.", "error")
    return redirect(url_for("admin.page_administration_donnees"))


@bp.route("/importer_enseignants_excel", methods=["POST"])
@login_required
@admin_required
def api_importer_enseignants_excel() -> Any:
    """Importe les données des enseignants depuis un fichier Excel."""
    if "fichier_enseignants" not in request.files or not (file := request.files["fichier_enseignants"]) or not file.filename:
        flash("Aucun fichier valide sélectionné.", "warning")
        return redirect(url_for("admin.page_administration_donnees"))
    if not allowed_file(file.filename):
        flash("Type de fichier non autorisé (.xlsx seulement).", "error")
        return redirect(url_for("admin.page_administration_donnees"))

    nouveaux_enseignants = []
    try:
        sheet = openpyxl.load_workbook(file.stream).active
        if not isinstance(sheet, Worksheet) or sheet.max_row <= 1:
            raise ValueError("Fichier Excel vide ou invalide.")
        for row_idx, row in enumerate(iter(sheet.rows), 1):
            if row_idx == 1:
                continue
            values = [cell.value for cell in row]
            if not any(values):
                continue
            if len(values) < 4:
                values.extend([None] * (4 - len(values)))
            champ_no, nom, prenom, temps_plein = values[0], values[1], values[2], values[3]
            if not all([champ_no, nom, prenom]):
                flash(f"Ligne {row_idx} (Enseignants): Données essentielles manquantes (Champ, Nom, Prénom), ligne ignorée.", "warning")
                continue
            try:
                is_temps_plein = str(temps_plein).strip().upper() == "VRAI" if temps_plein else False
                nom_clean, prenom_clean = str(nom).strip(), str(prenom).strip()

                nouveaux_enseignants.append(
                    {
                        "nomcomplet": f"{prenom_clean} {nom_clean}",
                        "nom": nom_clean,
                        "prenom": prenom_clean,
                        "champno": str(champ_no).strip(),
                        "esttempsplein": is_temps_plein,
                    }
                )
            except (ValueError, TypeError) as conv_e:
                flash(
                    f"Ligne {row_idx} (Enseignants): Erreur de format de données ({conv_e}), ligne ignorée. Vérifiez 'VRAI/FAUX' pour 'Temps plein'.",
                    "warning",
                )
                continue

    except (InvalidFileException, ValueError, TypeError) as e:
        flash(
            f"Erreur lors de la lecture du fichier Excel: {e}. Assurez-vous qu'il s'agit d'un \
            fichier .xlsx valide et que les données sont au bon format.",
            "error",
        )
        return redirect(url_for("admin.page_administration_donnees"))

    if not nouveaux_enseignants:
        flash("Aucun enseignant valide trouvé dans le fichier après lecture.", "warning")
        return redirect(url_for("admin.page_administration_donnees"))

    conn = cast(connection, db.get_db())
    if not conn:
        flash("Erreur de connexion à la base de données. Impossible d'importer les enseignants.", "error")
        return redirect(url_for("admin.page_administration_donnees"))

    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM AttributionsCours;")
            cur.execute("DELETE FROM Enseignants;")
            for ens in nouveaux_enseignants:
                cur.execute(
                    """INSERT INTO Enseignants (NomComplet, Nom, Prenom, ChampNo, EstTempsPlein, EstFictif, PeutChoisirHorsChampPrincipal)
                       VALUES (%(nomcomplet)s, %(nom)s, %(prenom)s, %(champno)s, %(esttempsplein)s, FALSE, FALSE);""",
                    ens,
                )
            conn.commit()
        flash(f"{len(nouveaux_enseignants)} enseignants importés avec succès. Les anciens enseignants et attributions ont été supprimés.", "success")
    except psycopg2.Error as e:
        conn.rollback()
        current_app.logger.error(f"Erreur DB lors de l'importation des enseignants: {e}")
        flash(f"Erreur de base de données lors de l'importation des enseignants: {e}. L'importation a été annulée.", "error")
    return redirect(url_for("admin.page_administration_donnees"))


@bp.route("/api/cours/reassigner_champ", methods=["POST"])
@admin_api_required
def api_reassigner_cours_champ() -> Any:
    """API pour réassigner un cours à un nouveau champ."""
    data = request.get_json()
    if not data or not (code_cours := data.get("code_cours")) or not (nouveau_champ_no := data.get("nouveau_champ_no")):
        return jsonify({"success": False, "message": "Données manquantes."}), 400

    result = db.reassign_cours_to_champ(code_cours, nouveau_champ_no)
    if result:
        return jsonify(success=True, message=f"Cours '{code_cours}' réassigné au champ '{nouveau_champ_no}'.", **result)
    return jsonify({"success": False, "message": "Champ de destination invalide ou erreur base de données."}), 500
