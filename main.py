import datetime
import os

import openpyxl  # Pour la manipulation des fichiers Excel
import psycopg2
import psycopg2.extras  # Nécessaire pour DictCursor
from flask import Flask, flash, g, jsonify, redirect, render_template, request, url_for

# Import direct de l'exception, essayez l'autre si Pyright se plaint toujours
from openpyxl.utils.exceptions import InvalidFileException

# from openpyxl.exceptions import InvalidFileException
from openpyxl.worksheet.worksheet import Worksheet  # Import pour l'assertion de type

# secure_filename n'est pas utilisé actuellement, mais gardé pour info
# from werkzeug.utils import secure_filename

# --- Configuration de l'application Flask ---
app = Flask(__name__)
app.secret_key = os.urandom(24)
UPLOAD_FOLDER = "uploads"  # Défini mais non utilisé si lecture directe du flux
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
def close_db(_exception=None):  # Paramètre _exception intentionnellement non utilisé
    """Ferme la connexion à la base de données à la fin de la requête."""
    db = g.pop("db", None)
    if db is not None and not db.closed:
        try:
            db.close()
        except psycopg2.Error as e:
            app.logger.error(f"Erreur lors de la fermeture de la connexion DB: {e}")


# --- Fonctions d'accès aux données (DAO) ---


def get_all_champs():
    """Récupère tous les champs."""
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
    """Récupère les détails d'un champ."""
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
    """Récupère les enseignants d'un champ."""
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
    """Récupère tous les enseignants avec détails et périodes calculées."""
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
    """Récupère les cours disponibles pour un champ avec groupes restants."""
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
    """Récupère les attributions d'un enseignant."""
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
                WHERE ac.EnseignantID = %s;
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
    """Calcule les périodes (cours/autres) pour un enseignant."""
    attributions = get_attributions_enseignant(enseignant_id)
    periodes_enseignement = sum(a["nbperiodes"] * a["nbgroupespris"] for a in attributions if not a["estcoursautre"])
    periodes_autres = sum(a["nbperiodes"] * a["nbgroupespris"] for a in attributions if a["estcoursautre"])
    return {
        "periodes_cours": periodes_enseignement,
        "periodes_autres": periodes_autres,
        "total_periodes": periodes_enseignement + periodes_autres,
    }


def get_groupes_restants_pour_cours(code_cours):
    """Calcule les groupes restants pour un cours."""
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
    """Récupère tous les cours avec détails du champ."""
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
    """Affiche la page d'accueil avec la liste des champs."""
    champs = get_all_champs()
    current_year = datetime.datetime.now().year
    return render_template("index.html", champs=champs, SCRIPT_YEAR=current_year)


@app.route("/champ/<string:champ_no>")
def page_champ(champ_no):
    """Affiche la page détaillée d'un champ."""
    champ_details = get_champ_details(champ_no)
    if not champ_details:
        return "Champ non trouvé", 404

    enseignants_bruts = get_enseignants_par_champ(champ_no)
    cours_disponibles = get_cours_disponibles_par_champ(champ_no)
    cours_ens = [c for c in cours_disponibles if not c["estcoursautre"]]
    cours_autres = [c for c in cours_disponibles if c["estcoursautre"]]

    enseignants_complets, sommaire_champ_data = [], []
    total_periodes_tp, nb_ens_tp = 0, 0

    for ens_brut in enseignants_bruts:
        periodes = calculer_periodes_enseignant(ens_brut["enseignantid"])
        attributions = get_attributions_enseignant(ens_brut["enseignantid"])
        enseignants_complets.append({**ens_brut, "attributions": attributions, "periodes_actuelles": periodes})
        sommaire_champ_data.append(
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
            total_periodes_tp += periodes["total_periodes"]
            nb_ens_tp += 1

    moyenne = (total_periodes_tp / nb_ens_tp) if nb_ens_tp > 0 else 0
    current_year = datetime.datetime.now().year
    return render_template(
        "page_champ.html",
        champ=champ_details,
        enseignants=enseignants_complets,
        cours_enseignement_champ=cours_ens,
        cours_autres_taches_champ=cours_autres,
        cours_disponibles_pour_tableau_restant=cours_disponibles,
        taches_sommaire_champ=sommaire_champ_data,
        moyenne_champ_initiale=moyenne,
        SCRIPT_YEAR=current_year,
    )


@app.route("/sommaire")
def page_sommaire():
    """Affiche la page du sommaire global des tâches."""
    enseignants, moyennes_champs, moyenne_gen = calculer_donnees_sommaire()
    current_year = datetime.datetime.now().year
    return render_template(
        "page_sommaire.html", enseignants=enseignants, moyennes_par_champ=moyennes_champs, moyenne_generale=moyenne_gen, SCRIPT_YEAR=current_year
    )


@app.route("/administration")
def page_administration_donnees():
    """Affiche la page d'administration pour la gestion des données."""
    cours = get_all_cours_avec_details_champ()
    champs = get_all_champs()
    current_year = datetime.datetime.now().year
    return render_template("administration_donnees.html", cours_a_reassigner=cours or [], champs_destination=champs or [], SCRIPT_YEAR=current_year)


# --- Fonctions utilitaires pour le sommaire ---
def calculer_donnees_sommaire():
    """Calcule les données nécessaires pour la page sommaire et l'API sommaire."""
    tous_enseignants = get_all_enseignants_avec_details()
    moyennes_par_champ, total_periodes_glob, nb_ens_tp_glob = {}, 0, 0

    for ens in tous_enseignants:
        if ens["compte_pour_moyenne_champ"]:
            champ_no = ens["champno"]
            if champ_no not in moyennes_par_champ:
                moyennes_par_champ[champ_no] = {
                    "champ_nom": ens["champnom"],
                    "total_periodes": 0,
                    "nb_enseignants": 0,
                    "moyenne": 0.0,
                }
            moyennes_par_champ[champ_no]["total_periodes"] += ens["total_periodes"]
            moyennes_par_champ[champ_no]["nb_enseignants"] += 1
            total_periodes_glob += ens["total_periodes"]
            nb_ens_tp_glob += 1

    for data_ch in moyennes_par_champ.values():
        if data_ch["nb_enseignants"] > 0:
            data_ch["moyenne"] = data_ch["total_periodes"] / data_ch["nb_enseignants"]

    moyenne_generale = (total_periodes_glob / nb_ens_tp_glob) if nb_ens_tp_glob > 0 else 0
    return tous_enseignants, moyennes_par_champ, moyenne_generale


# --- API ENDPOINTS ---
@app.route("/api/sommaire/donnees", methods=["GET"])
def api_get_donnees_sommaire():
    """API pour récupérer les données actualisées du sommaire global."""
    ens, moy_ch, moy_gen = calculer_donnees_sommaire()
    return jsonify({"enseignants": ens, "moyennes_par_champ": moy_ch, "moyenne_generale": moy_gen})


@app.route("/api/attributions/ajouter", methods=["POST"])
def api_ajouter_attribution():
    """API pour ajouter une attribution de cours à un enseignant."""
    db = get_db()
    if not db:
        return jsonify({"success": False, "message": "Erreur BDD"}), 500
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "message": "Pas de données JSON"}), 400

    ens_id = data.get("enseignant_id")
    code_cr = data.get("code_cours")
    if not ens_id or not code_cr:
        return jsonify({"success": False, "message": "Données manquantes"}), 400

    attr_id, periodes_maj, grp_rest_maj, ens_info = None, {}, 0, {}
    try:
        with db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                "SELECT (NbGroupeInitial - COALESCE((SELECT SUM(NbGroupesPris)\
                FROM AttributionsCours WHERE CodeCours = %s), 0)) as grp_dispo FROM Cours WHERE CodeCours = %s;",
                (code_cr, code_cr),
            )
            cours_info = cur.fetchone()
            if not cours_info or cours_info["grp_dispo"] < 1:
                return jsonify({"success": False, "message": "Plus de groupes disponibles."}), 409

            cur.execute(
                "INSERT INTO AttributionsCours (EnseignantID, CodeCours, NbGroupesPris) VALUES (%s, %s, %s) RETURNING AttributionID;",
                (ens_id, code_cr, 1),
            )
            res_insert = cur.fetchone()
            if res_insert is None:
                db.rollback()
                app.logger.error("INSERT attribution sans retour ID.")
                return jsonify({"success": False, "message": "Erreur interne (ID attribution)."}), 500
            attr_id = res_insert["attributionid"]

            cur.execute("SELECT ChampNo, EstTempsPlein, EstFictif FROM Enseignants WHERE EnseignantID = %s", (ens_id,))
            res_ens = cur.fetchone()
            if res_ens:
                ens_info = dict(res_ens)
            db.commit()

        try:
            periodes_maj = calculer_periodes_enseignant(ens_id)
            grp_rest_maj = get_groupes_restants_pour_cours(code_cr)
        except Exception as e_calc:
            app.logger.error(f"Erreur post-attribution (calculs): {e_calc}")
            # Message plus concis
            msg = "Attribué, mais erreur MàJ totaux."
            return jsonify(
                {
                    "success": True,
                    "message": msg,
                    "attribution_id": attr_id,
                    "enseignant_id": ens_id,
                    "code_cours": code_cr,
                    "periodes_enseignant": {},
                    "groupes_restants_cours": -1,
                    **ens_info,
                }
            ), 201

        return jsonify(
            {
                "success": True,
                "message": "Cours attribué!",
                "attribution_id": attr_id,
                "enseignant_id": ens_id,
                "code_cours": code_cr,
                "periodes_enseignant": periodes_maj,
                "groupes_restants_cours": grp_rest_maj,
                **ens_info,
            }
        ), 201
    except psycopg2.Error as e_psy:
        if db and not db.closed:
            db.rollback()
        app.logger.error(f"Erreur psycopg2 API ajouter attribution: {e_psy}")
        return jsonify({"success": False, "message": "Erreur BDD (ajout)."}), 500
    except Exception as e_gen:  # pylint: disable=broad-except
        if db and not db.closed:
            db.rollback()
        app.logger.error(f"Erreur Exception API ajouter attribution: {e_gen}")
        return jsonify({"success": False, "message": "Erreur serveur (ajout)."}), 500


@app.route("/api/attributions/supprimer", methods=["POST"])
def api_supprimer_attribution():
    """API pour supprimer une attribution de cours."""
    db = get_db()
    if not db:
        return jsonify({"success": False, "message": "Erreur BDD"}), 500
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "message": "Pas de données JSON"}), 400
    attr_id_req = data.get("attribution_id")
    if not attr_id_req:
        return jsonify({"success": False, "message": "ID attribution manquant"}), 400

    ens_id, code_cr, periodes_maj, grp_rest_maj, periodes_liberees, ens_data = None, None, {}, 0, 0, {}
    try:
        with db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            query_select = """
                SELECT ac.EnseignantID, ac.CodeCours, c.NbPeriodes AS PeriodesDuCours
                FROM AttributionsCours ac JOIN Cours c ON ac.CodeCours = c.CodeCours
                WHERE ac.AttributionID = %s;
            """
            cur.execute(query_select, (attr_id_req,))
            attr_info = cur.fetchone()
            if not attr_info:
                return jsonify({"success": False, "message": "Attribution non trouvée"}), 404

            ens_id = attr_info["enseignantid"]
            code_cr = attr_info["codecours"]
            periodes_liberees = attr_info.get("periodesducours", 0)

            cur.execute("DELETE FROM AttributionsCours WHERE AttributionID = %s;", (attr_id_req,))
            cur.execute("SELECT ChampNo, EstTempsPlein, EstFictif FROM Enseignants WHERE EnseignantID = %s", (ens_id,))
            res_ens = cur.fetchone()
            if res_ens:
                ens_data = dict(res_ens)
            db.commit()

        try:
            periodes_maj = calculer_periodes_enseignant(ens_id)
            grp_rest_maj = get_groupes_restants_pour_cours(code_cr)
        except Exception as e_calc:
            app.logger.error(f"Erreur post-suppression (calculs): {e_calc}")
            msg = "Supprimé, mais erreur MàJ totaux."
            return jsonify(
                {
                    "success": True,
                    "message": msg,
                    "enseignant_id": ens_id,
                    "code_cours": code_cr,
                    "nb_periodes_cours_libere": periodes_liberees,
                    "periodes_enseignant": {},
                    "groupes_restants_cours": -1,
                    **ens_data,
                }
            ), 200

        return jsonify(
            {
                "success": True,
                "message": "Attribution supprimée!",
                "enseignant_id": ens_id,
                "code_cours": code_cr,
                "periodes_enseignant": periodes_maj,
                "groupes_restants_cours": grp_rest_maj,
                "nb_periodes_cours_libere": periodes_liberees,
                **ens_data,
            }
        ), 200
    except psycopg2.Error as e_psy:
        if db and not db.closed:
            db.rollback()
        app.logger.error(f"Erreur psycopg2 API supprimer attribution: {e_psy}")
        if hasattr(e_psy, "pgcode") and e_psy.pgcode == "23503":
            return jsonify({"success": False, "message": "Suppression impossible (référence)."}), 409
        return jsonify({"success": False, "message": "Erreur BDD (suppression)."}), 500
    except Exception as e_gen:  # pylint: disable=broad-except
        if db and not db.closed:
            db.rollback()
        app.logger.error(f"Erreur Exception API supprimer attribution: {e_gen}")
        return jsonify({"success": False, "message": f"Erreur serveur (suppression): {str(e_gen)}"}), 500


@app.route("/api/champs/<string:champ_no>/taches_restantes/creer", methods=["POST"])
def api_creer_tache_restante(champ_no):
    """API pour créer une nouvelle tâche restante (enseignant fictif)."""
    db = get_db()
    if not db:
        return jsonify({"success": False, "message": "Erreur BDD"}), 500
    nouvel_ens_fictif = {}
    periodes_init = {"periodes_cours": 0, "periodes_autres": 0, "total_periodes": 0}
    try:
        with db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            query_select_exist = """
                SELECT NomComplet FROM Enseignants
                WHERE ChampNo = %s AND EstFictif = TRUE AND NomComplet LIKE %s;
            """
            cur.execute(query_select_exist, (champ_no, f"{champ_no}-Tâche restante-%"))
            taches_exist = cur.fetchall()
            max_num = 0
            for tache in taches_exist:
                try:
                    max_num = max(max_num, int(tache["nomcomplet"].split("-")[-1].strip()))
                except (ValueError, IndexError):
                    continue  # Ignorer si le format du nom n'est pas celui attendu
            nom_tache = f"{champ_no}-Tâche restante-{max_num + 1}"

            query_insert = """
                INSERT INTO Enseignants (NomComplet, ChampNo, EstTempsPlein, EstFictif, PeutChoisirHorsChampPrincipal)
                VALUES (%s, %s, FALSE, TRUE, FALSE)
                RETURNING EnseignantID, NomComplet, EstTempsPlein, EstFictif, PeutChoisirHorsChampPrincipal, ChampNo;
            """
            cur.execute(query_insert, (nom_tache, champ_no))
            res_insert = cur.fetchone()
            if res_insert is None:
                db.rollback()
                app.logger.error(f"INSERT tâche restante {nom_tache} sans retour.")
                return jsonify({"success": False, "message": "Erreur interne (création tâche)."}), 500
            nouvel_ens_fictif = dict(res_insert)
            db.commit()
        return jsonify(
            {
                "success": True,
                "message": "Tâche restante créée!",
                "enseignant": nouvel_ens_fictif,
                "periodes_actuelles": periodes_init,
                "attributions": [],
            }
        ), 201
    except psycopg2.Error as e_psy:
        if db and not db.closed:
            db.rollback()
        app.logger.error(f"Erreur psycopg2 API créer tâche: {e_psy}")
        return jsonify({"success": False, "message": "Erreur BDD (création tâche)."}), 500
    except Exception as e_gen:  # pylint: disable=broad-except
        if db and not db.closed:
            db.rollback()
        app.logger.error(f"Erreur Exception API créer tâche: {e_gen}")
        return jsonify({"success": False, "message": "Erreur serveur (création tâche)."}), 500


@app.route("/api/enseignants/<int:enseignant_id>/supprimer", methods=["POST"])
def api_supprimer_enseignant(enseignant_id):
    """API pour supprimer un enseignant."""
    db = get_db()
    if not db:
        return jsonify({"success": False, "message": "Erreur BDD"}), 500
    cours_liberes = []
    try:
        with db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT EstFictif FROM Enseignants WHERE EnseignantID = %s;", (enseignant_id,))
            if not cur.fetchone():  # Vérifie si l'enseignant existe
                return jsonify({"success": False, "message": "Enseignant non trouvé."}), 404

            query_cours_affectes = """
                SELECT DISTINCT ac.CodeCours, c.NbPeriodes
                FROM AttributionsCours ac JOIN Cours c ON ac.CodeCours = c.CodeCours
                WHERE ac.EnseignantID = %s;
            """
            cur.execute(query_cours_affectes, (enseignant_id,))
            cours_affectes = cur.fetchall()
            cur.execute("DELETE FROM Enseignants WHERE EnseignantID = %s;", (enseignant_id,))
            db.commit()

            if cours_affectes:
                # Utiliser un set pour les codes de cours uniques pour éviter des appels redondants
                for code_cours_unique in list(set(c["codecours"] for c in cours_affectes)):
                    grp_rest = get_groupes_restants_pour_cours(code_cours_unique)
                    nb_p = next((c["nbperiodes"] for c in cours_affectes if c["codecours"] == code_cours_unique), 0)
                    cours_liberes.append({"code_cours": code_cours_unique, "nouveaux_groupes_restants": grp_rest, "nb_periodes": nb_p})
        return jsonify(
            {
                "success": True,
                "message": "Enseignant supprimé. Cours libérés.",
                "enseignant_id": enseignant_id,
                "cours_liberes_details": cours_liberes,
            }
        ), 200
    except psycopg2.Error as e_psy:
        if db and not db.closed:
            db.rollback()
        if hasattr(e_psy, "pgcode") and e_psy.pgcode == "23503":  # Violation de clé étrangère
            app.logger.error(f"Erreur FK API supprimer enseignant: {e_psy}")
            msg = "Suppression impossible (référence autre que attributions)."
            return jsonify({"success": False, "message": msg}), 409
        app.logger.error(f"Erreur psycopg2 API supprimer enseignant: {e_psy}")
        return jsonify({"success": False, "message": "Erreur BDD (suppression enseignant)."}), 500
    except Exception as e_gen:  # pylint: disable=broad-except
        if db and not db.closed:
            db.rollback()
        app.logger.error(f"Erreur Exception API supprimer enseignant: {e_gen}")
        return jsonify({"success": False, "message": f"Erreur serveur (suppr. enseignant): {str(e_gen)}"}), 500


@app.route("/api/cours/reassigner_champ", methods=["POST"])
def api_reassigner_champ_cours():
    """API pour réassigner un cours à un nouveau champ."""
    db = get_db()
    if not db:
        return jsonify({"success": False, "message": "Erreur BDD"}), 500
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "message": "Pas de données JSON"}), 400
    code_cr = data.get("code_cours")
    nouv_champ_no = data.get("nouveau_champ_no")
    if not code_cr or not nouv_champ_no:
        return jsonify({"success": False, "message": "Données manquantes"}), 400

    nouv_champ_nom = ""
    try:
        with db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT ChampNo FROM Cours WHERE CodeCours = %s;", (code_cr,))
            cours_act = cur.fetchone()
            if not cours_act:
                return jsonify({"success": False, "message": f"Cours {code_cr} non trouvé."}), 404
            cur.execute("SELECT ChampNom FROM Champs WHERE ChampNo = %s;", (nouv_champ_no,))
            champ_dest = cur.fetchone()
            if not champ_dest:
                return jsonify({"success": False, "message": f"Champ destination {nouv_champ_no} non trouvé."}), 404
            nouv_champ_nom = champ_dest["champnom"]

            if cours_act["champno"] == nouv_champ_no:
                msg = f"Cours {code_cr} déjà dans champ " f"{nouv_champ_no} ({nouv_champ_nom})."
                return jsonify({"success": False, "message": msg, "nouveau_champ_no": nouv_champ_no, "nouveau_champ_nom": nouv_champ_nom}), 409

            cur.execute("UPDATE Cours SET ChampNo = %s WHERE CodeCours = %s;", (nouv_champ_no, code_cr))
            if cur.rowcount == 0:  # Vérifie si la mise à jour a réellement affecté une ligne
                db.rollback()
                app.logger.error(f"UPDATE ChampNo pour {code_cr} sans effet.")
                return jsonify({"success": False, "message": "MàJ cours sans effet."}), 500
            db.commit()
        return jsonify(
            {
                "success": True,
                "message": f"Cours {code_cr} réassigné à {nouv_champ_no} ({nouv_champ_nom}).",
                "code_cours": code_cr,
                "nouveau_champ_no": nouv_champ_no,
                "nouveau_champ_nom": nouv_champ_nom,
            }
        ), 200
    except psycopg2.Error as e_psy:
        if db and not db.closed:
            db.rollback()
        app.logger.error(f"Erreur psycopg2 API réassigner champ: {e_psy}")
        return jsonify({"success": False, "message": "Erreur BDD (réassignation)."}), 500
    except Exception as e_gen:  # pylint: disable=broad-except
        if db and not db.closed:
            db.rollback()
        app.logger.error(f"Erreur Exception API réassigner champ: {e_gen}")
        return jsonify({"success": False, "message": f"Erreur serveur (réassign.): {str(e_gen)}"}), 500


# --- Fonctions utilitaires et routes pour l'importation de données Excel ---
def allowed_file(filename):
    """Vérifie si l'extension du fichier est autorisée."""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route("/administration/importer_cours_excel", methods=["POST"])
def api_importer_cours_excel():
    """Importe les cours depuis un fichier Excel, écrase les données existantes."""
    db = get_db()
    if not db:
        flash("Erreur de connexion à la base de données.", "error")
        return redirect(url_for("page_administration_donnees"))

    if "fichier_cours" not in request.files:
        flash("Aucun fichier sélectionné pour l'importation des cours.", "warning")
        return redirect(url_for("page_administration_donnees"))

    file = request.files["fichier_cours"]
    if not file or not file.filename:  # Vérification plus robuste
        flash("Aucun fichier sélectionné pour les cours (nom de fichier vide).", "warning")
        return redirect(url_for("page_administration_donnees"))

    if allowed_file(file.filename):
        nouveaux_cours = []
        try:
            workbook = openpyxl.load_workbook(file.stream)
            sheet = workbook.active
            assert isinstance(sheet, Worksheet), "La feuille active n'est pas du type attendu."

            iter_rows = iter(sheet.rows)
            try:
                next(iter_rows)  # Sauter la ligne d'en-tête
            except StopIteration:  # Fichier vide ou que en-têtes
                flash("Le fichier Excel des cours est vide ou ne contient que des données d'en-tête.", "warning")
                return redirect(url_for("page_administration_donnees"))

            for row_idx, row in enumerate(iter_rows, start=2):
                try:
                    champ_no_raw, code_cours_raw, cours_descriptif_raw = row[0].value, row[1].value, row[3].value
                    champ_no = str(champ_no_raw).strip() if champ_no_raw is not None else None
                    code_cours = str(code_cours_raw).strip() if code_cours_raw is not None else None
                    cours_descriptif = str(cours_descriptif_raw).strip() if cours_descriptif_raw is not None else None

                    if not all([champ_no, code_cours, cours_descriptif]):
                        flash(f"Ligne {row_idx} (Cours): Données manquantes (Champ/Code/Descr.). Ligne ignorée.", "warning")
                        continue

                    nb_groupe_initial, nb_periodes = 0, 0  # Valeurs par défaut
                    cell_val_grp, cell_val_per = row[4].value, row[5].value

                    if isinstance(cell_val_grp, int | float):
                        nb_groupe_initial = int(cell_val_grp)
                    elif isinstance(cell_val_grp, str) and cell_val_grp.strip().isdigit():
                        nb_groupe_initial = int(cell_val_grp.strip())
                    elif cell_val_grp is not None:
                        flash(f"Ligne {row_idx} (Cours): Val. non num. '{cell_val_grp}' pr Groupes. Ignorée.", "warning")
                        continue

                    if isinstance(cell_val_per, int | float):
                        nb_periodes = int(cell_val_per)
                    elif isinstance(cell_val_per, str) and cell_val_per.strip().isdigit():
                        nb_periodes = int(cell_val_per.strip())
                    elif cell_val_per is not None:
                        flash(f"Ligne {row_idx} (Cours): Val. non num. '{cell_val_per}' pr Périodes. Ignorée.", "warning")
                        continue

                    est_cours_autre_raw = row[7].value
                    est_cours_autre = str(est_cours_autre_raw).strip().upper() == "VRAI" if est_cours_autre_raw is not None else False

                    nouveaux_cours.append(
                        {
                            "codecours": code_cours,
                            "champno": champ_no,
                            "coursdescriptif": cours_descriptif,
                            "nbperiodes": nb_periodes,
                            "nbgroupeinitial": nb_groupe_initial,
                            "estcoursautre": est_cours_autre,
                        }
                    )
                except IndexError:
                    flash(f"Ligne {row_idx} (Cours): Pas assez de colonnes. Ignorée.", "warning")
                    continue
                except TypeError as te:
                    flash(f"Ligne {row_idx} (Cours): Erreur de type. Ignorée. {te}", "warning")
                    continue

            if not nouveaux_cours:
                flash("Aucun cours valide lu depuis Excel.", "warning")
                return redirect(url_for("page_administration_donnees"))

            with db.cursor() as cur:
                cur.execute("DELETE FROM AttributionsCours;")
                cur.execute("DELETE FROM Cours;")
                for cours_data in nouveaux_cours:
                    try:
                        cur.execute(
                            "INSERT INTO Cours (CodeCours, ChampNo, CoursDescriptif, NbPeriodes,\
                            NbGroupeInitial, EstCoursAutre) VALUES (%(codecours)s, %(champno)s,\
                            %(coursdescriptif)s, %(nbperiodes)s, %(nbgroupeinitial)s, %(estcoursautre)s);",
                            cours_data,
                        )
                    except psycopg2.Error as e_ins:
                        db.rollback()
                        err_det = e_ins.pgerror if hasattr(e_ins, "pgerror") else str(e_ins)
                        code = cours_data.get("codecours", "INCONNU")
                        err_msg = f"Erreur insertion cours '{code}': {err_det}. Import annulé."
                        flash(err_msg, "error")
                        app.logger.error(err_msg)
                        return redirect(url_for("page_administration_donnees"))
                db.commit()
                flash(f"{len(nouveaux_cours)} cours importés. Anciens cours/attributions écrasés.", "success")

        except InvalidFileException:
            flash("Fichier cours .xlsx invalide.", "error")
        except Exception as e:  # pylint: disable=broad-except
            if db and not db.closed and not db.autocommit:
                db.rollback()
            app.logger.error(f"Erreur inattendue (import cours): {type(e).__name__} - {e}")
            flash(f"Erreur inattendue (import cours): {type(e).__name__}", "error")
        return redirect(url_for("page_administration_donnees"))
    else:
        flash("Type fichier cours non autorisé (.xlsx seulement).", "error")
        return redirect(url_for("page_administration_donnees"))


@app.route("/administration/importer_enseignants_excel", methods=["POST"])
def api_importer_enseignants_excel():
    """Importe les enseignants depuis Excel, écrase les données existantes."""
    db = get_db()
    if not db:
        flash("Erreur connexion BDD.", "error")
        return redirect(url_for("page_administration_donnees"))

    if "fichier_enseignants" not in request.files:
        flash("Aucun fichier enseignants sélectionné.", "warning")
        return redirect(url_for("page_administration_donnees"))

    file = request.files["fichier_enseignants"]
    if not file or not file.filename:
        flash("Aucun fichier enseignants sélectionné (nom de fichier vide).", "warning")
        return redirect(url_for("page_administration_donnees"))

    if allowed_file(file.filename):
        nouveaux_enseignants = []
        try:
            workbook = openpyxl.load_workbook(file.stream)
            sheet = workbook.active
            assert isinstance(sheet, Worksheet), "La feuille active n'est pas du type attendu."

            iter_rows = iter(sheet.rows)
            try:
                next(iter_rows)  # Sauter en-tête
            except StopIteration:
                flash("Fichier Excel enseignants vide ou que en-têtes.", "warning")
                return redirect(url_for("page_administration_donnees"))

            for row_idx, row in enumerate(iter_rows, start=2):
                try:
                    champ_no_raw, nom_raw, prenom_raw = row[0].value, row[1].value, row[2].value
                    champ_no = str(champ_no_raw).strip() if champ_no_raw is not None else None
                    nom = str(nom_raw).strip() if nom_raw is not None else None
                    prenom = str(prenom_raw).strip() if prenom_raw is not None else None

                    if not all([champ_no, nom, prenom]):
                        flash(f"Ligne {row_idx} (Ens.): Données manquantes (Champ/Nom/Prénom). Ignorée.", "warning")
                        continue

                    nom_complet = f"{prenom} {nom}"
                    temps_plein_raw = row[3].value
                    # Par défaut à True si la cellule est vide, sinon évalue "VRAI"
                    est_temps_plein = str(temps_plein_raw).strip().upper() == "VRAI" if temps_plein_raw is not None else True

                    nouveaux_enseignants.append(
                        {
                            "nomcomplet": nom_complet,
                            "champno": champ_no,
                            "esttempsplein": est_temps_plein,
                            "estfictif": False,
                            "peutchoisirhorschampprincipal": False,  # Valeurs par défaut
                        }
                    )
                except IndexError:
                    flash(f"Ligne {row_idx} (Ens.): Pas assez de colonnes. Ignorée.", "warning")
                    continue
                except TypeError as te:
                    flash(f"Ligne {row_idx} (Ens.): Erreur de type. Ignorée. {te}", "warning")
                    continue

            if not nouveaux_enseignants:
                flash("Aucun enseignant valide lu depuis Excel.", "warning")
                return redirect(url_for("page_administration_donnees"))

            with db.cursor() as cur:
                cur.execute("DELETE FROM AttributionsCours;")  # Doit être fait avant Enseignants
                cur.execute("DELETE FROM Enseignants;")
                for ens_data in nouveaux_enseignants:
                    try:
                        cur.execute(
                            "INSERT INTO Enseignants (NomComplet, ChampNo, EstTempsPlein, EstFictif, PeutChoisirHorsChampPrincipal) VALUES \
                            (%(nomcomplet)s, %(champno)s, %(esttempsplein)s, %(estfictif)s, %(peutchoisirhorschampprincipal)s);",
                            ens_data,
                        )
                    except psycopg2.Error as e_ins:
                        db.rollback()
                        err_det = e_ins.pgerror if hasattr(e_ins, "pgerror") else str(e_ins)
                        nom_c = ens_data.get("nomcomplet", "INCONNU")
                        err_msg = f"Erreur insertion enseignant '{nom_c}': {err_det}. Import annulé."
                        flash(err_msg, "error")
                        app.logger.error(err_msg)
                        return redirect(url_for("page_administration_donnees"))
                db.commit()
                flash(f"{len(nouveaux_enseignants)} enseignants importés. Anciens enseignants/attributions écrasés.", "success")

        except InvalidFileException:
            flash("Fichier enseignants .xlsx invalide.", "error")
        except Exception as e:  # pylint: disable=broad-except
            if db and not db.closed and not db.autocommit:
                db.rollback()
            app.logger.error(f"Erreur inattendue (import enseignants): {type(e).__name__} - {e}")
            flash(f"Erreur inattendue (import enseignants): {type(e).__name__}", "error")
        return redirect(url_for("page_administration_donnees"))
    else:
        flash("Type fichier enseignants non autorisé (.xlsx seulement).", "error")
        return redirect(url_for("page_administration_donnees"))


# --- Démarrage de l'application ---
if __name__ == "__main__":
    # Pour un logging plus verbeux en développement:
    # import logging
    # console_handler = logging.StreamHandler()
    # console_handler.setLevel(logging.INFO)
    # app.logger.addHandler(console_handler)
    # app.logger.setLevel(logging.INFO)
    app.run(host="0.0.0.0", port=8080, debug=True)
