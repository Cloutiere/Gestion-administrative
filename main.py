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
    """
    Récupère tous les enseignants avec les détails de leur champ, leurs périodes de cours et autres.
    Les enseignants sont triés par numéro de champ, puis par statut fictif, puis par nom.
    """
    db = get_db()
    if not db:
        return []
    enseignants_complets = []
    try:
        with db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """
                SELECT e.EnseignantID, e.NomComplet, e.EstTempsPlein, e.EstFictif,
                       e.ChampNo, ch.ChampNom, e.PeutChoisirHorsChampPrincipal
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
                    **ens_brut,  # Contient EnseignantID, NomComplet, EstTempsPlein, EstFictif, ChampNo, ChampNom
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
        # Assurer que grprestant est au moins 0 si aucun groupe n'a été pris
        initial_groups_if_no_attributions_query = "SELECT NbGroupeInitial FROM Cours WHERE CodeCours = %s;"
        if result is None or result["grprestant"] is None: # Cas où le cours existe mais n'a AUCUNE attribution.
            with db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur_init:
                cur_init.execute(initial_groups_if_no_attributions_query, (code_cours,))
                initial_result = cur_init.fetchone()
            return initial_result["nbgroupeinitial"] if initial_result else 0
        return result["grprestant"]
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
    enseignants_par_champ_data, moyennes_champs, moyenne_gen = calculer_donnees_sommaire()
    current_year = datetime.datetime.now().year
    return render_template(
        "page_sommaire.html",
        enseignants_par_champ=enseignants_par_champ_data,  # MODIFIÉ
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
    """
    Calcule les données agrégées pour la page sommaire.
    Retourne les enseignants groupés par champ avec totaux, les moyennes par champ,
    et la moyenne générale.
    """
    tous_enseignants_details = get_all_enseignants_avec_details()
    # Structure temporaire pour regrouper les enseignants et calculer les totaux par champ
    enseignants_par_champ_temp = {}
    moyennes_par_champ_calculees = {}
    total_periodes_global_tp = 0
    nb_enseignants_tp_global = 0

    for ens in tous_enseignants_details:
        champ_no = ens["champno"]
        champ_nom = ens["champnom"]

        # Initialisation du champ s'il n'existe pas encore
        if champ_no not in enseignants_par_champ_temp:
            enseignants_par_champ_temp[champ_no] = {
                "champno": champ_no,
                "champnom": champ_nom,
                "enseignants": [],
                "total_periodes_cours_champ": 0,
                "total_periodes_autres_champ": 0,
                "total_periodes_champ": 0,
            }

        # Ajout de l'enseignant à son champ
        enseignants_par_champ_temp[champ_no]["enseignants"].append(ens)

        # Mise à jour des totaux de périodes pour le champ
        enseignants_par_champ_temp[champ_no]["total_periodes_cours_champ"] += ens["periodes_cours"]
        enseignants_par_champ_temp[champ_no]["total_periodes_autres_champ"] += ens["periodes_autres"]
        enseignants_par_champ_temp[champ_no]["total_periodes_champ"] += ens["total_periodes"]

        # Calcul pour les moyennes (enseignants temps plein non fictifs)
        if ens["compte_pour_moyenne_champ"]:
            if champ_no not in moyennes_par_champ_calculees:
                moyennes_par_champ_calculees[champ_no] = {
                    "champ_nom": champ_nom,
                    "total_periodes": 0,
                    "nb_enseignants": 0,
                    "moyenne": 0.0,
                }
            moyennes_par_champ_calculees[champ_no]["total_periodes"] += ens["total_periodes"]
            moyennes_par_champ_calculees[champ_no]["nb_enseignants"] += 1

            total_periodes_global_tp += ens["total_periodes"]
            nb_enseignants_tp_global += 1

    # Calcul final des moyennes par champ
    for data_champ in moyennes_par_champ_calculees.values():
        if data_champ["nb_enseignants"] > 0:
            data_champ["moyenne"] = data_champ["total_periodes"] / data_champ["nb_enseignants"]
        # Supprimer les clés temporaires non nécessaires pour le template
        del data_champ["total_periodes"]
        del data_champ["nb_enseignants"]


    moyenne_generale_calculee = (
        (total_periodes_global_tp / nb_enseignants_tp_global) if nb_enseignants_tp_global > 0 else 0
    )

    # Convertir le dictionnaire des enseignants par champ en une liste triée par champNo
    # Le tri est déjà fait par la requête SQL dans get_all_enseignants_avec_details
    enseignants_par_champ_final = list(enseignants_par_champ_temp.values())

    return enseignants_par_champ_final, moyennes_par_champ_calculees, moyenne_generale_calculee


# --- API ENDPOINTS ---
@app.route("/api/sommaire/donnees", methods=["GET"])
def api_get_donnees_sommaire():
    """API pour récupérer les données actualisées du sommaire global."""
    enseignants_groupes, moyennes_champs, moyenne_gen = calculer_donnees_sommaire()
    return jsonify({
        "enseignants_par_champ": enseignants_groupes,  # MODIFIÉ
        "moyennes_par_champ": moyennes_champs,
        "moyenne_generale": moyenne_gen,
    })


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
            # Vérifier les groupes disponibles avant l'insertion
            # Cette sous-requête est plus sûre pour calculer les groupes pris
            query_grp_dispo = """
                SELECT (c.NbGroupeInitial - COALESCE(SUM(ac.NbGroupesPris), 0)) AS grp_dispo
                FROM Cours c
                LEFT JOIN AttributionsCours ac ON c.CodeCours = ac.CodeCours AND c.CodeCours = %s
                WHERE c.CodeCours = %s
                GROUP BY c.NbGroupeInitial;
            """
            cur.execute(query_grp_dispo, (code_cours, code_cours))
            cours_info = cur.fetchone()

            # Gérer le cas où le cours n'a aucune attribution (cours_info peut être None)
            # ou si tous les groupes sont déjà pris
            groupes_disponibles_actuels = 0
            if cours_info and cours_info["grp_dispo"] is not None:
                groupes_disponibles_actuels = cours_info["grp_dispo"]
            else: # Si cours_info est None, le cours n'a pas d'attributions, donc tous les groupes initiaux sont dispo
                cur.execute("SELECT NbGroupeInitial FROM Cours WHERE CodeCours = %s", (code_cours,))
                initial_groups_info = cur.fetchone()
                if initial_groups_info:
                    groupes_disponibles_actuels = initial_groups_info["nbgroupeinitial"]
                else: # Le cours n'existe pas
                     return jsonify({"success": False, "message": "Cours non trouvé."}), 404


            if groupes_disponibles_actuels < 1:
                return jsonify({"success": False, "message": "Plus de groupes disponibles pour ce cours."}), 409

            cur.execute(
                "INSERT INTO AttributionsCours (EnseignantID, CodeCours, NbGroupesPris) VALUES (%s, %s, %s) RETURNING AttributionID;",
                (enseignant_id, code_cours, 1), # On attribue toujours 1 groupe à la fois
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
                "groupes_restants_cours": -1, # Indique une erreur de calcul
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
            "attributions_enseignant": attributions_enseignant_maj,
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
    attributions_enseignant_maj = []
    periodes_liberees_par_suppression = 0
    infos_enseignant_pour_reponse = {}

    try:
        with db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            # Récupérer les informations de l'attribution avant suppression
            query_select_attribution = """
                SELECT ac.EnseignantID, ac.CodeCours, c.NbPeriodes AS PeriodesDuCours, ac.NbGroupesPris
                FROM AttributionsCours ac JOIN Cours c ON ac.CodeCours = c.CodeCours
                WHERE ac.AttributionID = %s;
            """
            cur.execute(query_select_attribution, (attribution_id_a_supprimer,))
            attribution_info = cur.fetchone()
            if not attribution_info:
                return jsonify({"success": False, "message": "Attribution non trouvée."}), 404

            enseignant_id_concerne = attribution_info["enseignantid"]
            code_cours_concerne = attribution_info["codecours"]
            # Les périodes libérées sont NbPeriodesDuCours * NbGroupesPris (ici, NbGroupesPris est toujours 1)
            periodes_liberees_par_suppression = attribution_info.get("periodesducours", 0) * attribution_info.get("nbgroupespris", 0)


            cur.execute("DELETE FROM AttributionsCours WHERE AttributionID = %s;", (attribution_id_a_supprimer,))
            if cur.rowcount == 0: # Devrait pas arriver si fetchone() a réussi avant
                db.rollback()
                return jsonify({"success": False, "message": "Attribution non trouvée ou déjà supprimée (concurrence?)."}), 404

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
                "groupes_restants_cours": -1, # Indique une erreur de calcul
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
            "attributions_enseignant": attributions_enseignant_maj,
            "nb_periodes_cours_libere": periodes_liberees_par_suppression,
            **infos_enseignant_pour_reponse,
        }), 200

    except psycopg2.Error as e_psy:
        if db and not db.closed:
            db.rollback()
        app.logger.error(f"Erreur psycopg2 API supprimer attribution: {e_psy}")
        if hasattr(e_psy, "pgcode") and e_psy.pgcode == "23503": # Foreign key violation
            return jsonify({"success": False, "message": "Suppression impossible car l'attribution est référencée ailleurs."}), 409
        return jsonify({"success": False, "message": "Erreur de base de données lors de la suppression de l'attribution."}), 500
    except Exception as e_gen:  # pylint: disable=broad-except
        if db and not db.closed:
            db.rollback()
        app.logger.error(f"Erreur générale Exception API supprimer attribution: {e_gen}")
        return jsonify({"success": False, "message": f"Erreur serveur inattendue lors de la suppression: {str(e_gen)}"}), 500


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
            # Trouver le prochain numéro disponible pour la tâche restante
            query_select_taches_existantes = """
                SELECT NomComplet FROM Enseignants
                WHERE ChampNo = %s AND EstFictif = TRUE AND NomComplet LIKE %s;
            """
            # Le pattern doit utiliser % pour la recherche SQL LIKE
            pattern_nom_tache = f"{champ_no}-Tâche restante-%"
            cur.execute(query_select_taches_existantes, (champ_no, pattern_nom_tache))
            taches_existantes = cur.fetchall()

            max_numero_tache = 0
            for tache in taches_existantes:
                nom_tache = tache["nomcomplet"]
                # Extraire le numéro à la fin, après le dernier '-'
                parts = nom_tache.split("-")
                if len(parts) > 1:
                    num_part = parts[-1].strip()
                    if num_part.isdigit():
                        numero = int(num_part)
                        max_numero_tache = max(max_numero_tache, numero)

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
            "enseignant": {**nouvel_enseignant_fictif_cree, "attributions": []}, # Nouvelle tâche, pas d'attributions
            "periodes_actuelles": periodes_initiales_tache,
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
            # Vérifier si l'enseignant existe et est fictif (logique métier, peut être assouplie si besoin)
            cur.execute("SELECT EstFictif FROM Enseignants WHERE EnseignantID = %s;", (enseignant_id,))
            enseignant_info = cur.fetchone()
            if not enseignant_info:
                return jsonify({"success": False, "message": "Enseignant non trouvé."}), 404

            # Bien que la suppression en cascade via la BDD pourrait gérer les attributions,
            # il est bon de savoir quels cours sont affectés pour mettre à jour le front-end.
            query_cours_affectes_enseignant = """
                SELECT DISTINCT ac.CodeCours, c.NbPeriodes
                FROM AttributionsCours ac JOIN Cours c ON ac.CodeCours = c.CodeCours
                WHERE ac.EnseignantID = %s;
            """
            cur.execute(query_cours_affectes_enseignant, (enseignant_id,))
            cours_affectes_avant_suppression = cur.fetchall()

            # Supprimer d'abord les attributions (si pas de ON DELETE CASCADE sur la FK EnseignantID dans AttributionsCours)
            # S'il y a ON DELETE CASCADE, cette ligne n'est pas strictement nécessaire mais ne nuit pas.
            cur.execute("DELETE FROM AttributionsCours WHERE EnseignantID = %s;", (enseignant_id,))

            # Puis supprimer l'enseignant
            cur.execute("DELETE FROM Enseignants WHERE EnseignantID = %s;", (enseignant_id,))
            if cur.rowcount == 0: # Si l'enseignant n'a pas été trouvé ou déjà supprimé
                db.rollback()
                return jsonify({"success": False, "message": "L'enseignant n'a pas pu être supprimé (déjà supprimé?)."}), 404
            db.commit()

            # Recalculer les groupes restants pour les cours affectés
            if cours_affectes_avant_suppression:
                # Utiliser un set pour éviter de recalculer pour le même cours plusieurs fois
                # si un enseignant avait plusieurs groupes du même cours (ce qui n'est pas le cas ici car 1 grp/attribution)
                codes_cours_uniques = list(set(c["codecours"] for c in cours_affectes_avant_suppression))
                for code_cours_unique in codes_cours_uniques:
                    groupes_restants_maj = get_groupes_restants_pour_cours(code_cours_unique)
                    # Trouver le nombre de périodes pour ce cours
                    nb_periodes = next(
                        (c["nbperiodes"] for c in cours_affectes_avant_suppression if c["codecours"] == code_cours_unique), 0
                    )
                    cours_liberes_apres_suppression.append({
                        "code_cours": code_cours_unique,
                        "nouveaux_groupes_restants": groupes_restants_maj,
                        "nb_periodes": nb_periodes, # Utile si le front-end veut afficher les périodes libérées
                    })
        return jsonify({
            "success": True,
            "message": "Enseignant et ses attributions supprimés avec succès. Groupes de cours mis à jour.",
            "enseignant_id": enseignant_id,
            "cours_liberes_details": cours_liberes_apres_suppression,
        }), 200

    except psycopg2.Error as e_psy:
        if db and not db.closed:
            db.rollback()
        # Gérer spécifiquement les violations de contrainte de clé étrangère
        # si la suppression des attributions n'était pas faite ou si d'autres tables référencent Enseignants
        if hasattr(e_psy, "pgcode") and e_psy.pgcode == "23503": # foreign_key_violation
            msg_err_fk = (
                f"Suppression de l'enseignant {enseignant_id} impossible "
                "car il est référencé dans d'autres tables (ex: attributions non gérées en cascade)."
            )
            app.logger.error(f"{msg_err_fk} Détail: {e_psy}")
            return jsonify({"success": False, "message": msg_err_fk}), 409
        app.logger.error(f"Erreur psycopg2 API supprimer enseignant: {e_psy}")
        return jsonify({"success": False, "message": "Erreur de base de données lors de la suppression de l'enseignant."}), 500
    except Exception as e_gen:  # pylint: disable=broad-except
        if db and not db.closed:
            db.rollback()
        app.logger.error(f"Erreur générale Exception API supprimer enseignant: {e_gen}")
        msg = f"Erreur serveur inattendue lors de la suppression de l'enseignant: {str(e_gen)}"
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
            # Vérifier si le cours existe
            cur.execute("SELECT ChampNo FROM Cours WHERE CodeCours = %s;", (code_cours_a_reassigner,))
            cours_actuel_info = cur.fetchone()
            if not cours_actuel_info:
                msg = f"Le cours {code_cours_a_reassigner} n'a pas été trouvé."
                return jsonify({"success": False, "message": msg}), 404

            # Vérifier si le champ de destination existe
            cur.execute("SELECT ChampNom FROM Champs WHERE ChampNo = %s;", (nouveau_champ_no_destination,))
            champ_destination_info = cur.fetchone()
            if not champ_destination_info:
                msg = f"Le champ de destination {nouveau_champ_no_destination} n'a pas été trouvé."
                return jsonify({"success": False, "message": msg}), 404
            nom_nouveau_champ = champ_destination_info["champnom"]

            # Vérifier si le cours est déjà dans le champ destination
            if str(cours_actuel_info["champno"]) == str(nouveau_champ_no_destination): # Comparer comme str pour être sûr
                message_deja_assigne = (
                    f"Le cours {code_cours_a_reassigner} est déjà assigné au champ "
                    f"{nouveau_champ_no_destination} ({nom_nouveau_champ}). Aucune action requise."
                )
                return jsonify({
                    "success": True, # Ou False avec code 409 (Conflict) si on considère que c'est une non-opération
                    "message": message_deja_assigne,
                    "code_cours": code_cours_a_reassigner,
                    "nouveau_champ_no": nouveau_champ_no_destination,
                    "nouveau_champ_nom": nom_nouveau_champ,
                }), 200 # OK, mais rien n'a changé

            # Mettre à jour le champ du cours
            cur.execute("UPDATE Cours SET ChampNo = %s WHERE CodeCours = %s;", (nouveau_champ_no_destination, code_cours_a_reassigner))
            if cur.rowcount == 0: # Ne devrait pas arriver si le cours existe
                db.rollback()
                msg = f"La mise à jour du ChampNo pour le cours {code_cours_a_reassigner} n'a affecté aucune ligne."
                app.logger.error(msg)
                return jsonify({"success": False, "message": "La mise à jour du champ du cours n'a pas eu d'effet."}), 500
            db.commit()

        return jsonify({
            "success": True,
            "message": f"Le cours {code_cours_a_reassigner} a été réassigné avec succès au champ {nouveau_champ_no_destination} ({nom_nouveau_champ}).",
            "code_cours": code_cours_a_reassigner,
            "nouveau_champ_no": nouveau_champ_no_destination,
            "nouveau_champ_nom": nom_nouveau_champ,
        }), 200

    except psycopg2.Error as e_psy:
        if db and not db.closed:
            db.rollback()
        app.logger.error(f"Erreur psycopg2 API réassigner champ cours: {e_psy}")
        # Vérifier si c'est une violation de clé étrangère (si ChampNo est une FK vers Champs)
        if hasattr(e_psy, "pgcode") and e_psy.pgcode == "23503": # foreign_key_violation
            msg = f"Réassignation impossible: le champ de destination '{nouveau_champ_no_destination}' n'existe pas ou problème de référence."
            return jsonify({"success": False, "message": msg }), 400 # Bad request (donnée invalide)
        return jsonify({"success": False, "message": "Erreur de base de données lors de la réassignation du champ du cours."}), 500
    except Exception as e_gen:  # pylint: disable=broad-except
        if db and not db.closed:
            db.rollback()
        app.logger.error(f"Erreur générale Exception API réassigner champ cours: {e_gen}")
        msg = f"Erreur serveur inattendue lors de la réassignation du champ du cours: {str(e_gen)}"
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
        flash("Erreur de connexion à la base de données. Importation des cours annulée.", "error")
        return redirect(url_for("page_administration_donnees"))

    if "fichier_cours" not in request.files:
        flash("Aucun fichier sélectionné pour l'importation des cours.", "warning")
        return redirect(url_for("page_administration_donnees"))

    file = request.files["fichier_cours"]
    if not file or not file.filename: # Vérifier si file.filename est vide
        flash("Nom de fichier vide pour l'importation des cours.", "warning")
        return redirect(url_for("page_administration_donnees"))

    if not allowed_file(file.filename):
        flash("Type de fichier non autorisé pour les cours. Seuls les fichiers .xlsx sont acceptés.", "error")
        return redirect(url_for("page_administration_donnees"))

    nouveaux_cours_a_importer = []
    try:
        workbook = openpyxl.load_workbook(file.stream) # Utiliser file.stream est plus sûr
        sheet = workbook.active
        if not isinstance(sheet, Worksheet): # Vérification de type plus explicite
            flash("La feuille active du fichier Excel des cours est invalide.", "error")
            return redirect(url_for("page_administration_donnees"))


        iter_rows = iter(sheet.rows)
        try:
            next(iter_rows)  # Ignorer la ligne d'en-tête
        except StopIteration:
            flash("Le fichier Excel des cours est vide ou ne contient que l'en-tête.", "warning")
            return redirect(url_for("page_administration_donnees"))

        lignes_ignorees_compt = 0
        for row_idx, row in enumerate(iter_rows, start=2): # start=2 car on a sauté l'en-tête
            try:
                # Extraire les valeurs des cellules et les nettoyer
                champ_no_raw = row[0].value
                code_cours_raw = row[1].value
                # Colonne 2 (Nom du champ) est ignorée, car ChampNo est la référence
                cours_descriptif_raw = row[3].value
                nb_groupe_initial_raw = row[4].value
                nb_periodes_raw = row[5].value
                # Colonne 6 (Type de cours) est ignorée
                est_cours_autre_raw = row[7].value

                champ_no = str(champ_no_raw).strip() if champ_no_raw is not None else None
                code_cours = str(code_cours_raw).strip() if code_cours_raw is not None else None
                cours_descriptif = str(cours_descriptif_raw).strip() if cours_descriptif_raw is not None else None

                if not all([champ_no, code_cours, cours_descriptif]):
                    flash(f"Ligne {row_idx} (Cours): Données essentielles (ChampNo, CodeCours, Descriptif) manquantes. Ligne ignorée.", "warning")
                    lignes_ignorees_compt +=1
                    continue

                # Conversion sécurisée des nombres
                nb_groupe_initial = 0
                if isinstance(nb_groupe_initial_raw, int | float):
                    nb_groupe_initial = int(nb_groupe_initial_raw)
                elif isinstance(nb_groupe_initial_raw, str) and nb_groupe_initial_raw.strip().isdigit():
                    nb_groupe_initial = int(nb_groupe_initial_raw.strip())
                elif nb_groupe_initial_raw is not None: # Si non None et non convertible
                    flash(f"Ligne {row_idx} (Cours): Valeur non numérique ou incorrecte pour 'Nb Groupes Prévus' ('{nb_groupe_initial_raw}'). Ligne ignorée.", "warning")
                    lignes_ignorees_compt +=1
                    continue

                nb_periodes = 0
                if isinstance(nb_periodes_raw, int | float):
                    nb_periodes = int(nb_periodes_raw)
                elif isinstance(nb_periodes_raw, str) and nb_periodes_raw.strip().isdigit():
                    nb_periodes = int(nb_periodes_raw.strip())
                elif nb_periodes_raw is not None: # Si non None et non convertible
                    flash(f"Ligne {row_idx} (Cours): Valeur non numérique ou incorrecte pour 'Périodes/GR' ('{nb_periodes_raw}'). Ligne ignorée.", "warning")
                    lignes_ignorees_compt +=1
                    continue

                # Conversion du booléen 'EstCoursAutre'
                est_cours_autre = False # Valeur par défaut
                if isinstance(est_cours_autre_raw, bool):
                    est_cours_autre = est_cours_autre_raw
                elif isinstance(est_cours_autre_raw, str):
                    val_str_upper = est_cours_autre_raw.strip().upper()
                    if val_str_upper in ("VRAI", "TRUE", "1", "OUI", "YES"):
                        est_cours_autre = True
                    elif val_str_upper in ("FAUX", "FALSE", "0", "NON", "NO", ""): # Chaîne vide aussi FAUX
                        est_cours_autre = False
                    else:
                        flash(f"Ligne {row_idx} (Cours): Valeur inattendue pour 'EstCoursAutre' ('{est_cours_autre_raw}'). Assumée FAUX.", "warning")
                elif est_cours_autre_raw is not None: # Si c'est un nombre par exemple
                     flash(f"Ligne {row_idx} (Cours): Valeur inattendue pour 'EstCoursAutre' ('{est_cours_autre_raw}'). Assumée FAUX.", "warning")


                nouveaux_cours_a_importer.append({
                    "codecours": code_cours,
                    "champno": champ_no,
                    "coursdescriptif": cours_descriptif,
                    "nbperiodes": nb_periodes,
                    "nbgroupeinitial": nb_groupe_initial,
                    "estcoursautre": est_cours_autre,
                })
            except IndexError: # Moins de colonnes que prévu
                flash(f"Ligne {row_idx} (Cours): Nombre de colonnes insuffisant. La ligne est ignorée.", "warning")
                lignes_ignorees_compt +=1
                continue
            except (TypeError, ValueError) as te: # Erreur de conversion de type inattendue
                flash(f"Ligne {row_idx} (Cours): Erreur de type de donnée ou de valeur. Ligne ignorée. Détails: {te}", "warning")
                lignes_ignorees_compt +=1
                continue

        if lignes_ignorees_compt > 0:
            flash(f"{lignes_ignorees_compt} ligne(s) du fichier cours ont été ignorée(s) en raison d'erreurs.", "info")

        if not nouveaux_cours_a_importer:
            flash("Aucun cours valide n'a été lu depuis le fichier. Aucune modification n'a été apportée à la base de données.", "warning")
            return redirect(url_for("page_administration_donnees"))

        # Procéder à l'importation en base de données
        with db.cursor() as cur:
            # Vider les tables dépendantes et la table Cours
            # ATTENTION: S'assurer que c'est le comportement désiré (suppression totale avant import)
            cur.execute("DELETE FROM AttributionsCours;") # Supprimer d'abord les attributions
            cur.execute("DELETE FROM Cours;")            # Puis les cours

            cours_importes_count = 0
            for cours_data in nouveaux_cours_a_importer:
                try:
                    cur.execute(
                        """INSERT INTO Cours (CodeCours, ChampNo, CoursDescriptif, NbPeriodes, NbGroupeInitial, EstCoursAutre)
                           VALUES (%(codecours)s, %(champno)s, %(coursdescriptif)s, %(nbperiodes)s, %(nbgroupeinitial)s, %(estcoursautre)s);""",
                        cours_data,
                    )
                    cours_importes_count += 1
                except psycopg2.Error as e_insert: # Gérer les erreurs d'insertion (ex: ChampNo inexistant)
                    db.rollback() # Annuler toute la transaction
                    err_details = e_insert.pgerror if hasattr(e_insert, "pgerror") else str(e_insert)
                    code_prob = cours_data.get("codecours", "INCONNU")
                    err_msg = (f"Erreur lors de l'insertion du cours '{code_prob}' (ChampNo: {cours_data.get('champno')}): {err_details}. "
                               "L'importation des cours a été annulée. Aucune donnée n'a été modifiée.")
                    flash(err_msg, "error")
                    app.logger.error(err_msg)
                    return redirect(url_for("page_administration_donnees"))
            db.commit() # Valider la transaction si tout s'est bien passé
            msg_succes = (f"{cours_importes_count} cours ont été importés avec succès. "
                          "Les anciens cours et toutes les attributions existantes ont été supprimés.")
            flash(msg_succes, "success")

    except InvalidFileException:
        flash("Le fichier Excel des cours fourni est invalide ou corrompu.", "error")
    except AssertionError as ae: # Levée par `isinstance(sheet, Worksheet)` par exemple
        flash(f"Erreur de format ou de structure dans le fichier Excel des cours: {ae}", "error")
        app.logger.error(f"Erreur d'assertion lors de l'importation des cours: {ae}")
    except Exception as e:  # pylint: disable=broad-except # Capturer toute autre exception
        if db and not db.closed and not db.autocommit: # Rollback si une transaction était en cours
            db.rollback()
        app.logger.error(f"Erreur inattendue lors de l'importation des cours: {type(e).__name__} - {e}")
        msg_err_inatt = f"Une erreur inattendue est survenue lors de l'importation des cours: {type(e).__name__}. L'opération a été annulée."
        flash(msg_err_inatt, "error")
    return redirect(url_for("page_administration_donnees"))


@app.route("/administration/importer_enseignants_excel", methods=["POST"])
def api_importer_enseignants_excel():
    """Importe les enseignants depuis un fichier Excel."""
    db = get_db()
    if not db:
        flash("Erreur de connexion à la base de données. Importation des enseignants annulée.", "error")
        return redirect(url_for("page_administration_donnees"))

    if "fichier_enseignants" not in request.files:
        flash("Aucun fichier sélectionné pour l'importation des enseignants.", "warning")
        return redirect(url_for("page_administration_donnees"))

    file = request.files["fichier_enseignants"]
    if not file or not file.filename:
        flash("Nom de fichier vide pour l'importation des enseignants.", "warning")
        return redirect(url_for("page_administration_donnees"))

    if not allowed_file(file.filename):
        flash("Type de fichier non autorisé pour les enseignants. Seuls les fichiers .xlsx sont acceptés.", "error")
        return redirect(url_for("page_administration_donnees"))

    nouveaux_enseignants_a_importer = []
    try:
        workbook = openpyxl.load_workbook(file.stream)
        sheet = workbook.active
        if not isinstance(sheet, Worksheet):
            flash("La feuille active du fichier Excel des enseignants est invalide.", "error")
            return redirect(url_for("page_administration_donnees"))

        iter_rows = iter(sheet.rows)
        try:
            next(iter_rows)  # Ignorer la ligne d'en-tête
        except StopIteration:
            flash("Le fichier Excel des enseignants est vide ou ne contient que l'en-tête.", "warning")
            return redirect(url_for("page_administration_donnees"))

        lignes_ignorees_compt = 0
        for row_idx, row in enumerate(iter_rows, start=2):
            try:
                champ_no_raw = row[0].value
                nom_raw = row[1].value
                prenom_raw = row[2].value
                temps_plein_raw = row[3].value
                # peut_choisir_hors_champ_raw = row[4].value # Si cette colonne existe

                champ_no = str(champ_no_raw).strip() if champ_no_raw is not None else None
                nom = str(nom_raw).strip() if nom_raw is not None else None
                prenom = str(prenom_raw).strip() if prenom_raw is not None else None

                if not all([champ_no, nom, prenom]):
                    flash(f"Ligne {row_idx} (Enseignants): Données essentielles (ChampNo, Nom, Prénom) manquantes. Ligne ignorée.", "warning")
                    lignes_ignorees_compt +=1
                    continue

                nom_complet = f"{prenom} {nom}"

                # Conversion du booléen 'EstTempsPlein'
                est_temps_plein = True # Valeur par défaut si non spécifié ou malformé
                if isinstance(temps_plein_raw, bool):
                    est_temps_plein = temps_plein_raw
                elif isinstance(temps_plein_raw, str):
                    val_str_upper = temps_plein_raw.strip().upper()
                    if val_str_upper in ("VRAI", "TRUE", "1", "OUI", "YES"):
                        est_temps_plein = True
                    elif val_str_upper in ("FAUX", "FALSE", "0", "NON", "NO", ""):
                        est_temps_plein = False
                    else: # Valeur inattendue, on garde la valeur par défaut True et on avertit
                        flash(f"Ligne {row_idx} (Ens): Valeur inattendue pour 'Temps Plein' ('{temps_plein_raw}'). Assumée VRAI.", "warning")
                elif temps_plein_raw is None: # Si la cellule est vide, on considère VRAI par défaut
                    est_temps_plein = True
                else: # Si c'est un nombre autre que 0/1 par exemple
                    flash(f"Ligne {row_idx} (Ens): Valeur inattendue pour 'Temps Plein' ('{temps_plein_raw}'). Assumée VRAI.", "warning")

                # Pour 'PeutChoisirHorsChampPrincipal', si cette colonne est ajoutée à l'Excel
                # peut_choisir = False # Valeur par défaut
                # if isinstance(peut_choisir_hors_champ_raw, bool):
                # peut_choisir = peut_choisir_hors_champ_raw
                # ... (logique similaire à EstTempsPlein)

                nouveaux_enseignants_a_importer.append({
                    "nomcomplet": nom_complet,
                    "champno": champ_no,
                    "esttempsplein": est_temps_plein,
                    "estfictif": False,  # Les enseignants importés ne sont jamais fictifs
                    "peutchoisirhorschampprincipal": False, # Valeur par défaut, à ajuster si colonne Excel existe
                })
            except IndexError:
                flash(f"Ligne {row_idx} (Enseignants): Nombre de colonnes insuffisant. La ligne est ignorée.", "warning")
                lignes_ignorees_compt +=1
                continue
            except (TypeError, ValueError) as te:
                flash(f"Ligne {row_idx} (Enseignants): Erreur de type de donnée ou de valeur. Ligne ignorée. Détails: {te}", "warning")
                lignes_ignorees_compt +=1
                continue

        if lignes_ignorees_compt > 0:
            flash(f"{lignes_ignorees_compt} ligne(s) du fichier enseignants ont été ignorée(s) en raison d'erreurs.", "info")

        if not nouveaux_enseignants_a_importer:
            flash("Aucun enseignant valide n'a été lu. Aucune modification apportée à la base de données.", "warning")
            return redirect(url_for("page_administration_donnees"))

        with db.cursor() as cur:
            # Vider les tables dépendantes et la table Enseignants
            # ATTENTION: Ceci supprime aussi tous les enseignants fictifs (tâches restantes)
            cur.execute("DELETE FROM AttributionsCours;")
            cur.execute("DELETE FROM Enseignants;")

            ens_importes_count = 0
            for ens_data in nouveaux_enseignants_a_importer:
                try:
                    cur.execute(
                        """INSERT INTO Enseignants (NomComplet, ChampNo, EstTempsPlein, EstFictif, PeutChoisirHorsChampPrincipal)
                           VALUES (%(nomcomplet)s, %(champno)s, %(esttempsplein)s, %(estfictif)s, %(peutchoisirhorschampprincipal)s);""",
                        ens_data,
                    )
                    ens_importes_count += 1
                except psycopg2.Error as e_insert:
                    db.rollback()
                    err_details = e_insert.pgerror if hasattr(e_insert, "pgerror") else str(e_insert)
                    nom_prob = ens_data.get("nomcomplet", "INCONNU")
                    err_msg = (f"Erreur lors de l'insertion de l'enseignant '{nom_prob}' (ChampNo: {ens_data.get('champno')}): {err_details}. "
                               "L'importation des enseignants a été annulée. Aucune donnée n'a été modifiée.")
                    flash(err_msg, "error")
                    app.logger.error(err_msg)
                    return redirect(url_for("page_administration_donnees"))
            db.commit()
            msg_succes = (f"{ens_importes_count} enseignants ont été importés avec succès. "
                          "Les anciens enseignants (y compris fictifs) et toutes les attributions existantes ont été supprimés.")
            flash(msg_succes, "success")

    except InvalidFileException:
        flash("Le fichier Excel des enseignants fourni est invalide ou corrompu.", "error")
    except AssertionError as ae:
        flash(f"Erreur de format ou de structure dans le fichier Excel des enseignants: {ae}", "error")
        app.logger.error(f"Erreur d'assertion lors de l'importation des enseignants: {ae}")
    except Exception as e:  # pylint: disable=broad-except
        if db and not db.closed and not db.autocommit:
            db.rollback()
        app.logger.error(f"Erreur inattendue lors de l'importation des enseignants: {type(e).__name__} - {e}")
        msg_err_inatt = f"Une erreur inattendue est survenue lors de l'importation des enseignants: {type(e).__name__}. L'opération a été annulée."
        flash(msg_err_inatt, "error")
    return redirect(url_for("page_administration_donnees"))


# --- Démarrage de l'application ---
if __name__ == "__main__":
    # Le port est configuré via la variable d'environnement PORT pour Cloud Run, Heroku, etc.
    # ou 8080 par défaut pour un développement local.
    port = int(os.environ.get("PORT", 8080))
    # debug=False est généralement recommandé pour la production.
    # Pour le développement, debug=True peut être activé via une variable d'environnement.
    debug_mode = os.environ.get("FLASK_DEBUG", "False").lower() == "true"
    app.run(host="0.0.0.0", port=port, debug=debug_mode)