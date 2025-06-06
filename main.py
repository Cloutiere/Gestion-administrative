import datetime
import os

import openpyxl  # Pour la manipulation des fichiers Excel
import psycopg2
import psycopg2.extras  # Nécessaire pour DictCursor
from flask import Flask, flash, g, jsonify, redirect, render_template, request, url_for
from openpyxl.utils.exceptions import InvalidFileException
from openpyxl.worksheet.worksheet import Worksheet  # Import pour l'assertion de type

# --- Configuration de l'application Flask ---
app = Flask(__name__)
app.secret_key = os.urandom(24)  # Clé secrète pour la session Flask
UPLOAD_FOLDER = "uploads"
ALLOWED_EXTENSIONS = {"xlsx"}
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# --- Configuration de la base de données ---
DB_HOST = os.environ.get("PGHOST")
DB_NAME = os.environ.get("PGDATABASE")
DB_USER = os.environ.get("PGUSER")
DB_PASS = os.environ.get("PGPASSWORD")
DB_PORT = os.environ.get("PGPORT", "5432")


def get_db_connection_string():
    """Construit la chaîne de connexion à la base de données."""
    return f"dbname='{DB_NAME}' user='{DB_USER}' host='{DB_HOST}' password='{DB_PASS}' port='{DB_PORT}'"


def get_db():
    """Ouvre une nouvelle connexion à la base de données si nécessaire."""
    if "db" not in g:
        try:
            conn_string = get_db_connection_string()
            g.db = psycopg2.connect(conn_string)
        except psycopg2.Error as e:
            app.logger.error(f"Erreur de connexion à la base de données: {e}")
            g.db = None
    return g.db


@app.teardown_appcontext
def close_db(_exception=None):
    """Ferme la connexion à la base de données."""
    db = g.pop("db", None)
    if db is not None and not db.closed:
        try:
            db.close()
        except psycopg2.Error as e:
            app.logger.error(f"Erreur lors de la fermeture de la connexion DB: {e}")


# --- Fonctions d'accès aux données (DAO) ---


def get_all_champs():
    """Récupère tous les champs, triés par numéro."""
    db = get_db()
    if not db:
        return []
    try:
        with db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT ChampNo, ChampNom FROM Champs ORDER BY ChampNo;")
            return [dict(row) for row in cur.fetchall()]
    except psycopg2.Error as e:
        app.logger.error(f"Erreur DAO get_all_champs: {e}")
        if db and not db.closed:
            db.rollback()
        return []


def get_champ_details(champ_no):
    """Récupère les détails d'un champ spécifique."""
    db = get_db()
    if not db:
        return None
    try:
        with db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT ChampNo, ChampNom FROM Champs WHERE ChampNo = %s;", (champ_no,))
            champ_row = cur.fetchone()
        return dict(champ_row) if champ_row else None
    except psycopg2.Error as e:
        app.logger.error(f"Erreur DAO get_champ_details pour {champ_no}: {e}")
        if db and not db.closed:
            db.rollback()
        return None


def get_enseignants_par_champ(champ_no):
    """Récupère les enseignants d'un champ, triés."""
    db = get_db()
    if not db:
        return []
    try:
        with db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """
                SELECT EnseignantID, NomComplet, EstTempsPlein, EstFictif, PeutChoisirHorsChampPrincipal
                FROM Enseignants WHERE ChampNo = %s ORDER BY EstFictif, NomComplet;
                """,
                (champ_no,),
            )
            return [dict(e) for e in cur.fetchall()]
    except psycopg2.Error as e:
        app.logger.error(f"Erreur DAO get_enseignants_par_champ pour {champ_no}: {e}")
        if db and not db.closed:
            db.rollback()
        return []


def get_all_enseignants_avec_details():
    """Récupère tous les enseignants avec détails et périodes."""
    db = get_db()
    if not db:
        return []
    enseignants_complets = []
    try:
        with db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """
                SELECT e.EnseignantID, e.NomComplet, e.EstTempsPlein, e.EstFictif, e.ChampNo, ch.ChampNom
                FROM Enseignants e JOIN Champs ch ON e.ChampNo = ch.ChampNo
                ORDER BY e.ChampNo, e.EstFictif, e.NomComplet;
                """
            )
            enseignants_bruts = [dict(row) for row in cur.fetchall()]

        for ens_brut in enseignants_bruts:
            periodes = calculer_periodes_enseignant(ens_brut["enseignantid"])
            compte_pour_moyenne_champ = ens_brut["esttempsplein"] and not ens_brut["estfictif"]
            enseignants_complets.append(
                {
                    **ens_brut,
                    "periodes_cours": periodes["periodes_cours"],
                    "periodes_autres": periodes["periodes_autres"],
                    "total_periodes": periodes["total_periodes"],
                    "compte_pour_moyenne_champ": compte_pour_moyenne_champ,
                }
            )
        return enseignants_complets
    except psycopg2.Error as e:
        app.logger.error(f"Erreur DAO get_all_enseignants_avec_details: {e}")
        if db and not db.closed:
            db.rollback()
        return []


def get_cours_disponibles_par_champ(champ_no):
    """Récupère les cours disponibles pour un champ, avec groupes restants."""
    db = get_db()
    if not db:
        return []
    try:
        with db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """
                SELECT c.CodeCours, c.CoursDescriptif, c.NbPeriodes, c.EstCoursAutre, c.NbGroupeInitial,
                       (c.NbGroupeInitial - COALESCE(SUM(ac.NbGroupesPris), 0)) AS grprestant
                FROM Cours c LEFT JOIN AttributionsCours ac ON c.CodeCours = ac.CodeCours
                WHERE c.ChampNo = %s
                GROUP BY c.CodeCours, c.CoursDescriptif, c.NbPeriodes, c.EstCoursAutre, c.NbGroupeInitial
                ORDER BY c.EstCoursAutre, c.CodeCours;
                """,
                (champ_no,),
            )
            return [dict(cr) for cr in cur.fetchall()]
    except psycopg2.Error as e:
        app.logger.error(f"Erreur DAO get_cours_disponibles_par_champ pour {champ_no}: {e}")
        if db and not db.closed:
            db.rollback()
        return []


def get_attributions_enseignant(enseignant_id):
    """Récupère toutes les attributions de cours pour un enseignant."""
    db = get_db()
    if not db:
        return []
    try:
        with db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """
                SELECT ac.AttributionID, ac.CodeCours, ac.NbGroupesPris, c.CoursDescriptif,
                       c.NbPeriodes, c.EstCoursAutre, c.ChampNo AS ChampOrigineCours
                FROM AttributionsCours ac JOIN Cours c ON ac.CodeCours = c.CodeCours
                WHERE ac.EnseignantID = %s
                ORDER BY c.EstCoursAutre, c.CoursDescriptif;
                """,
                (enseignant_id,),
            )
            return [dict(a) for a in cur.fetchall()]
    except psycopg2.Error as e:
        app.logger.error(f"Erreur DAO get_attributions_enseignant pour {enseignant_id}: {e}")
        if db and not db.closed:
            db.rollback()
        return []


def calculer_periodes_enseignant(enseignant_id):
    """Calcule le total des périodes de cours et autres pour un enseignant."""
    attributions = get_attributions_enseignant(enseignant_id)
    periodes_enseignement = sum(a["nbperiodes"] * a["nbgroupespris"] for a in attributions if not a["estcoursautre"])
    periodes_autres = sum(a["nbperiodes"] * a["nbgroupespris"] for a in attributions if a["estcoursautre"])
    return {
        "periodes_cours": periodes_enseignement,
        "periodes_autres": periodes_autres,
        "total_periodes": periodes_enseignement + periodes_autres,
    }


def get_groupes_restants_pour_cours(code_cours):
    """Calcule le nombre de groupes restants pour un cours."""
    db = get_db()
    if not db:
        app.logger.warning(f"get_groupes_restants_pour_cours: Connexion DB échouée pour {code_cours}.")
        return 0
    try:
        with db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """
                SELECT (c.NbGroupeInitial - COALESCE(SUM(ac.NbGroupesPris), 0)) AS grprestant
                FROM Cours c LEFT JOIN AttributionsCours ac ON c.CodeCours = ac.CodeCours
                WHERE c.CodeCours = %s GROUP BY c.NbGroupeInitial;
                """,
                (code_cours,),
            )
            result = cur.fetchone()
        return result["grprestant"] if result and result["grprestant"] is not None else 0
    except psycopg2.Error as e:
        app.logger.error(f"Erreur DAO get_groupes_restants_pour_cours pour {code_cours}: {e}")
        if db and not db.closed:
            db.rollback()
        return 0


def get_all_cours_avec_details_champ():
    """Récupère tous les cours avec détails de leur champ."""
    db = get_db()
    if not db:
        return []
    try:
        with db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """
                SELECT c.CodeCours, c.CoursDescriptif, c.ChampNo, ch.ChampNom
                FROM Cours c JOIN Champs ch ON c.ChampNo = ch.ChampNo ORDER BY c.CodeCours;
                """
            )
            return [dict(row) for row in cur.fetchall()]
    except psycopg2.Error as e:
        app.logger.error(f"Erreur DAO get_all_cours_avec_details_champ: {e}")
        if db and not db.closed:
            db.rollback()
        return []


# --- ROUTES DE L'APPLICATION (Pages HTML) ---
@app.route("/")
def index():
    """Affiche la page d'accueil."""
    champs = get_all_champs()
    current_year = datetime.datetime.now().year
    return render_template("index.html", champs=champs, SCRIPT_YEAR=current_year)


@app.route("/champ/<string:champ_no>")
def page_champ(champ_no):
    """Affiche la page détaillée d'un champ."""
    champ_details = get_champ_details(champ_no)
    if not champ_details:
        flash(f"Le champ {champ_no} n'a pas été trouvé.", "error")
        return redirect(url_for("index"))

    enseignants_bruts = get_enseignants_par_champ(champ_no)
    cours_disponibles_bruts = get_cours_disponibles_par_champ(champ_no)

    cours_enseignement_champ = [c for c in cours_disponibles_bruts if not c["estcoursautre"]]
    cours_autres_taches_champ = [c for c in cours_disponibles_bruts if c["estcoursautre"]]

    enseignants_complets_pour_template = []
    sommaire_champ_data_pour_template = []
    total_periodes_tp_pour_moyenne = 0
    nb_enseignants_tp_pour_moyenne = 0

    for ens_brut in enseignants_bruts:
        periodes = calculer_periodes_enseignant(ens_brut["enseignantid"])
        attributions = get_attributions_enseignant(ens_brut["enseignantid"])
        enseignants_complets_pour_template.append(
            {**ens_brut, "attributions": attributions, "periodes_actuelles": periodes}
        )

        sommaire_champ_data_pour_template.append(
            {
                "enseignant_id": ens_brut["enseignantid"],
                "nom": ens_brut["nomcomplet"],
                "periodes_cours": periodes["periodes_cours"],
                "periodes_autres": periodes["periodes_autres"],
                "total_periodes": periodes["total_periodes"],
                "est_temps_plein": ens_brut["esttempsplein"],
                "est_fictif": ens_brut["estfictif"],
            }
        )
        if ens_brut["esttempsplein"] and not ens_brut["estfictif"]:
            total_periodes_tp_pour_moyenne += periodes["total_periodes"]
            nb_enseignants_tp_pour_moyenne += 1

    moyenne_champ = (
        (total_periodes_tp_pour_moyenne / nb_enseignants_tp_pour_moyenne) if nb_enseignants_tp_pour_moyenne > 0 else 0
    )
    current_year = datetime.datetime.now().year

    return render_template(
        "page_champ.html",
        champ=champ_details,
        enseignants=enseignants_complets_pour_template,
        cours_enseignement_champ=cours_enseignement_champ,
        cours_autres_taches_champ=cours_autres_taches_champ,
        cours_disponibles_pour_tableau_restant=cours_disponibles_bruts,
        taches_sommaire_champ=sommaire_champ_data_pour_template,
        moyenne_champ_initiale=moyenne_champ,
        SCRIPT_YEAR=current_year,
    )


@app.route("/sommaire")
def page_sommaire():
    """Affiche la page du sommaire global."""
    enseignants, moyennes_champs, moyenne_gen = calculer_donnees_sommaire()
    current_year = datetime.datetime.now().year
    return render_template(
        "page_sommaire.html",
        enseignants=enseignants,
        moyennes_par_champ=moyennes_champs,
        moyenne_generale=moyenne_gen,
        SCRIPT_YEAR=current_year,
    )


@app.route("/administration")
def page_administration_donnees():
    """Affiche la page d'administration des données."""
    cours_pour_reassignation = get_all_cours_avec_details_champ()
    champs_pour_destination = get_all_champs()
    current_year = datetime.datetime.now().year
    return render_template(
        "administration_donnees.html",
        cours_a_reassigner=cours_pour_reassignation or [],
        champs_destination=champs_pour_destination or [],
        SCRIPT_YEAR=current_year,
    )


# --- Fonctions utilitaires pour le sommaire ---
def calculer_donnees_sommaire():
    """Calcule les données agrégées pour la page sommaire."""
    tous_enseignants_details = get_all_enseignants_avec_details()
    moyennes_par_champ_calculees = {}
    total_periodes_global_tp = 0
    nb_enseignants_tp_global = 0

    for ens in tous_enseignants_details:
        if ens["compte_pour_moyenne_champ"]:
            champ_no = ens["champno"]
            if champ_no not in moyennes_par_champ_calculees:
                moyennes_par_champ_calculees[champ_no] = {
                    "champ_nom": ens["champnom"],
                    "total_periodes": 0,
                    "nb_enseignants": 0,
                    "moyenne": 0.0,
                }
            moyennes_par_champ_calculees[champ_no]["total_periodes"] += ens["total_periodes"]
            moyennes_par_champ_calculees[champ_no]["nb_enseignants"] += 1

            total_periodes_global_tp += ens["total_periodes"]
            nb_enseignants_tp_global += 1

    for data_champ in moyennes_par_champ_calculees.values():
        if data_champ["nb_enseignants"] > 0:
            data_champ["moyenne"] = data_champ["total_periodes"] / data_champ["nb_enseignants"]

    moyenne_generale_calculee = (
        (total_periodes_global_tp / nb_enseignants_tp_global) if nb_enseignants_tp_global > 0 else 0
    )
    return tous_enseignants_details, moyennes_par_champ_calculees, moyenne_generale_calculee


# --- API ENDPOINTS ---
@app.route("/api/sommaire/donnees", methods=["GET"])
def api_get_donnees_sommaire():
    """API pour récupérer les données actualisées du sommaire global."""
    enseignants, moyennes_champs, moyenne_gen = calculer_donnees_sommaire()
    return jsonify({"enseignants": enseignants, "moyennes_par_champ": moyennes_champs, "moyenne_generale": moyenne_gen})


@app.route("/api/attributions/ajouter", methods=["POST"])
def api_ajouter_attribution():
    """API pour ajouter une attribution de cours."""
    db = get_db()
    if not db:
        return jsonify({"success": False, "message": "Erreur de connexion à la base de données."}), 500

    data = request.get_json()
    if not data:
        return jsonify({"success": False, "message": "Aucune donnée JSON reçue."}), 400

    enseignant_id = data.get("enseignant_id")
    code_cours = data.get("code_cours")
    if not enseignant_id or not code_cours:
        return jsonify({"success": False, "message": "Données manquantes (ID enseignant ou code cours)."}), 400

    nouvelle_attribution_id = None
    periodes_enseignant_maj = {}
    groupes_restants_cours_maj = 0
    attributions_enseignant_maj = []
    infos_enseignant_pour_reponse = {}

    try:
        with db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            query_grp_dispo = """
                SELECT (NbGroupeInitial - COALESCE((SELECT SUM(NbGroupesPris)
                                                    FROM AttributionsCours
                                                    WHERE CodeCours = %s), 0)) as grp_dispo
                FROM Cours WHERE CodeCours = %s;
            """
            cur.execute(query_grp_dispo, (code_cours, code_cours))
            cours_info = cur.fetchone()
            if not cours_info or cours_info["grp_dispo"] < 1:
                return jsonify({"success": False, "message": "Plus de groupes disponibles pour ce cours."}), 409

            cur.execute(
                "INSERT INTO AttributionsCours (EnseignantID, CodeCours, NbGroupesPris) VALUES (%s, %s, %s) RETURNING AttributionID;",
                (enseignant_id, code_cours, 1),
            )
            resultat_insertion = cur.fetchone()
            if resultat_insertion is None:
                db.rollback()
                msg = f"Échec de l'insertion d'attribution pour ens {enseignant_id}, cours {code_cours}."
                app.logger.error(msg)
                return jsonify({"success": False, "message": "Erreur interne lors de la création de l'attribution."}), 500
            nouvelle_attribution_id = resultat_insertion["attributionid"]

            cur.execute("SELECT ChampNo, EstTempsPlein, EstFictif FROM Enseignants WHERE EnseignantID = %s", (enseignant_id,))
            resultat_enseignant = cur.fetchone()
            if resultat_enseignant:
                infos_enseignant_pour_reponse = dict(resultat_enseignant)
            db.commit()

        try:
            periodes_enseignant_maj = calculer_periodes_enseignant(enseignant_id)
            groupes_restants_cours_maj = get_groupes_restants_pour_cours(code_cours)
            attributions_enseignant_maj = get_attributions_enseignant(enseignant_id)
        except Exception as e_calcul:  # pylint: disable=broad-except
            msg = f"Erreur post-attribution (calculs) pour ens {enseignant_id}, cours {code_cours}: {e_calcul}"
            app.logger.error(msg)
            message_succes_partiel = "Cours attribué, mais erreur lors de la mise à jour des totaux."
            return jsonify({
                "success": True,
                "message": message_succes_partiel,
                "attribution_id": nouvelle_attribution_id,
                "enseignant_id": enseignant_id,
                "code_cours": code_cours,
                "periodes_enseignant": {},
                "groupes_restants_cours": -1,
                "attributions_enseignant": [],
                **infos_enseignant_pour_reponse,
            }), 201

        return jsonify({
            "success": True,
            "message": "Cours attribué avec succès!",
            "attribution_id": nouvelle_attribution_id,
            "enseignant_id": enseignant_id,
            "code_cours": code_cours,
            "periodes_enseignant": periodes_enseignant_maj,
            "groupes_restants_cours": groupes_restants_cours_maj,
            "attributions_enseignant": attributions_enseignant_maj,  # Ajouté ici
            **infos_enseignant_pour_reponse,
        }), 201

    except psycopg2.Error as e_psy:
        if db and not db.closed:
            db.rollback()
        app.logger.error(f"Erreur psycopg2 API ajouter attribution: {e_psy}")
        return jsonify({"success": False, "message": "Erreur de base de données lors de l'ajout de l'attribution."}), 500
    except Exception as e_gen:  # pylint: disable=broad-except
        if db and not db.closed:
            db.rollback()
        app.logger.error(f"Erreur générale Exception API ajouter attribution: {e_gen}")
        return jsonify({"success": False, "message": "Erreur serveur inattendue lors de l'ajout de l'attribution."}), 500


@app.route("/api/attributions/supprimer", methods=["POST"])
def api_supprimer_attribution():
    """API pour supprimer une attribution de cours."""
    db = get_db()
    if not db:
        return jsonify({"success": False, "message": "Erreur de connexion à la base de données."}), 500

    data = request.get_json()
    if not data:
        return jsonify({"success": False, "message": "Aucune donnée JSON reçue."}), 400
    attribution_id_a_supprimer = data.get("attribution_id")
    if not attribution_id_a_supprimer:
        return jsonify({"success": False, "message": "ID d'attribution manquant."}), 400

    enseignant_id_concerne, code_cours_concerne = None, None
    periodes_enseignant_maj, groupes_restants_cours_maj = {}, 0
    attributions_enseignant_maj = []  # Pour renvoyer la liste complète
    periodes_liberees_par_suppression = 0
    infos_enseignant_pour_reponse = {}

    try:
        with db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            query_select_attribution = """
                SELECT ac.EnseignantID, ac.CodeCours, c.NbPeriodes AS PeriodesDuCours
                FROM AttributionsCours ac JOIN Cours c ON ac.CodeCours = c.CodeCours
                WHERE ac.AttributionID = %s;
            """
            cur.execute(query_select_attribution, (attribution_id_a_supprimer,))
            attribution_info = cur.fetchone()
            if not attribution_info:
                return jsonify({"success": False, "message": "Attribution non trouvée."}), 404

            enseignant_id_concerne = attribution_info["enseignantid"]
            code_cours_concerne = attribution_info["codecours"]
            periodes_liberees_par_suppression = attribution_info.get("periodesducours", 0)

            cur.execute("DELETE FROM AttributionsCours WHERE AttributionID = %s;", (attribution_id_a_supprimer,))
            if cur.rowcount == 0:
                db.rollback()
                return jsonify({"success": False, "message": "Attribution non trouvée ou déjà supprimée."}), 404

            cur.execute("SELECT ChampNo, EstTempsPlein, EstFictif FROM Enseignants WHERE EnseignantID = %s", (enseignant_id_concerne,))
            resultat_enseignant = cur.fetchone()
            if resultat_enseignant:
                infos_enseignant_pour_reponse = dict(resultat_enseignant)
            db.commit()

        try:
            periodes_enseignant_maj = calculer_periodes_enseignant(enseignant_id_concerne)
            groupes_restants_cours_maj = get_groupes_restants_pour_cours(code_cours_concerne)
            attributions_enseignant_maj = get_attributions_enseignant(enseignant_id_concerne)
        except Exception as e_calcul:  # pylint: disable=broad-except
            msg = f"Erreur post-suppression (calculs) pour ens {enseignant_id_concerne}, cours {code_cours_concerne}: {e_calcul}"
            app.logger.error(msg)
            message_succes_partiel = "Attribution supprimée, mais erreur lors de la mise à jour des totaux."
            return jsonify({
                "success": True,
                "message": message_succes_partiel,
                "enseignant_id": enseignant_id_concerne,
                "code_cours": code_cours_concerne,
                "nb_periodes_cours_libere": periodes_liberees_par_suppression,
                "periodes_enseignant": {},
                "groupes_restants_cours": -1,
                "attributions_enseignant": [],
                **infos_enseignant_pour_reponse,
            }), 200

        return jsonify({
            "success": True,
            "message": "Attribution supprimée avec succès!",
            "enseignant_id": enseignant_id_concerne,
            "code_cours": code_cours_concerne,
            "periodes_enseignant": periodes_enseignant_maj,
            "groupes_restants_cours": groupes_restants_cours_maj,
            "attributions_enseignant": attributions_enseignant_maj,  # Ajouté ici
            "nb_periodes_cours_libere": periodes_liberees_par_suppression,
            **infos_enseignant_pour_reponse,
        }), 200

    except psycopg2.Error as e_psy:
        if db and not db.closed:
            db.rollback()
        app.logger.error(f"Erreur psycopg2 API supprimer attribution: {e_psy}")
        if hasattr(e_psy, "pgcode") and e_psy.pgcode == "23503":
            return jsonify({"success": False, "message": "Suppression impossible car référencée ailleurs."}), 409
        return jsonify({"success": False, "message": "Erreur de base de données lors de la suppression."}), 500
    except Exception as e_gen:  # pylint: disable=broad-except
        if db and not db.closed:
            db.rollback()
        app.logger.error(f"Erreur générale Exception API supprimer attribution: {e_gen}")
        return jsonify({"success": False, "message": f"Erreur serveur inattendue: {str(e_gen)}"}), 500


@app.route("/api/champs/<string:champ_no>/taches_restantes/creer", methods=["POST"])
def api_creer_tache_restante(champ_no):
    """API pour créer une nouvelle tâche restante (enseignant fictif)."""
    db = get_db()
    if not db:
        return jsonify({"success": False, "message": "Erreur de connexion à la base de données."}), 500

    nouvel_enseignant_fictif_cree = {}
    periodes_initiales_tache = {"periodes_cours": 0, "periodes_autres": 0, "total_periodes": 0}

    try:
        with db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            query_select_taches_existantes = """
                SELECT NomComplet FROM Enseignants
                WHERE ChampNo = %s AND EstFictif = TRUE AND NomComplet LIKE %s;
            """
            pattern_nom_tache = f"{champ_no}-Tâche restante-%"
            cur.execute(query_select_taches_existantes, (champ_no, pattern_nom_tache))
            taches_existantes = cur.fetchall()

            max_numero_tache = 0
            for tache in taches_existantes:
                try:
                    numero = int(tache["nomcomplet"].split("-")[-1].strip())
                    max_numero_tache = max(max_numero_tache, numero)
                except (ValueError, IndexError):
                    continue
            nom_nouvelle_tache = f"{champ_no}-Tâche restante-{max_numero_tache + 1}"

            query_insert_tache = """
                INSERT INTO Enseignants (NomComplet, ChampNo, EstTempsPlein, EstFictif, PeutChoisirHorsChampPrincipal)
                VALUES (%s, %s, FALSE, TRUE, FALSE)
                RETURNING EnseignantID, NomComplet, EstTempsPlein, EstFictif, PeutChoisirHorsChampPrincipal, ChampNo;
            """
            cur.execute(query_insert_tache, (nom_nouvelle_tache, champ_no))
            resultat_insertion = cur.fetchone()
            if resultat_insertion is None:
                db.rollback()
                msg = f"Échec de l'insertion de la tâche restante '{nom_nouvelle_tache}'."
                app.logger.error(msg)
                return jsonify({"success": False, "message": "Erreur interne lors de la création de la tâche."}), 500
            nouvel_enseignant_fictif_cree = dict(resultat_insertion)
            db.commit()

        return jsonify({
            "success": True,
            "message": "Tâche restante créée avec succès!",
            "enseignant": nouvel_enseignant_fictif_cree,
            "periodes_actuelles": periodes_initiales_tache,
            "attributions": [],  # Une nouvelle tâche n'a pas d'attributions
        }), 201

    except psycopg2.Error as e_psy:
        if db and not db.closed:
            db.rollback()
        app.logger.error(f"Erreur psycopg2 API créer tâche restante: {e_psy}")
        return jsonify({"success": False, "message": "Erreur de base de données lors de la création de la tâche."}), 500
    except Exception as e_gen:  # pylint: disable=broad-except
        if db and not db.closed:
            db.rollback()
        app.logger.error(f"Erreur générale Exception API créer tâche restante: {e_gen}")
        return jsonify({"success": False, "message": "Erreur serveur inattendue lors de la création."}), 500


@app.route("/api/enseignants/<int:enseignant_id>/supprimer", methods=["POST"])
def api_supprimer_enseignant(enseignant_id):
    """API pour supprimer un enseignant (principalement tâches fictives)."""
    db = get_db()
    if not db:
        return jsonify({"success": False, "message": "Erreur de connexion à la base de données."}), 500

    cours_liberes_apres_suppression = []
    try:
        with db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT EstFictif FROM Enseignants WHERE EnseignantID = %s;", (enseignant_id,))
            enseignant_existe = cur.fetchone()
            if not enseignant_existe:
                return jsonify({"success": False, "message": "Enseignant non trouvé."}), 404

            query_cours_affectes_enseignant = """
                SELECT DISTINCT ac.CodeCours, c.NbPeriodes
                FROM AttributionsCours ac JOIN Cours c ON ac.CodeCours = c.CodeCours
                WHERE ac.EnseignantID = %s;
            """
            cur.execute(query_cours_affectes_enseignant, (enseignant_id,))
            cours_affectes_avant_suppression = cur.fetchall()

            cur.execute("DELETE FROM Enseignants WHERE EnseignantID = %s;", (enseignant_id,))
            if cur.rowcount == 0:
                db.rollback()
                return jsonify({"success": False, "message": "L'enseignant n'a pas pu être supprimé."}), 404
            db.commit()

            if cours_affectes_avant_suppression:
                codes_cours_uniques = list(set(c["codecours"] for c in cours_affectes_avant_suppression))
                for code_cours_unique in codes_cours_uniques:
                    groupes_restants_maj = get_groupes_restants_pour_cours(code_cours_unique)
                    nb_periodes = next(
                        (c["nbperiodes"] for c in cours_affectes_avant_suppression if c["codecours"] == code_cours_unique), 0
                    )
                    cours_liberes_apres_suppression.append({
                        "code_cours": code_cours_unique,
                        "nouveaux_groupes_restants": groupes_restants_maj,
                        "nb_periodes": nb_periodes,
                    })
        return jsonify({
            "success": True,
            "message": "Enseignant supprimé avec succès. Cours affectés mis à jour.",
            "enseignant_id": enseignant_id,
            "cours_liberes_details": cours_liberes_apres_suppression,
        }), 200

    except psycopg2.Error as e_psy:
        if db and not db.closed:
            db.rollback()
        if hasattr(e_psy, "pgcode") and e_psy.pgcode == "23503":
            msg_err_fk = f"Erreur FK non attendue pour enseignant {enseignant_id}: {e_psy}"
            app.logger.error(msg_err_fk)
            message_erreur_fk = "Suppression impossible due à des références existantes."
            return jsonify({"success": False, "message": message_erreur_fk}), 409
        app.logger.error(f"Erreur psycopg2 API supprimer enseignant: {e_psy}")
        return jsonify({"success": False, "message": "Erreur de base de données lors de la suppression."}), 500
    except Exception as e_gen:  # pylint: disable=broad-except
        if db and not db.closed:
            db.rollback()
        app.logger.error(f"Erreur générale Exception API supprimer enseignant: {e_gen}")
        msg = f"Erreur serveur inattendue lors de la suppression: {str(e_gen)}"
        return jsonify({"success": False, "message": msg}), 500


@app.route("/api/cours/reassigner_champ", methods=["POST"])
def api_reassigner_champ_cours():
    """API pour réassigner un cours à un nouveau champ."""
    db = get_db()
    if not db:
        return jsonify({"success": False, "message": "Erreur de connexion à la base de données."}), 500

    data = request.get_json()
    if not data:
        return jsonify({"success": False, "message": "Aucune donnée JSON reçue."}), 400
    code_cours_a_reassigner = data.get("code_cours")
    nouveau_champ_no_destination = data.get("nouveau_champ_no")
    if not code_cours_a_reassigner or not nouveau_champ_no_destination:
        return jsonify({"success": False, "message": "Données manquantes (code cours ou nouveau champ)."}), 400

    nom_nouveau_champ = ""
    try:
        with db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT ChampNo FROM Cours WHERE CodeCours = %s;", (code_cours_a_reassigner,))
            cours_actuel_info = cur.fetchone()
            if not cours_actuel_info:
                msg = f"Le cours {code_cours_a_reassigner} n'a pas été trouvé."
                return jsonify({"success": False, "message": msg}), 404

            cur.execute("SELECT ChampNom FROM Champs WHERE ChampNo = %s;", (nouveau_champ_no_destination,))
            champ_destination_info = cur.fetchone()
            if not champ_destination_info:
                msg = f"Le champ de destination {nouveau_champ_no_destination} n'a pas été trouvé."
                return jsonify({"success": False, "message": msg}), 404
            nom_nouveau_champ = champ_destination_info["champnom"]

            if cours_actuel_info["champno"] == nouveau_champ_no_destination:
                message_deja_assigne = (
                    f"Le cours {code_cours_a_reassigner} est déjà assigné au champ "
                    f"{nouveau_champ_no_destination} ({nom_nouveau_champ})."
                )
                return jsonify({
                    "success": False,  # Note: techniquement pas une erreur, mais une non-action
                    "message": message_deja_assigne,
                    "nouveau_champ_no": nouveau_champ_no_destination,
                    "nouveau_champ_nom": nom_nouveau_champ,
                }), 409

            cur.execute("UPDATE Cours SET ChampNo = %s WHERE CodeCours = %s;", (nouveau_champ_no_destination, code_cours_a_reassigner))
            if cur.rowcount == 0:
                db.rollback()
                msg = f"La mise à jour du ChampNo pour {code_cours_a_reassigner} n'a affecté aucune ligne."
                app.logger.error(msg)
                return jsonify({"success": False, "message": "La mise à jour du champ n'a pas eu d'effet."}), 500
            db.commit()

        return jsonify({
            "success": True,
            "message": f"Le cours {code_cours_a_reassigner} a été réassigné à {nouveau_champ_no_destination} ({nom_nouveau_champ}).",
            "code_cours": code_cours_a_reassigner,
            "nouveau_champ_no": nouveau_champ_no_destination,
            "nouveau_champ_nom": nom_nouveau_champ,
        }), 200

    except psycopg2.Error as e_psy:
        if db and not db.closed:
            db.rollback()
        app.logger.error(f"Erreur psycopg2 API réassigner champ cours: {e_psy}")
        return jsonify({"success": False, "message": "Erreur de base de données lors de la réassignation."}), 500
    except Exception as e_gen:  # pylint: disable=broad-except
        if db and not db.closed:
            db.rollback()
        app.logger.error(f"Erreur générale Exception API réassigner champ cours: {e_gen}")
        msg = f"Erreur serveur inattendue lors de la réassignation: {str(e_gen)}"
        return jsonify({"success": False, "message": msg}), 500


# --- Fonctions utilitaires et routes pour l'importation de données Excel ---
def allowed_file(filename):
    """Vérifie si l'extension du fichier est autorisée."""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route("/administration/importer_cours_excel", methods=["POST"])
def api_importer_cours_excel():
    """Importe les cours depuis un fichier Excel."""
    db = get_db()
    if not db:
        flash("Erreur de connexion BDD. Importation annulée.", "error")
        return redirect(url_for("page_administration_donnees"))

    if "fichier_cours" not in request.files:
        flash("Aucun fichier sélectionné pour l'importation des cours.", "warning")
        return redirect(url_for("page_administration_donnees"))

    file = request.files["fichier_cours"]
    if not file or not file.filename:
        flash("Nom de fichier vide pour l'importation des cours.", "warning")
        return redirect(url_for("page_administration_donnees"))

    if not allowed_file(file.filename):
        flash("Type de fichier non autorisé pour les cours (.xlsx seulement).", "error")
        return redirect(url_for("page_administration_donnees"))

    nouveaux_cours_a_importer = []
    try:
        workbook = openpyxl.load_workbook(file.stream)
        sheet = workbook.active
        assert isinstance(sheet, Worksheet), "Feuille active Excel invalide."

        iter_rows = iter(sheet.rows)
        try:
            next(iter_rows)  # Ignorer en-tête
        except StopIteration:
            flash("Fichier Excel des cours vide ou que en-tête.", "warning")
            return redirect(url_for("page_administration_donnees"))

        for row_idx, row in enumerate(iter_rows, start=2):
            try:
                champ_no_raw = row[0].value
                code_cours_raw = row[1].value
                cours_descriptif_raw = row[3].value

                champ_no = str(champ_no_raw).strip() if champ_no_raw is not None else None
                code_cours = str(code_cours_raw).strip() if code_cours_raw is not None else None
                cours_descriptif = str(cours_descriptif_raw).strip() if cours_descriptif_raw is not None else None

                if not all([champ_no, code_cours, cours_descriptif]):
                    flash(f"Ligne {row_idx} (Cours): Données essentielles manquantes. Ligne ignorée.", "warning")
                    continue

                nb_groupe_initial, nb_periodes = 0, 0
                cell_val_nb_groupe = row[4].value
                cell_val_nb_periodes = row[5].value

                if isinstance(cell_val_nb_groupe, int | float):
                    nb_groupe_initial = int(cell_val_nb_groupe)
                elif isinstance(cell_val_nb_groupe, str) and cell_val_nb_groupe.strip().isdigit():
                    nb_groupe_initial = int(cell_val_nb_groupe.strip())
                elif cell_val_nb_groupe is not None:
                    flash(f"Ligne {row_idx} (Cours): Val non num pour 'Groupes prévus'. Ignorée.", "warning")
                    continue

                if isinstance(cell_val_nb_periodes, int | float):
                    nb_periodes = int(cell_val_nb_periodes)
                elif isinstance(cell_val_nb_periodes, str) and cell_val_nb_periodes.strip().isdigit():
                    nb_periodes = int(cell_val_nb_periodes.strip())
                elif cell_val_nb_periodes is not None:
                    flash(f"Ligne {row_idx} (Cours): Val non num pour 'Périodes'. Ignorée.", "warning")
                    continue

                est_cours_autre_raw = row[7].value
                est_cours_autre = False
                if isinstance(est_cours_autre_raw, bool):
                    est_cours_autre = est_cours_autre_raw
                elif isinstance(est_cours_autre_raw, str):
                    est_cours_autre = est_cours_autre_raw.strip().upper() == "VRAI"
                elif est_cours_autre_raw is not None:
                    flash(f"Ligne {row_idx} (Cours): Val inattendue pour 'Cours Autre'. Assumée FAUX.", "warning")

                nouveaux_cours_a_importer.append({
                    "codecours": code_cours,
                    "champno": champ_no,
                    "coursdescriptif": cours_descriptif,
                    "nbperiodes": nb_periodes,
                    "nbgroupeinitial": nb_groupe_initial,
                    "estcoursautre": est_cours_autre,
                })
            except IndexError:
                flash(f"Ligne {row_idx} (Cours): Nb colonnes insuffisant. Ignorée.", "warning")
                continue
            except TypeError as te:
                flash(f"Ligne {row_idx} (Cours): Erreur type donnée. Ignorée. Détails: {te}", "warning")
                continue

        if not nouveaux_cours_a_importer:
            flash("Aucun cours valide lu. Aucune modification.", "warning")
            return redirect(url_for("page_administration_donnees"))

        with db.cursor() as cur:
            cur.execute("DELETE FROM AttributionsCours;")
            cur.execute("DELETE FROM Cours;")
            for cours_data in nouveaux_cours_a_importer:
                try:
                    cur.execute(
                        """INSERT INTO Cours (CodeCours, ChampNo, CoursDescriptif, NbPeriodes, NbGroupeInitial, EstCoursAutre)
                           VALUES (%(codecours)s, %(champno)s, %(coursdescriptif)s, %(nbperiodes)s, %(nbgroupeinitial)s, %(estcoursautre)s);""",
                        cours_data,
                    )
                except psycopg2.Error as e_insert:
                    db.rollback()
                    err_details = e_insert.pgerror if hasattr(e_insert, "pgerror") else str(e_insert)
                    code_prob = cours_data.get("codecours", "INCONNU")
                    err_msg = f"Erreur insertion cours '{code_prob}': {err_details}. Importation annulée."
                    flash(err_msg, "error")
                    app.logger.error(err_msg)
                    return redirect(url_for("page_administration_donnees"))
            db.commit()
            msg_succes = f"{len(nouveaux_cours_a_importer)} cours importés. Anciens cours et attributions écrasés."
            flash(msg_succes, "success")

    except InvalidFileException:
        flash("Fichier Excel des cours invalide ou corrompu.", "error")
    except AssertionError as ae:
        flash(f"Erreur format fichier Excel (cours): {ae}", "error")
        app.logger.error(f"Erreur assertion import cours: {ae}")
    except Exception as e:  # pylint: disable=broad-except
        if db and not db.closed and not db.autocommit:
            db.rollback()
        app.logger.error(f"Erreur inattendue import cours: {type(e).__name__} - {e}")
        msg_err_inatt = f"Erreur inattendue import cours: {type(e).__name__}. Opération annulée."
        flash(msg_err_inatt, "error")
    return redirect(url_for("page_administration_donnees"))


@app.route("/administration/importer_enseignants_excel", methods=["POST"])
def api_importer_enseignants_excel():
    """Importe les enseignants depuis un fichier Excel."""
    db = get_db()
    if not db:
        flash("Erreur de connexion BDD. Importation annulée.", "error")
        return redirect(url_for("page_administration_donnees"))

    if "fichier_enseignants" not in request.files:
        flash("Aucun fichier sélectionné pour l'importation des enseignants.", "warning")
        return redirect(url_for("page_administration_donnees"))

    file = request.files["fichier_enseignants"]
    if not file or not file.filename:
        flash("Nom de fichier vide pour l'importation des enseignants.", "warning")
        return redirect(url_for("page_administration_donnees"))

    if not allowed_file(file.filename):
        flash("Type de fichier non autorisé pour enseignants (.xlsx seulement).", "error")
        return redirect(url_for("page_administration_donnees"))

    nouveaux_enseignants_a_importer = []
    try:
        workbook = openpyxl.load_workbook(file.stream)
        sheet = workbook.active
        assert isinstance(sheet, Worksheet), "Feuille active Excel invalide."

        iter_rows = iter(sheet.rows)
        try:
            next(iter_rows)  # Ignorer en-tête
        except StopIteration:
            flash("Fichier Excel enseignants vide ou que en-tête.", "warning")
            return redirect(url_for("page_administration_donnees"))

        for row_idx, row in enumerate(iter_rows, start=2):
            try:
                champ_no_raw = row[0].value
                nom_raw = row[1].value
                prenom_raw = row[2].value

                champ_no = str(champ_no_raw).strip() if champ_no_raw is not None else None
                nom = str(nom_raw).strip() if nom_raw is not None else None
                prenom = str(prenom_raw).strip() if prenom_raw is not None else None

                if not all([champ_no, nom, prenom]):
                    flash(f"Ligne {row_idx} (Enseignants): Données essentielles manquantes. Ignorée.", "warning")
                    continue

                nom_complet = f"{prenom} {nom}"
                temps_plein_raw = row[3].value
                est_temps_plein = True
                if isinstance(temps_plein_raw, bool):
                    est_temps_plein = temps_plein_raw
                elif isinstance(temps_plein_raw, str):
                    est_temps_plein = temps_plein_raw.strip().upper() == "VRAI"
                elif temps_plein_raw is None:
                    est_temps_plein = True
                else:
                    est_temps_plein = False
                    flash(f"Ligne {row_idx} (Ens): Val inattendue 'Temps plein'. Assumée FAUX.", "warning")

                nouveaux_enseignants_a_importer.append({
                    "nomcomplet": nom_complet,
                    "champno": champ_no,
                    "esttempsplein": est_temps_plein,
                    "estfictif": False,
                    "peutchoisirhorschampprincipal": False,
                })
            except IndexError:
                flash(f"Ligne {row_idx} (Enseignants): Nb colonnes insuffisant. Ignorée.", "warning")
                continue
            except TypeError as te:
                flash(f"Ligne {row_idx} (Enseignants): Erreur type donnée. Ignorée. Détails: {te}", "warning")
                continue

        if not nouveaux_enseignants_a_importer:
            flash("Aucun enseignant valide lu. Aucune modification.", "warning")
            return redirect(url_for("page_administration_donnees"))

        with db.cursor() as cur:
            cur.execute("DELETE FROM AttributionsCours;")
            cur.execute("DELETE FROM Enseignants;")
            for ens_data in nouveaux_enseignants_a_importer:
                try:
                    cur.execute(
                        """INSERT INTO Enseignants (NomComplet, ChampNo, EstTempsPlein, EstFictif, PeutChoisirHorsChampPrincipal)
                           VALUES (%(nomcomplet)s, %(champno)s, %(esttempsplein)s, %(estfictif)s, %(peutchoisirhorschampprincipal)s);""",
                        ens_data,
                    )
                except psycopg2.Error as e_insert:
                    db.rollback()
                    err_details = e_insert.pgerror if hasattr(e_insert, "pgerror") else str(e_insert)
                    nom_prob = ens_data.get("nomcomplet", "INCONNU")
                    err_msg = f"Erreur insertion ens '{nom_prob}': {err_details}. Importation annulée."
                    flash(err_msg, "error")
                    app.logger.error(err_msg)
                    return redirect(url_for("page_administration_donnees"))
            db.commit()
            msg_succes = f"{len(nouveaux_enseignants_a_importer)} enseignants importés. Anciens ens et attributions écrasés."
            flash(msg_succes, "success")

    except InvalidFileException:
        flash("Fichier Excel enseignants invalide ou corrompu.", "error")
    except AssertionError as ae:
        flash(f"Erreur format fichier Excel (enseignants): {ae}", "error")
        app.logger.error(f"Erreur assertion import enseignants: {ae}")
    except Exception as e:  # pylint: disable=broad-except
        if db and not db.closed and not db.autocommit:
            db.rollback()
        app.logger.error(f"Erreur inattendue import enseignants: {type(e).__name__} - {e}")
        msg_err_inatt = f"Erreur inattendue import enseignants: {type(e).__name__}. Opération annulée."
        flash(msg_err_inatt, "error")
    return redirect(url_for("page_administration_donnees"))


# --- Démarrage de l'application ---
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)
