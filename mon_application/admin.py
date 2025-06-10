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
from flask import Blueprint, current_app, flash, g, jsonify, redirect, render_template, request, session, url_for
from flask_login import current_user
from openpyxl.utils.exceptions import InvalidFileException  # Conservé car potentiellement utile
from openpyxl.worksheet.worksheet import Worksheet
from psycopg2.extensions import connection
from werkzeug.security import generate_password_hash

from . import database as db
from .utils import admin_api_required, admin_required

# Crée un Blueprint 'admin' avec un préfixe d'URL.
bp = Blueprint("admin", __name__, url_prefix="/admin")


# --- Fonctions utilitaires pour le sommaire (maintenant dépendantes de l'année) ---
def calculer_donnees_sommaire(annee_id: int) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]], float]:
    """Calcule les données agrégées pour la page sommaire globale pour une année donnée."""
    tous_enseignants_details = db.get_all_enseignants_avec_details(annee_id)
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
                    "est_verrouille": _enseignants[0][
                        "estverrouille"
                    ],  # Tous les enseignants d'un champ partagent le statut de verrouillage du champ
                }
                total_periodes_global_tp += total_periodes_champ
                nb_enseignants_tp_global += nb_enseignants_champ

    moyenne_generale_calculee = (total_periodes_global_tp / nb_enseignants_tp_global) if nb_enseignants_tp_global > 0 else 0.0
    return list(enseignants_par_champ_temp.values()), moyennes_par_champ_calculees, moyenne_generale_calculee


# --- ROUTES DES PAGES D'ADMINISTRATION (HTML) ---


@bp.route("/sommaire")
@admin_required
def page_sommaire() -> str:
    """Affiche la page du sommaire global pour l'année active."""
    if not g.annee_active:
        flash("Aucune année scolaire n'est disponible. Veuillez en créer une dans la section 'Données'.", "warning")
        return render_template("page_sommaire.html", enseignants_par_champ=[], moyennes_par_champ={}, moyenne_generale=0.0)

    annee_id = g.annee_active["annee_id"]
    enseignants_par_champ_data, moyennes_champs, moyenne_gen = calculer_donnees_sommaire(annee_id)

    return render_template(
        "page_sommaire.html",
        enseignants_par_champ=enseignants_par_champ_data,
        moyennes_par_champ=moyennes_champs,
        moyenne_generale=moyenne_gen,
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
        flash("Aucune année scolaire active. Veuillez en créer une pour gérer les données.", "warning")

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
        return jsonify({"success": False, "message": "Le libellé de l'année est requis."}), 400

    new_annee = db.create_annee_scolaire(libelle)
    if new_annee:
        # Si c'est la toute première année créée, la définir comme courante
        # g.toutes_les_annees est mis à jour par le décorateur @app.before_request dans __init__.py
        # après la création, donc on vérifie si la nouvelle année est la seule *activement* connue.
        # Idéalement, get_all_annees() devrait être appelé à nouveau ici pour une logique plus stricte,
        # mais pour simplifier, on se base sur le fait que si aucune n'était courante avant, celle-ci le devient.
        if not g.annee_courante:  # Ou si len(db.get_all_annees()) == 1 après création
            db.set_annee_courante(new_annee["annee_id"])
            new_annee["est_courante"] = True
        current_app.logger.info(f"Année scolaire '{libelle}' créée avec ID {new_annee['annee_id']}.")
        return jsonify({"success": True, "message": f"Année '{libelle}' créée.", "annee": new_annee}), 201

    return jsonify({"success": False, "message": f"L'année '{libelle}' existe déjà."}), 409


@bp.route("/api/annees/changer_active", methods=["POST"])
@admin_api_required
def api_changer_annee_active() -> Any:
    """API pour changer l'année de travail de l'admin (stockée en session)."""
    data = request.get_json()
    if not data or not (annee_id := data.get("annee_id")):
        return jsonify({"success": False, "message": "ID de l'année manquant."}), 400

    session["annee_scolaire_id"] = annee_id
    # Log pour suivi
    annee_selectionnee = next((annee for annee in g.toutes_les_annees if annee["annee_id"] == annee_id), None)
    if annee_selectionnee:
        current_app.logger.info(f"Année de travail changée pour l'admin '{current_user.username}' : '{annee_selectionnee['libelle_annee']}'.")
    return jsonify({"success": True, "message": "Année de travail changée."})


@bp.route("/api/annees/set_courante", methods=["POST"])
@admin_api_required
def api_set_annee_courante() -> Any:
    """API pour définir l'année courante pour toute l'application."""
    data = request.get_json()
    if not data or not (annee_id := data.get("annee_id")):
        return jsonify({"success": False, "message": "ID de l'année manquant."}), 400

    if db.set_annee_courante(annee_id):
        # Log pour suivi
        annee_maj = next((annee for annee in g.toutes_les_annees if annee["annee_id"] == annee_id), None)
        if annee_maj:
            current_app.logger.info(f"Année courante de l'application définie sur : '{annee_maj['libelle_annee']}'.")
        return jsonify({"success": True, "message": "Nouvelle année courante définie."})

    return jsonify({"success": False, "message": "Erreur lors de la mise à jour."}), 500


# --- API adaptées pour l'année scolaire ---


@bp.route("/api/sommaire/donnees", methods=["GET"])
@admin_api_required
def api_get_donnees_sommaire() -> Any:
    """API pour récupérer les données du sommaire pour l'année active."""
    if not g.annee_active:
        current_app.logger.warning("API sommaire: Aucune année active, retour de données vides.")
        return jsonify(enseignants_par_champ=[], moyennes_par_champ={}, moyenne_generale=0.0)

    annee_id = g.annee_active["annee_id"]
    enseignants_groupes, moyennes_champs, moyenne_gen = calculer_donnees_sommaire(annee_id)
    return jsonify(enseignants_par_champ=enseignants_groupes, moyennes_par_champ=moyennes_champs, moyenne_generale=moyenne_gen)


@bp.route("/api/cours/creer", methods=["POST"])
@admin_api_required
def api_create_cours() -> Any:
    """API pour créer un nouveau cours dans l'année active."""
    if not g.annee_active:
        return jsonify({"success": False, "message": "Aucune année scolaire active."}), 400
    data = request.get_json()
    if not data or not all(k in data for k in ["codecours", "champno", "coursdescriptif", "nbperiodes", "nbgroupeinitial"]):
        return jsonify({"success": False, "message": "Données manquantes."}), 400
    try:
        new_cours = db.create_cours(data, g.annee_active["annee_id"])
        current_app.logger.info(f"Cours '{data['codecours']}' créé pour l'année ID {g.annee_active['annee_id']}.")
        return jsonify({"success": True, "message": "Cours créé.", "cours": new_cours}), 201
    except psycopg2.errors.UniqueViolation:
        return jsonify({"success": False, "message": "Ce code de cours existe déjà pour cette année."}), 409
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
        return jsonify({"success": False, "message": "Cours non trouvé pour cette année."}), 404
    return jsonify({"success": True, "cours": cours})


@bp.route("/api/cours/<path:code_cours>/modifier", methods=["POST"])
@admin_api_required
def api_update_cours(code_cours: str) -> Any:
    """API pour modifier un cours de l'année active."""
    if not g.annee_active:
        return jsonify({"success": False, "message": "Aucune année scolaire active."}), 400
    data = request.get_json()
    if not data or not all(k in data for k in ["champno", "coursdescriptif", "nbperiodes", "nbgroupeinitial"]):
        return jsonify({"success": False, "message": "Données manquantes."}), 400
    try:
        updated_cours = db.update_cours(code_cours, g.annee_active["annee_id"], data)
        if not updated_cours:
            return jsonify({"success": False, "message": "Cours non trouvé pour cette année."}), 404
        current_app.logger.info(f"Cours '{code_cours}' modifié pour l'année ID {g.annee_active['annee_id']}.")
        return jsonify({"success": True, "message": "Cours mis à jour.", "cours": updated_cours})
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
        current_app.logger.info(f"Cours '{code_cours}' supprimé pour l'année ID {g.annee_active['annee_id']}.")
    return jsonify({"success": success, "message": message}), status_code


@bp.route("/api/enseignants/creer", methods=["POST"])
@admin_api_required
def api_create_enseignant() -> Any:
    """API pour créer un nouvel enseignant dans l'année active."""
    if not g.annee_active:
        return jsonify({"success": False, "message": "Aucune année scolaire active."}), 400
    data = request.get_json()
    if not data or not all(k in data for k in ["nom", "prenom", "champno", "esttempsplein"]):
        return jsonify({"success": False, "message": "Données manquantes."}), 400
    try:
        new_enseignant = db.create_enseignant(data, g.annee_active["annee_id"])
        current_app.logger.info(f"Enseignant '{data['nom']}' créé pour l'année ID {g.annee_active['annee_id']}.")
        return jsonify({"success": True, "message": "Enseignant créé.", "enseignant": new_enseignant}), 201
    except psycopg2.errors.UniqueViolation:
        return jsonify({"success": False, "message": "Cet enseignant (nom/prénom) existe déjà pour cette année."}), 409
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
        return jsonify({"success": False, "message": "Enseignant non trouvé ou non modifiable."}), 404
    return jsonify({"success": True, "enseignant": enseignant})


@bp.route("/api/enseignants/<int:enseignant_id>/modifier", methods=["POST"])
@admin_api_required
def api_update_enseignant(enseignant_id: int) -> Any:
    """API pour modifier un enseignant existant."""
    data = request.get_json()
    if not data or not all(k in data for k in ["nom", "prenom", "champno", "esttempsplein"]):
        return jsonify({"success": False, "message": "Données manquantes."}), 400
    try:
        # L'année d'un enseignant n'est pas modifiable directement.
        # Pour changer un enseignant d'année, il faudrait le supprimer et le recréer dans la nouvelle année.
        updated_enseignant = db.update_enseignant(enseignant_id, data)
        if not updated_enseignant:
            return jsonify({"success": False, "message": "Enseignant non trouvé ou non modifiable (ex: fictif)."}), 404
        current_app.logger.info(f"Enseignant ID {enseignant_id} modifié.")
        return jsonify({"success": True, "message": "Enseignant mis à jour.", "enseignant": updated_enseignant})
    except psycopg2.errors.UniqueViolation:
        # Cette erreur peut survenir si la combinaison nom/prénom/année existe déjà
        # suite à une tentative de modification qui recréerait un doublon.
        return jsonify({"success": False, "message": "Un enseignant avec ce nom/prénom existe déjà pour l'année de cet enseignant."}), 409
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
        # La suppression des fictifs devrait se faire via la page de champ si nécessaire (non implémenté ici)
        return jsonify({"success": False, "message": "Impossible de supprimer un enseignant fictif via cette interface."}), 403

    if db.delete_enseignant(enseignant_id):
        current_app.logger.info(f"Enseignant ID {enseignant_id} supprimé.")
        return jsonify({"success": True, "message": "Enseignant et ses attributions supprimés."})
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
        flash("Format de fichier invalide. Veuillez utiliser un fichier Excel (.xlsx ou .xls).", "error")
        return redirect(url_for("admin.page_administration_donnees"))

    nouveaux_cours = []
    try:
        workbook = openpyxl.load_workbook(file.stream)
        sheet = workbook.active
        if not isinstance(sheet, Worksheet) or sheet.max_row <= 1:
            raise ValueError("Fichier Excel vide ou ne contient que l'en-tête.")

        _header = [cell.value for cell in sheet[1]]
        # Valider l'en-tête si nécessaire, ex:
        # attendu = ["ChampNo", "CodeCours", "TypeCours", "CoursDescriptif", ...]
        # if header[:len(attendu)] != attendu:
        #     raise ValueError("En-tête du fichier Excel incorrect.")

        for row_idx, row in enumerate(sheet.iter_rows(min_row=2), start=2):  # Commence à la ligne 2
            values = [cell.value for cell in row]
            if not any(v is not None and str(v).strip() != "" for v in values[:6]):  # Vérifie les 6 premières colonnes pertinentes
                current_app.logger.debug(f"Ligne {row_idx} ignorée (vide ou non pertinente).")
                continue  # Ignore les lignes vides

            # Extrait les valeurs en s'assurant qu'elles ne sont pas None avant de stripper
            champ_no_raw = values[0]
            code_cours_raw = values[1]
            # type_cours_raw = values[2] # Ignoré pour l'instant
            desc_raw = values[3]
            nb_grp_raw = values[4]
            nb_per_raw = values[5]
            # champ_affectation_raw = values[6] # Ignoré pour l'instant
            est_autre_raw = values[7]

            # Validation de base et conversion
            if not all([champ_no_raw, code_cours_raw, desc_raw, nb_grp_raw is not None, nb_per_raw is not None]):
                flash(f"Ligne {row_idx}: Données manquantes. Vérifiez ChampNo, CodeCours, Descriptif, NbGroupes, NbPériodes.", "warning")
                continue

            try:
                champ_no = str(champ_no_raw).strip()
                code_cours = str(code_cours_raw).strip()
                desc = str(desc_raw).strip()
                nb_grp = int(float(str(nb_grp_raw).replace(",", ".")))
                nb_per = float(str(nb_per_raw).replace(",", "."))
                # --- CORRECTION APPLIQUÉE ICI ---
                est_autre = str(est_autre_raw).strip().upper() in ("VRAI", "TRUE") if est_autre_raw is not None else False
            except ValueError as ve:
                flash(f"Ligne {row_idx}: Erreur de type de données ({ve}). Vérifiez les nombres et le format 'VRAI/FAUX'.", "warning")
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
    except ValueError as e_val:  # Capturer les ValueErrors spécifiques de la logique de parsing
        flash(str(e_val), "error")
        return redirect(url_for("admin.page_administration_donnees"))
    except Exception as e_gen:
        current_app.logger.error(f"Erreur imprévue lecture Excel cours: {e_gen}", exc_info=True)
        flash(f"Erreur inattendue lors de la lecture du fichier Excel : {e_gen}", "error")
        return redirect(url_for("admin.page_administration_donnees"))

    if not nouveaux_cours:
        flash("Aucun cours valide trouvé dans le fichier après traitement. Vérifiez le contenu et les messages d'avertissement.", "warning")
        return redirect(url_for("admin.page_administration_donnees"))

    conn = cast(connection, db.get_db())
    if not conn:
        flash("Erreur de connexion à la base de données.", "error")
        return redirect(url_for("admin.page_administration_donnees"))

    try:
        with conn.cursor() as cur:
            # Opérations transactionnelles
            current_app.logger.info(f"Suppression des anciennes attributions pour l'année ID {annee_id}...")
            nb_attr_supp = db.delete_all_attributions_for_year(annee_id)
            current_app.logger.info(f"{nb_attr_supp} attributions supprimées.")

            current_app.logger.info(f"Suppression des anciens cours pour l'année ID {annee_id}...")
            nb_cours_supp = db.delete_all_cours_for_year(annee_id)
            current_app.logger.info(f"{nb_cours_supp} cours supprimés.")

            current_app.logger.info(f"Insertion de {len(nouveaux_cours)} nouveaux cours...")
            for cours in nouveaux_cours:
                cur.execute(
                    """INSERT INTO Cours (annee_id, CodeCours, ChampNo, CoursDescriptif, NbPeriodes, NbGroupeInitial, EstCoursAutre)
                       VALUES (%(annee_id)s, %(codecours)s, %(champno)s, %(coursdescriptif)s, %(nbperiodes)s, %(nbgroupeinitial)s, \
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
        flash(f"Erreur base de données: {e_db}. L'importation a été annulée.", "error")
    except Exception as e_final:  # Pour toute autre exception durant la transaction
        conn.rollback()
        current_app.logger.error(f"Erreur inconnue durant transaction d'importation cours: {e_final}", exc_info=True)
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
        flash("Format de fichier invalide. Veuillez utiliser un fichier Excel (.xlsx ou .xls).", "error")
        return redirect(url_for("admin.page_administration_donnees"))

    nouveaux_enseignants = []
    try:
        workbook = openpyxl.load_workbook(file.stream)
        sheet = workbook.active
        if not isinstance(sheet, Worksheet) or sheet.max_row <= 1:
            raise ValueError("Fichier Excel vide ou ne contient que l'en-tête.")

        # Optionnel: valider l'en-tête
        # header = [cell.value for cell in sheet[1]]
        # attendu_ens = ["ChampNo", "Nom", "Prenom", "EstTempsPlein"]
        # if header[:len(attendu_ens)] != attendu_ens:
        #     raise ValueError("En-tête du fichier Excel des enseignants incorrect.")

        for row_idx, row in enumerate(sheet.iter_rows(min_row=2), start=2):  # Commence à la ligne 2
            values = [cell.value for cell in row]
            # Ignorer les lignes manifestement vides (basé sur les 4 premières colonnes)
            if not any(v is not None and str(v).strip() != "" for v in values[:4]):
                current_app.logger.debug(f"Ligne enseignant {row_idx} ignorée (vide).")
                continue

            champ_no_raw, nom_raw, prenom_raw, temps_plein_raw = values[0], values[1], values[2], values[3]

            if not all([champ_no_raw, nom_raw, prenom_raw, temps_plein_raw is not None]):
                flash(f"Ligne enseignant {row_idx}: Données manquantes. Vérifiez ChampNo, Nom, Prénom, EstTempsPlein.", "warning")
                continue

            try:
                champ_no = str(champ_no_raw).strip()
                nom_clean = str(nom_raw).strip()
                prenom_clean = str(prenom_raw).strip()
                # --- CORRECTION APPLIQUÉE ICI ---
                est_temps_plein = str(temps_plein_raw).strip().upper() in ("VRAI", "TRUE")
            except ValueError as ve_ens:  # Peu probable ici, mais par sécurité
                flash(f"Ligne enseignant {row_idx}: Erreur de conversion de données ({ve_ens}).", "warning")
                continue

            if not nom_clean or not prenom_clean:  # S'assurer que nom et prénom ne sont pas vides après strip
                flash(f"Ligne enseignant {row_idx}: Nom ou Prénom vide après nettoyage.", "warning")
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
    except ValueError as e_val_ens:  # Capturer les ValueErrors spécifiques de la logique de parsing
        flash(str(e_val_ens), "error")
        return redirect(url_for("admin.page_administration_donnees"))
    except Exception as e_gen_ens:
        current_app.logger.error(f"Erreur imprévue lecture Excel enseignants: {e_gen_ens}", exc_info=True)
        flash(f"Erreur inattendue lors de la lecture du fichier Excel des enseignants : {e_gen_ens}", "error")
        return redirect(url_for("admin.page_administration_donnees"))

    if not nouveaux_enseignants:
        flash("Aucun enseignant valide trouvé dans le fichier après traitement. Vérifiez le contenu et les messages d'avertissement.", "warning")
        return redirect(url_for("admin.page_administration_donnees"))

    conn = cast(connection, db.get_db())
    if not conn:
        flash("Erreur de connexion à la base de données.", "error")
        return redirect(url_for("admin.page_administration_donnees"))

    try:
        with conn.cursor() as cur:
            current_app.logger.info(f"Suppression des anciennes attributions pour l'année ID {annee_id} (avant import enseignants)...")
            nb_attr_supp_ens = db.delete_all_attributions_for_year(annee_id)
            current_app.logger.info(f"{nb_attr_supp_ens} attributions supprimées.")

            current_app.logger.info(f"Suppression des anciens enseignants pour l'année ID {annee_id}...")
            nb_ens_supp = db.delete_all_enseignants_for_year(annee_id)
            current_app.logger.info(f"{nb_ens_supp} enseignants supprimés.")

            current_app.logger.info(f"Insertion de {len(nouveaux_enseignants)} nouveaux enseignants...")
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
        current_app.logger.error(f"Erreur DB importation enseignants: {e_db_ens}", exc_info=True)
        flash(f"Erreur base de données: {e_db_ens}. L'importation a été annulée.", "error")
    except Exception as e_final_ens:  # Pour toute autre exception durant la transaction
        conn.rollback()
        current_app.logger.error(f"Erreur inconnue durant transaction d'importation enseignants: {e_final_ens}", exc_info=True)
        flash(f"Erreur inconnue: {e_final_ens}. L'importation a été annulée.", "error")

    return redirect(url_for("admin.page_administration_donnees"))


# --- API non modifiées car indépendantes de l'année ---
@bp.route("/api/champs/<string:champ_no>/basculer_verrou", methods=["POST"])
@admin_api_required
def api_basculer_verrou_champ(champ_no: str) -> Any:
    """Bascule le statut de verrouillage d'un champ (indépendant de l'année)."""
    nouveau_statut = db.toggle_champ_lock_status(champ_no)
    if nouveau_statut is None:
        return jsonify({"success": False, "message": f"Impossible de modifier le verrou du champ {champ_no}."}), 500
    message = f"Le champ {champ_no} a été {'verrouillé' if nouveau_statut else 'déverrouillé'}."
    current_app.logger.info(message)
    return jsonify({"success": True, "message": message, "est_verrouille": nouveau_statut})


@bp.route("/api/utilisateurs", methods=["GET"])
@admin_api_required
def api_get_all_users() -> Any:
    """Récupère tous les utilisateurs avec des informations sur leur nombre (admin/total)."""
    return jsonify(users=db.get_all_users_with_access_info(), admin_count=db.get_admin_count())


@bp.route("/api/utilisateurs/creer", methods=["POST"])
@admin_api_required
def api_create_user() -> Any:
    """Crée un nouvel utilisateur."""
    data = request.get_json()
    if not data or not (username := data.get("username", "").strip()) or not (password := data.get("password", "").strip()):
        return jsonify({"success": False, "message": "Nom d'utilisateur et mot de passe requis."}), 400
    if len(password) < 6:  # Exemple de règle de validation simple pour le mot de passe
        return jsonify({"success": False, "message": "Le mot de passe doit faire au moins 6 caractères."}), 400

    is_admin = data.get("is_admin", False)
    allowed_champs = data.get("allowed_champs", [])  # Doit être une liste de champ_no (strings)
    hashed_pwd = generate_password_hash(password)
    user = db.create_user(username, hashed_pwd, is_admin)

    if not user:  # psycopg2.errors.UniqueViolation gérée dans db.create_user
        return jsonify({"success": False, "message": "Ce nom d'utilisateur est déjà pris."}), 409

    # Si ce n'est pas un admin et que des droits spécifiques aux champs sont donnés
    if not is_admin and allowed_champs:
        if not db.update_user_champ_access(user["id"], allowed_champs):
            # En cas d'échec de l'attribution des droits, on annule la création de l'utilisateur
            # pour éviter un état incohérent.
            db.delete_user_data(user["id"])  # Assurez-vous que cette fonction ne logue pas d'erreur si l'utilisateur n'existe plus.
            current_app.logger.error(f"Échec de l'attribution des droits pour le nouvel utilisateur {username}, création annulée.")
            return jsonify({"success": False, "message": "Erreur lors de l'attribution des accès aux champs."}), 500

    current_app.logger.info(f"Utilisateur '{username}' créé avec ID {user['id']}.")
    return jsonify({"success": True, "message": f"Utilisateur '{username}' créé!", "user_id": user["id"]}), 201


@bp.route("/api/utilisateurs/<int:user_id>/update_access", methods=["POST"])
@admin_api_required
def api_update_user_access(user_id: int) -> Any:
    """Met à jour les accès aux champs pour un utilisateur non-admin."""
    data = request.get_json()
    if not data or not isinstance(champ_nos := data.get("champ_nos"), list):
        return jsonify({"success": False, "message": "Données invalides (champ_nos doit être une liste)."}), 400

    target_user = db.get_user_by_id(user_id)
    if not target_user:
        return jsonify({"success": False, "message": "Utilisateur non trouvé."}), 404
    if target_user["is_admin"]:
        return jsonify({"success": False, "message": "Les accès d'un administrateur ne peuvent pas être modifiés via cette interface."}), 403

    if db.update_user_champ_access(user_id, champ_nos):
        current_app.logger.info(f"Accès aux champs mis à jour pour l'utilisateur ID {user_id}.")
        return jsonify({"success": True, "message": "Accès mis à jour."})
    current_app.logger.error(f"Échec de la mise à jour des accès pour l'utilisateur ID {user_id}.")
    return jsonify({"success": False, "message": "Erreur lors de la mise à jour des accès."}), 500


@bp.route("/api/utilisateurs/<int:user_id>/delete", methods=["POST"])
@admin_api_required
def api_delete_user(user_id: int) -> Any:
    """Supprime un utilisateur."""
    if user_id == current_user.id:  # L'utilisateur ne peut pas se supprimer lui-même
        return jsonify({"success": False, "message": "Vous ne pouvez pas supprimer votre propre compte."}), 403

    target_user = db.get_user_by_id(user_id)
    if not target_user:
        return jsonify({"success": False, "message": "Utilisateur non trouvé."}), 404

    # Empêcher la suppression du dernier administrateur
    if target_user["is_admin"] and db.get_admin_count() <= 1:
        return jsonify({"success": False, "message": "Impossible de supprimer le dernier administrateur."}), 403

    if db.delete_user_data(user_id):
        current_app.logger.info(f"Utilisateur ID {user_id} ('{target_user['username']}') supprimé par '{current_user.username}'.")
        return jsonify({"success": True, "message": "Utilisateur supprimé."})

    current_app.logger.error(f"Échec de la suppression de l'utilisateur ID {user_id} ('{target_user['username']}').")
    return jsonify({"success": False, "message": "Échec de la suppression de l'utilisateur."}), 500


@bp.route("/api/cours/reassigner_champ", methods=["POST"])
@admin_api_required
def api_reassigner_cours_champ() -> Any:
    """API pour réassigner un cours à un nouveau champ, pour l'année active."""
    if not g.annee_active:
        return jsonify({"success": False, "message": "Aucune année scolaire active."}), 400

    data = request.get_json()
    if not data or not (code_cours := data.get("code_cours")) or not (nouveau_champ_no := data.get("nouveau_champ_no")):
        return jsonify({"success": False, "message": "Données manquantes : 'code_cours' et 'nouveau_champ_no' requis."}), 400

    result = db.reassign_cours_to_champ(code_cours, g.annee_active["annee_id"], nouveau_champ_no)
    if result:
        current_app.logger.info(f"Cours '{code_cours}' réassigné au champ '{nouveau_champ_no}' pour l'année ID {g.annee_active['annee_id']}.")
        return jsonify(success=True, message=f"Cours '{code_cours}' réassigné au champ '{nouveau_champ_no}'.", **result)

    # Le message d'erreur de db.reassign_cours_to_champ est déjà assez générique
    # On pourrait ajouter plus de détails si la fonction retournait des codes d'erreur spécifiques.
    current_app.logger.warning(
        f"Échec de la réassignation du cours '{code_cours}' au champ '{nouveau_champ_no}' pour l'année ID {g.annee_active['annee_id']}."
    )
    return jsonify(
        {
            "success": False,
            "message": "Impossible de réassigner le cours. Vérifiez que le cours et le nouveau champ existent pour cette année scolaire.",
        }
    ), 500
