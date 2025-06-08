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
# Clé secrète pour la session Flask, utilisée pour les messages flash et autres sécurités.
# Génère une clé aléatoire de 24 octets.
app.secret_key = os.urandom(24)
UPLOAD_FOLDER = "uploads"
ALLOWED_EXTENSIONS = {"xlsx"}  # Extensions de fichiers autorisées pour l'importation
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# Crée le répertoire d'upload s'il n'existe pas déjà
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# --- Configuration de la base de données ---
# Récupération des informations de connexion à la base de données depuis les variables d'environnement.
# Permet une configuration flexible sans exposer les identifiants directement dans le code.
DB_HOST = os.environ.get("PGHOST")
DB_NAME = os.environ.get("PGDATABASE")
DB_USER = os.environ.get("PGUSER")
DB_PASS = os.environ.get("PGPASSWORD")
# Le port par défaut est 5432 si non spécifié dans les variables d'environnement.
DB_PORT = os.environ.get("PGPORT", "5432")


def get_db_connection_string():
    """Construit la chaîne de connexion à la base de données en utilisant les variables d'environnement."""
    return f"dbname='{DB_NAME}' user='{DB_USER}' host='{DB_HOST}' password='{DB_PASS}' port='{DB_PORT}'"


def get_db():
    """
    Ouvre une nouvelle connexion à la base de données si ce n'est pas déjà fait pour la requête actuelle.
    La connexion est stockée dans l'objet 'g' de Flask pour être réutilisée durant le cycle de requête.
    """
    if "db" not in g:
        try:
            conn_string = get_db_connection_string()
            g.db = psycopg2.connect(conn_string)
        except psycopg2.Error as e:
            # Enregistre l'erreur de connexion et marque g.db comme None pour signaler l'échec.
            app.logger.error(f"Erreur de connexion à la base de données: {e}")
            g.db = None
    return g.db


@app.teardown_appcontext
def close_db(_exception=None):
    """
    Ferme la connexion à la base de données à la fin de la requête Flask.
    Cette fonction est automatiquement appelée par Flask.
    """
    db = g.pop("db", None)  # Récupère la connexion de 'g' et la supprime.
    if db is not None and not db.closed:
        try:
            db.close()  # Tente de fermer la connexion.
        except psycopg2.Error as e:
            # Enregistre les erreurs lors de la fermeture de la connexion.
            app.logger.error(f"Erreur lors de la fermeture de la connexion DB: {e}")


# --- Fonctions d'accès aux données (DAO - Data Access Object) ---

def get_all_champs():
    """
    Récupère tous les champs depuis la base de données, y compris leur statut de verrouillage.
    Les champs sont triés par numéro de champ.
    Retourne une liste de dictionnaires, chaque dictionnaire représentant un champ.
    """
    db = get_db()
    if not db:
        return []
    try:
        with db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT ChampNo, ChampNom, EstVerrouille FROM Champs ORDER BY ChampNo;")
            return [dict(row) for row in cur.fetchall()]
    except psycopg2.Error as e:
        app.logger.error(f"Erreur DAO get_all_champs: {e}")
        # En cas d'erreur, annule toute transaction en cours sur la connexion.
        if db and not db.closed:
            db.rollback()
        return []


def get_champ_details(champ_no):
    """
    Récupère les détails d'un champ spécifique par son numéro, y compris son statut de verrouillage.
    Retourne un dictionnaire représentant le champ, ou None si non trouvé.
    """
    db = get_db()
    if not db:
        return None
    try:
        with db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT ChampNo, ChampNom, EstVerrouille FROM Champs WHERE ChampNo = %s;", (champ_no,))
            champ_row = cur.fetchone()
        return dict(champ_row) if champ_row else None
    except psycopg2.Error as e:
        app.logger.error(f"Erreur DAO get_champ_details pour {champ_no}: {e}")
        if db and not db.closed:
            db.rollback()
        return None


def get_enseignants_par_champ(champ_no):
    """
    Récupère les enseignants associés à un champ spécifique.
    Les enseignants sont triés par statut fictif (les fictifs après les réels),
    puis par nom de famille, puis par prénom.
    Retourne une liste de dictionnaires.
    """
    db = get_db()
    if not db:
        return []
    try:
        with db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """
                SELECT EnseignantID, NomComplet, Nom, Prenom, EstTempsPlein, EstFictif, PeutChoisirHorsChampPrincipal
                FROM Enseignants WHERE ChampNo = %s ORDER BY EstFictif, Nom, Prenom;
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
    Récupère tous les enseignants de la base de données avec des détails enrichis :
    informations sur leur champ (y compris le verrouillage), leurs périodes de cours et autres.
    Les enseignants sont triés par numéro de champ, puis par statut fictif, puis par nom et prénom.
    Cette fonction est optimisée pour récupérer toutes les attributions en une seule requête.
    """
    db = get_db()
    if not db:
        return []
    enseignants_complets = []
    try:
        with db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """
                SELECT e.EnseignantID, e.NomComplet, e.Nom, e.Prenom, e.EstTempsPlein, e.EstFictif,
                       e.ChampNo, ch.ChampNom, e.PeutChoisirHorsChampPrincipal, ch.EstVerrouille
                FROM Enseignants e JOIN Champs ch ON e.ChampNo = ch.ChampNo
                ORDER BY e.ChampNo, e.EstFictif, e.Nom, e.Prenom;
                """
            )
            enseignants_bruts = [dict(row) for row in cur.fetchall()]

        # Récupération optimisée de toutes les attributions de cours en une seule fois pour réduire les requêtes DB.
        toutes_les_attributions = get_toutes_les_attributions()
        attributions_par_enseignant = {}
        # Regroupe les attributions par enseignant ID pour un accès rapide.
        for attr in toutes_les_attributions:
            attributions_par_enseignant.setdefault(attr["enseignantid"], []).append(attr)

        # Jointure "virtuelle" des attributions et calcul des périodes pour chaque enseignant.
        for ens_brut in enseignants_bruts:
            attributions_de_l_enseignant = attributions_par_enseignant.get(ens_brut["enseignantid"], [])
            periodes = calculer_periodes_pour_attributions(attributions_de_l_enseignant)
            # Détermine si l'enseignant doit être compté pour la moyenne du champ (temps plein et non fictif).
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
    """
    Récupère les cours disponibles pour un champ donné, en calculant les groupes restants.
    Retourne une liste de dictionnaires, triés par type de cours (autre ou non) puis par code de cours.
    """
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
    """
    Récupère toutes les attributions de cours pour un enseignant spécifique.
    Inclut les détails du cours (descriptif, périodes, type, champ d'origine).
    Retourne une liste de dictionnaires.
    """
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


def get_toutes_les_attributions():
    """
    Récupère toutes les attributions de cours pour tous les enseignants en une seule requête.
    Cette fonction est utilisée pour optimiser les performances en évitant de multiples requêtes
    lors du calcul des totaux pour tous les enseignants.
    """
    db = get_db()
    if not db:
        return []
    try:
        with db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """
                SELECT ac.AttributionID, ac.EnseignantID, ac.CodeCours, ac.NbGroupesPris,
                       c.CoursDescriptif, c.NbPeriodes, c.EstCoursAutre
                FROM AttributionsCours ac JOIN Cours c ON ac.CodeCours = c.CodeCours
                ORDER BY ac.EnseignantID, c.EstCoursAutre, c.CoursDescriptif;
                """
            )
            return [dict(a) for a in cur.fetchall()]
    except psycopg2.Error as e:
        app.logger.error(f"Erreur DAO get_toutes_les_attributions: {e}")
        if db and not db.closed:
            db.rollback()
        return []


def calculer_periodes_pour_attributions(attributions):
    """
    Calcule le total des périodes de cours (enseignement) et des périodes d'autres tâches
    à partir d'une liste d'attributions fournie.
    Cette fonction est générique et peut être utilisée avec des listes d'attributions déjà chargées en mémoire.
    """
    periodes_enseignement = sum(a["nbperiodes"] * a["nbgroupespris"] for a in attributions if not a["estcoursautre"])
    periodes_autres = sum(a["nbperiodes"] * a["nbgroupespris"] for a in attributions if a["estcoursautre"])
    return {
        "periodes_cours": periodes_enseignement,
        "periodes_autres": periodes_autres,
        "total_periodes": periodes_enseignement + periodes_autres,
    }


def calculer_periodes_enseignant(enseignant_id):
    """
    Calcule le total des périodes de cours et d'autres tâches pour un enseignant spécifique
    en interrogeant la base de données pour ses attributions.
    """
    attributions = get_attributions_enseignant(enseignant_id)
    return calculer_periodes_pour_attributions(attributions)


def get_groupes_restants_pour_cours(code_cours):
    """
    Calcule le nombre de groupes restants pour un cours spécifique.
    Prend en compte le nombre initial de groupes et le nombre de groupes déjà attribués.
    """
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
        # Si le cours n'a aucune attribution, la requête GROUP BY peut retourner NULL.
        # Dans ce cas, nous devons récupérer le nombre initial de groupes directement depuis la table Cours.
        initial_groups_if_no_attributions_query = "SELECT NbGroupeInitial FROM Cours WHERE CodeCours = %s;"
        if result is None or result["grprestant"] is None:
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
    """
    Récupère tous les cours disponibles dans la base de données avec les détails de leur champ d'origine.
    Trié par code de cours.
    """
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


def toggle_champ_lock_status(champ_no):
    """
    Bascule le statut de verrouillage (EstVerrouille) d'un champ spécifique.
    Retourne le nouveau statut de verrouillage (True si verrouillé, False si déverrouillé)
    ou None en cas d'erreur.
    """
    db = get_db()
    if not db:
        return None
    try:
        with db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("UPDATE Champs SET EstVerrouille = NOT EstVerrouille WHERE ChampNo = %s RETURNING EstVerrouille;", (champ_no,))
            result = cur.fetchone()
            db.commit()  # Valide la modification dans la base de données.
            return result["estverrouille"] if result else None
    except psycopg2.Error as e:
        if db and not db.closed:
            db.rollback()  # Annule la transaction en cas d'erreur.
        app.logger.error(f"Erreur DAO toggle_champ_lock_status pour {champ_no}: {e}")
        return None


# --- ROUTES DE L'APPLICATION (Pages HTML) ---
@app.route("/")
def index():
    """
    Affiche la page d'accueil de l'application.
    Charge la liste de tous les champs et l'année courante pour l'affichage.
    """
    champs = get_all_champs()
    current_year = datetime.datetime.now().year
    return render_template("index.html", champs=champs, SCRIPT_YEAR=current_year)


@app.route("/champ/<string:champ_no>")
def page_champ(champ_no):
    """
    Affiche la page détaillée d'un champ spécifique, incluant la liste des enseignants
    de ce champ, leurs attributions de cours, les cours disponibles et un sommaire local.
    """
    champ_details = get_champ_details(champ_no)
    if not champ_details:
        flash(f"Le champ {champ_no} n'a pas été trouvé.", "error")
        return redirect(url_for("index"))

    # Récupération de toutes les données nécessaires en un minimum de requêtes pour optimiser.
    enseignants_du_champ = get_enseignants_par_champ(champ_no)
    cours_disponibles_bruts = get_cours_disponibles_par_champ(champ_no)

    # Récupération optimisée de toutes les attributions pour tous les enseignants,
    # puis filtrage pour ceux du champ actuel.
    ids_enseignants = [e["enseignantid"] for e in enseignants_du_champ]
    toutes_les_attributions = get_toutes_les_attributions()
    attributions_par_enseignant = {}
    for attr in toutes_les_attributions:
        if attr["enseignantid"] in ids_enseignants:
            attributions_par_enseignant.setdefault(attr["enseignantid"], []).append(attr)

    # Construction de la structure de données complète pour les enseignants du champ.
    enseignants_complets = []
    total_periodes_tp_pour_moyenne = 0
    nb_enseignants_tp_pour_moyenne = 0

    for ens in enseignants_du_champ:
        enseignant_id = ens["enseignantid"]
        attributions_de_l_enseignant = attributions_par_enseignant.get(enseignant_id, [])
        periodes = calculer_periodes_pour_attributions(attributions_de_l_enseignant)

        enseignants_complets.append(
            {
                **ens,  # Inclut Nom, Prenom, NomComplet, etc.
                "attributions": attributions_de_l_enseignant,
                "periodes_actuelles": periodes,
            }
        )

        # Calcul pour la moyenne du champ (seulement les enseignants temps plein non fictifs).
        if ens["esttempsplein"] and not ens["estfictif"]:
            total_periodes_tp_pour_moyenne += periodes["total_periodes"]
            nb_enseignants_tp_pour_moyenne += 1

    # Calcul de la moyenne du champ.
    moyenne_champ = (total_periodes_tp_pour_moyenne / nb_enseignants_tp_pour_moyenne) if nb_enseignants_tp_pour_moyenne > 0 else 0

    # Séparation des cours par catégorie pour l'affichage dans les listes de sélection.
    cours_enseignement_champ = [c for c in cours_disponibles_bruts if not c["estcoursautre"]]
    cours_autres_taches_champ = [c for c in cours_disponibles_bruts if c["estcoursautre"]]

    current_year = datetime.datetime.now().year

    return render_template(
        "page_champ.html",
        champ=champ_details,
        enseignants_data=enseignants_complets,
        cours_enseignement_champ=cours_enseignement_champ,
        cours_autres_taches_champ=cours_autres_taches_champ,
        # 'cours_disponibles_pour_tableau_restant' n'est plus utilisé directement ici car le JS prend les G_COURS_...
        moyenne_champ_initiale=moyenne_champ,
        SCRIPT_YEAR=current_year,
    )


@app.route("/sommaire")
def page_sommaire():
    """
    Affiche la page du sommaire global des tâches des enseignants.
    Calcule et présente les moyennes par champ et la moyenne générale.
    """
    enseignants_par_champ_data, moyennes_champs, moyenne_gen = calculer_donnees_sommaire()
    current_year = datetime.datetime.now().year
    return render_template(
        "page_sommaire.html",
        enseignants_par_champ=enseignants_par_champ_data,
        moyennes_par_champ=moyennes_champs,
        moyenne_generale=moyenne_gen,
        SCRIPT_YEAR=current_year,
    )


@app.route("/administration")
def page_administration_donnees():
    """
    Affiche la page d'administration où les utilisateurs peuvent importer des données
    (enseignants, cours) via Excel et réassigner des cours entre champs.
    """
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
    Calcule les données agrégées nécessaires pour la page sommaire globale.
    Regroupe les enseignants par champ, calcule les totaux de périodes pour chaque champ,
    les moyennes par champ (pour les enseignants temps plein non fictifs),
    et la moyenne générale de l'établissement.
    """
    # Récupère tous les enseignants avec leurs détails déjà calculés (y compris les périodes).
    # Ils sont déjà triés par champ, puis par statut fictif, puis nom/prénom.
    tous_enseignants_details = get_all_enseignants_avec_details()
    enseignants_par_champ_temp = {}
    moyennes_par_champ_calculees = {}
    total_periodes_global_tp = 0
    nb_enseignants_tp_global = 0

    for ens in tous_enseignants_details:
        champ_no = ens["champno"]
        champ_nom = ens["champnom"]
        est_verrouille = ens["estverrouille"]

        # Initialise la structure pour le champ si elle n'existe pas.
        if champ_no not in enseignants_par_champ_temp:
            enseignants_par_champ_temp[champ_no] = {
                "champno": champ_no,
                "champnom": champ_nom,
                "enseignants": [],
                "total_periodes_cours_champ": 0,
                "total_periodes_autres_champ": 0,
                "total_periodes_champ": 0,
            }

        # Ajoute l'enseignant aux données de son champ et met à jour les totaux du champ.
        enseignants_par_champ_temp[champ_no]["enseignants"].append(ens)
        enseignants_par_champ_temp[champ_no]["total_periodes_cours_champ"] += ens["periodes_cours"]
        enseignants_par_champ_temp[champ_no]["total_periodes_autres_champ"] += ens["periodes_autres"]
        enseignants_par_champ_temp[champ_no]["total_periodes_champ"] += ens["total_periodes"]

        # Si l'enseignant compte pour la moyenne (temps plein et non fictif), met à jour les agrégats.
        if ens["compte_pour_moyenne_champ"]:
            if champ_no not in moyennes_par_champ_calculees:
                moyennes_par_champ_calculees[champ_no] = {
                    "champ_nom": champ_nom,
                    "total_periodes": 0,
                    "nb_enseignants": 0,
                    "moyenne": 0.0,  # Valeur initiale
                    "est_verrouille": est_verrouille,
                }
            moyennes_par_champ_calculees[champ_no]["total_periodes"] += ens["total_periodes"]
            moyennes_par_champ_calculees[champ_no]["nb_enseignants"] += 1

            total_periodes_global_tp += ens["total_periodes"]
            nb_enseignants_tp_global += 1

    # Calcule les moyennes individuelles par champ.
    for data_champ in moyennes_par_champ_calculees.values():
        if data_champ["nb_enseignants"] > 0:
            data_champ["moyenne"] = data_champ["total_periodes"] / data_champ["nb_enseignants"]
        # Supprime les clés intermédiaires non nécessaires pour l'affichage final.
        del data_champ["total_periodes"]
        del data_champ["nb_enseignants"]

    # Calcule la moyenne générale de l'établissement.
    moyenne_generale_calculee = (total_periodes_global_tp / nb_enseignants_tp_global) if nb_enseignants_tp_global > 0 else 0
    # Convertit le dictionnaire temporaire en une liste pour le retour.
    enseignants_par_champ_final = list(enseignants_par_champ_temp.values())

    return enseignants_par_champ_final, moyennes_par_champ_calculees, moyenne_generale_calculee


# --- API ENDPOINTS ---
@app.route("/api/sommaire/donnees", methods=["GET"])
def api_get_donnees_sommaire():
    """
    API pour récupérer les données actualisées du sommaire global de l'établissement.
    Utilisée par JavaScript pour rafraîchir dynamiquement la page sommaire.
    """
    enseignants_groupes, moyennes_champs, moyenne_gen = calculer_donnees_sommaire()
    return jsonify(
        {
            "enseignants_par_champ": enseignants_groupes,
            "moyennes_par_champ": moyennes_champs,
            "moyenne_generale": moyenne_gen,
        }
    )


@app.route("/api/attributions/ajouter", methods=["POST"])
def api_ajouter_attribution():
    """
    API pour ajouter une attribution de cours à un enseignant.
    Vérifie les groupes disponibles et le statut de verrouillage du champ avant d'ajouter.
    Retourne les périodes mises à jour de l'enseignant et les groupes restants du cours.
    """
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
            # Vérifier le statut de verrouillage du champ de l'enseignant avant toute modification.
            # Les enseignants fictifs (tâches restantes) sont exemptés du verrouillage.
            query_verrou = """
                SELECT e.EstFictif, ch.EstVerrouille
                FROM Enseignants e JOIN Champs ch ON e.ChampNo = ch.ChampNo
                WHERE e.EnseignantID = %s;
            """
            cur.execute(query_verrou, (enseignant_id,))
            verrou_info = cur.fetchone()

            if verrou_info and verrou_info["estverrouille"] and not verrou_info["estfictif"]:
                msg = (
                    "Impossible d'attribuer un cours, le champ est verrouillé. "
                    "Seules les tâches restantes peuvent être modifiées."
                )
                return jsonify({"success": False, "message": msg}), 403

            # Vérifier les groupes disponibles pour le cours avant l'insertion.
            query_grp_dispo = """
                SELECT (c.NbGroupeInitial - COALESCE(SUM(ac.NbGroupesPris), 0)) AS grp_dispo
                FROM Cours c
                LEFT JOIN AttributionsCours ac ON c.CodeCours = ac.CodeCours AND c.CodeCours = %s
                WHERE c.CodeCours = %s
                GROUP BY c.NbGroupeInitial;
            """
            cur.execute(query_grp_dispo, (code_cours, code_cours))
            cours_info = cur.fetchone()

            groupes_disponibles_actuels = 0
            if cours_info and cours_info["grp_dispo"] is not None:
                groupes_disponibles_actuels = cours_info["grp_dispo"]
            else:
                # Si le cours n'a aucune attribution ou la requête ne renvoie rien,
                # on récupère directement le nombre initial de groupes du cours.
                cur.execute("SELECT NbGroupeInitial FROM Cours WHERE CodeCours = %s", (code_cours,))
                initial_groups_info = cur.fetchone()
                if initial_groups_info:
                    groupes_disponibles_actuels = initial_groups_info["nbgroupeinitial"]
                else:
                    return jsonify({"success": False, "message": "Cours non trouvé."}), 404

            if groupes_disponibles_actuels < 1:
                return jsonify({"success": False, "message": "Plus de groupes disponibles pour ce cours."}), 409

            # Insère la nouvelle attribution (toujours 1 groupe à la fois).
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

            # Récupère les informations de l'enseignant pour les inclure dans la réponse API.
            cur.execute(
                "SELECT ChampNo, EstTempsPlein, EstFictif, Nom, Prenom FROM Enseignants WHERE EnseignantID = %s", (enseignant_id,)
            )
            resultat_enseignant = cur.fetchone()
            if resultat_enseignant:
                infos_enseignant_pour_reponse = dict(resultat_enseignant)
            db.commit()  # Valide la transaction.

        try:
            # Recalcule les périodes de l'enseignant et les groupes restants du cours après l'attribution.
            periodes_enseignant_maj = calculer_periodes_enseignant(enseignant_id)
            groupes_restants_cours_maj = get_groupes_restants_pour_cours(code_cours)
            attributions_enseignant_maj = get_attributions_enseignant(enseignant_id)
        except Exception as e_calcul:  # pylint: disable=broad-except
            # Gère les erreurs lors des calculs post-attribution sans annuler l'attribution elle-même.
            msg = f"Erreur post-attribution (calculs) pour ens {enseignant_id}, cours {code_cours}: {e_calcul}"
            app.logger.error(msg)
            message_succes_partiel = "Cours attribué, mais erreur lors de la mise à jour des totaux."
            return (
                jsonify(
                    {
                        "success": True,
                        "message": message_succes_partiel,
                        "attribution_id": nouvelle_attribution_id,
                        "enseignant_id": enseignant_id,
                        "code_cours": code_cours,
                        "periodes_enseignant": {},  # Indique que les calculs n'ont pas pu être faits.
                        "groupes_restants_cours": -1,  # Indique une valeur inconnue.
                        "attributions_enseignant": [],
                        **infos_enseignant_pour_reponse,
                    }
                ),
                201,  # Statut 201 Created pour une attribution réussie.
            )

        # Retourne une réponse de succès avec les données mises à jour.
        return (
            jsonify(
                {
                    "success": True,
                    "message": "Cours attribué avec succès!",
                    "attribution_id": nouvelle_attribution_id,
                    "enseignant_id": enseignant_id,
                    "code_cours": code_cours,
                    "periodes_enseignant": periodes_enseignant_maj,
                    "groupes_restants_cours": groupes_restants_cours_maj,
                    "attributions_enseignant": attributions_enseignant_maj,
                    **infos_enseignant_pour_reponse,
                }
            ),
            201,
        )

    except psycopg2.Error as e_psy:
        # Gère les erreurs spécifiques à PostgreSQL.
        if db and not db.closed:
            db.rollback()
        app.logger.error(f"Erreur psycopg2 API ajouter attribution: {e_psy}")
        return jsonify({"success": False, "message": "Erreur de base de données lors de l'ajout de l'attribution."}), 500
    except Exception as e_gen:  # pylint: disable=broad-except
        # Gère toutes les autres exceptions inattendues.
        if db and not db.closed:
            db.rollback()
        app.logger.error(f"Erreur générale Exception API ajouter attribution: {e_gen}")
        return jsonify({"success": False, "message": "Erreur serveur inattendue lors de l'ajout de l'attribution."}), 500


@app.route("/api/attributions/supprimer", methods=["POST"])
def api_supprimer_attribution():
    """
    API pour supprimer une attribution de cours spécifique.
    Vérifie le statut de verrouillage du champ et recalcule les totaux après suppression.
    """
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
            # Récupérer les informations de l'attribution avant suppression et vérifier le verrouillage.
            query_select_attribution = """
                SELECT ac.EnseignantID, ac.CodeCours, c.NbPeriodes AS PeriodesDuCours, ac.NbGroupesPris,
                       e.EstFictif, ch.EstVerrouille
                FROM AttributionsCours ac
                JOIN Cours c ON ac.CodeCours = c.CodeCours
                JOIN Enseignants e ON ac.EnseignantID = e.EnseignantID
                JOIN Champs ch ON e.ChampNo = ch.ChampNo
                WHERE ac.AttributionID = %s;
            """
            cur.execute(query_select_attribution, (attribution_id_a_supprimer,))
            attribution_info = cur.fetchone()
            if not attribution_info:
                return jsonify({"success": False, "message": "Attribution non trouvée."}), 404

            # Refuse la suppression si le champ est verrouillé et l'enseignant n'est pas fictif.
            if attribution_info["estverrouille"] and not attribution_info["estfictif"]:
                msg = (
                    "Impossible de retirer ce cours, le champ est verrouillé. "
                    "Seules les tâches restantes peuvent être modifiées."
                )
                return jsonify({"success": False, "message": msg}), 403

            enseignant_id_concerne = attribution_info["enseignantid"]
            code_cours_concerne = attribution_info["codecours"]
            periodes_liberees_par_suppression = attribution_info.get("periodesducours", 0) * attribution_info.get("nbgroupespris", 0)

            # Supprime l'attribution.
            cur.execute("DELETE FROM AttributionsCours WHERE AttributionID = %s;", (attribution_id_a_supprimer,))
            if cur.rowcount == 0:
                db.rollback()
                return jsonify({"success": False, "message": "Attribution non trouvée ou déjà supprimée (concurrence?)."}), 404

            # Récupère les informations de l'enseignant pour la réponse.
            cur.execute(
                "SELECT ChampNo, EstTempsPlein, EstFictif, Nom, Prenom FROM Enseignants WHERE EnseignantID = %s",
                (enseignant_id_concerne,),
            )
            resultat_enseignant = cur.fetchone()
            if resultat_enseignant:
                infos_enseignant_pour_reponse = dict(resultat_enseignant)
            db.commit()

        try:
            # Recalcule les totaux après suppression.
            periodes_enseignant_maj = calculer_periodes_enseignant(enseignant_id_concerne)
            groupes_restants_cours_maj = get_groupes_restants_pour_cours(code_cours_concerne)
            attributions_enseignant_maj = get_attributions_enseignant(enseignant_id_concerne)
        except Exception as e_calcul:  # pylint: disable=broad-except
            msg = f"Erreur post-suppression (calculs) pour ens {enseignant_id_concerne}, cours {code_cours_concerne}: {e_calcul}"
            app.logger.error(msg)
            message_succes_partiel = "Attribution supprimée, mais erreur lors de la mise à jour des totaux."
            return (
                jsonify(
                    {
                        "success": True,
                        "message": message_succes_partiel,
                        "enseignant_id": enseignant_id_concerne,
                        "code_cours": code_cours_concerne,
                        "nb_periodes_cours_libere": periodes_liberees_par_suppression,
                        "periodes_enseignant": {},
                        "groupes_restants_cours": -1,
                        "attributions_enseignant": [],
                        **infos_enseignant_pour_reponse,
                    }
                ),
                200,
            )

        return (
            jsonify(
                {
                    "success": True,
                    "message": "Attribution supprimée avec succès!",
                    "enseignant_id": enseignant_id_concerne,
                    "code_cours": code_cours_concerne,
                    "periodes_enseignant": periodes_enseignant_maj,
                    "groupes_restants_cours": groupes_restants_cours_maj,
                    "attributions_enseignant": attributions_enseignant_maj,
                    "nb_periodes_cours_libere": periodes_liberees_par_suppression,
                    **infos_enseignant_pour_reponse,
                }
            ),
            200,
        )

    except psycopg2.Error as e_psy:
        if db and not db.closed:
            db.rollback()
        app.logger.error(f"Erreur psycopg2 API supprimer attribution: {e_psy}")
        # Gère l'erreur de clé étrangère (23503) si l'attribution est référencée ailleurs (improbable ici).
        if hasattr(e_psy, "pgcode") and e_psy.pgcode == "23503":
            return jsonify({"success": False, "message": "Suppression impossible car l'attribution est référencée ailleurs."}), 409
        return jsonify({"success": False, "message": "Erreur de base de données lors de la suppression de l'attribution."}), 500
    except Exception as e_gen:  # pylint: disable=broad-except
        if db and not db.closed:
            db.rollback()
        app.logger.error(f"Erreur générale Exception API supprimer attribution: {e_gen}")
        return jsonify({"success": False, "message": f"Erreur serveur inattendue lors de la suppression: {str(e_gen)}"}), 500


@app.route("/api/champs/<string:champ_no>/taches_restantes/creer", methods=["POST"])
def api_creer_tache_restante(champ_no):
    """
    API pour créer une nouvelle tâche restante (représentée par un enseignant fictif) dans un champ donné.
    Cette opération est permise même si le champ est verrouillé, car elle gère les "tâches" et non les enseignants réels.
    """
    db = get_db()
    if not db:
        return jsonify({"success": False, "message": "Erreur de connexion à la base de données."}), 500

    nouvel_enseignant_fictif_cree = {}
    # Les tâches restantes commencent avec 0 période.
    periodes_initiales_tache = {"periodes_cours": 0, "periodes_autres": 0, "total_periodes": 0}

    try:
        with db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            # Détermine le prochain numéro de tâche restante pour ce champ.
            query_select_taches_existantes = """
                SELECT NomComplet FROM Enseignants
                WHERE ChampNo = %s AND EstFictif = TRUE AND NomComplet LIKE %s;
            """
            # Le motif pour trouver les tâches restantes existantes (ex: "01-Tâche restante-X").
            pattern_nom_tache = f"{champ_no}-Tâche restante-%"
            cur.execute(query_select_taches_existantes, (champ_no, pattern_nom_tache))
            taches_existantes = cur.fetchall()

            max_numero_tache = 0
            for tache in taches_existantes:
                nom_tache_existante = tache["nomcomplet"]
                parts = nom_tache_existante.split("-")
                # Extrait le numéro à la fin du nom de la tâche.
                if len(parts) > 1:
                    num_part = parts[-1].strip()
                    if num_part.isdigit():
                        numero = int(num_part)
                        max_numero_tache = max(max_numero_tache, numero)

            # Construit le nom de la nouvelle tâche restante.
            nom_nouvelle_tache = f"{champ_no}-Tâche restante-{max_numero_tache + 1}"

            # Insère le nouvel enseignant fictif dans la base de données.
            query_insert_tache = """
                INSERT INTO Enseignants (NomComplet, Nom, Prenom, ChampNo, EstTempsPlein, EstFictif, PeutChoisirHorsChampPrincipal)
                VALUES (%s, NULL, NULL, %s, TRUE, TRUE, FALSE)
                RETURNING EnseignantID, NomComplet, Nom, Prenom, EstTempsPlein, EstFictif, PeutChoisirHorsChampPrincipal, ChampNo;
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

        return (
            jsonify(
                {
                    "success": True,
                    "message": "Tâche restante créée avec succès!",
                    "enseignant": {
                        **nouvel_enseignant_fictif_cree,  # Inclut Nom et Prenom (qui seront None pour les fictifs)
                        "attributions": [],  # Une nouvelle tâche n'a pas d'attributions initiales.
                    },
                    "periodes_actuelles": periodes_initiales_tache,
                }
            ),
            201,
        )

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
    """
    API pour supprimer un enseignant, principalement utilisée pour les tâches fictives.
    Vérifie les règles de verrouillage et s'assure de libérer les groupes de cours attribués.
    """
    db = get_db()
    if not db:
        return jsonify({"success": False, "message": "Erreur de connexion à la base de données."}), 500

    cours_liberes_apres_suppression = []
    try:
        with db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            # Récupère le statut fictif de l'enseignant et le statut de verrouillage de son champ.
            query_info_enseignant = """
                SELECT e.EstFictif, ch.EstVerrouille
                FROM Enseignants e JOIN Champs ch ON e.ChampNo = ch.ChampNo
                WHERE e.EnseignantID = %s;
            """
            cur.execute(query_info_enseignant, (enseignant_id,))
            enseignant_info = cur.fetchone()

            if not enseignant_info:
                return jsonify({"success": False, "message": "Enseignant non trouvé."}), 404

            # Règle de métier: on ne peut supprimer un enseignant non-fictif si son champ est verrouillé.
            if enseignant_info["estverrouille"] and not enseignant_info["estfictif"]:
                msg = "Impossible de supprimer un enseignant d'un champ verrouillé."
                return jsonify({"success": False, "message": msg}), 403

            # Récupère les cours affectés à cet enseignant avant de le supprimer,
            # car les attributions seront supprimées en cascade par la FK.
            query_cours_affectes_enseignant = """
                SELECT DISTINCT ac.CodeCours, c.NbPeriodes
                FROM AttributionsCours ac JOIN Cours c ON ac.CodeCours = c.CodeCours
                WHERE ac.EnseignantID = %s;
            """
            cur.execute(query_cours_affectes_enseignant, (enseignant_id,))
            cours_affectes_avant_suppression = cur.fetchall()

            # Supprime l'enseignant. La contrainte de clé étrangère ON DELETE CASCADE
            # sur AttributionsCours se chargera de supprimer toutes ses attributions associées.
            cur.execute("DELETE FROM Enseignants WHERE EnseignantID = %s;", (enseignant_id,))
            if cur.rowcount == 0:
                db.rollback()
                return jsonify({"success": False, "message": "L'enseignant n'a pas pu être supprimé (déjà supprimé?)."}), 404
            db.commit()

            # Après la suppression de l'enseignant et de ses attributions,
            # met à jour les groupes restants pour les cours qui ont été libérés.
            if cours_affectes_avant_suppression:
                codes_cours_uniques = list(set(c["codecours"] for c in cours_affectes_avant_suppression))
                for code_cours_unique in codes_cours_uniques:
                    groupes_restants_maj = get_groupes_restants_pour_cours(code_cours_unique)
                    # Récupère le nombre de périodes du cours pour le retour d'information.
                    nb_periodes = next((c["nbperiodes"] for c in cours_affectes_avant_suppression if c["codecours"] == code_cours_unique), 0)
                    cours_liberes_apres_suppression.append(
                        {
                            "code_cours": code_cours_unique,
                            "nouveaux_groupes_restants": groupes_restants_maj,
                            "nb_periodes": nb_periodes,
                        }
                    )
        return (
            jsonify(
                {
                    "success": True,
                    "message": "Enseignant et ses attributions supprimés avec succès. Groupes de cours mis à jour.",
                    "enseignant_id": enseignant_id,
                    "cours_liberes_details": cours_liberes_apres_suppression,
                }
            ),
            200,
        )

    except psycopg2.Error as e_psy:
        if db and not db.closed:
            db.rollback()
        if hasattr(e_psy, "pgcode") and e_psy.pgcode == "23503":
            # Erreur de clé étrangère : l'enseignant est référencé par une autre table qui n'est pas en cascade.
            msg_err_fk = f"Suppression de l'enseignant {enseignant_id} impossible car il est référencé dans d'autres tables."
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
    """
    API pour réassigner un cours à un nouveau champ.
    Vérifie l'existence du cours et du champ de destination, puis met à jour le champ du cours.
    """
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
            # Vérifie que le cours existe.
            cur.execute("SELECT ChampNo FROM Cours WHERE CodeCours = %s;", (code_cours_a_reassigner,))
            cours_actuel_info = cur.fetchone()
            if not cours_actuel_info:
                msg = f"Le cours {code_cours_a_reassigner} n'a pas été trouvé."
                return jsonify({"success": False, "message": msg}), 404

            # Vérifie que le champ de destination existe.
            cur.execute("SELECT ChampNom FROM Champs WHERE ChampNo = %s;", (nouveau_champ_no_destination,))
            champ_destination_info = cur.fetchone()
            if not champ_destination_info:
                msg = f"Le champ de destination {nouveau_champ_no_destination} n'a pas été trouvé."
                return jsonify({"success": False, "message": msg}), 404
            nom_nouveau_champ = champ_destination_info["champnom"]

            # Si le cours est déjà dans le champ de destination, ne fait rien et renvoie un message informatif.
            if str(cours_actuel_info["champno"]) == str(nouveau_champ_no_destination):
                message_deja_assigne = (
                    f"Le cours {code_cours_a_reassigner} est déjà assigné au champ "
                    f"{nouveau_champ_no_destination} ({nom_nouveau_champ}). Aucune action requise."
                )
                return (
                    jsonify(
                        {
                            "success": True,
                            "message": message_deja_assigne,
                            "code_cours": code_cours_a_reassigner,
                            "nouveau_champ_no": nouveau_champ_no_destination,
                            "nouveau_champ_nom": nom_nouveau_champ,
                        }
                    ),
                    200,
                )

            # Met à jour le champ du cours.
            cur.execute("UPDATE Cours SET ChampNo = %s WHERE CodeCours = %s;", (nouveau_champ_no_destination, code_cours_a_reassigner))
            if cur.rowcount == 0:
                db.rollback()
                msg = f"La mise à jour du ChampNo pour le cours {code_cours_a_reassigner} n'a affecté aucune ligne."
                app.logger.error(msg)
                return jsonify({"success": False, "message": "La mise à jour du champ du cours n'a pas eu d'effet."}), 500
            db.commit()

        return (
            jsonify(
                {
                    "success": True,
                    "message": (
                        f"Le cours {code_cours_a_reassigner} a été réassigné avec succès au champ {nouveau_champ_no_destination}"
                        f"({nom_nouveau_champ})."
                    ),
                    "code_cours": code_cours_a_reassigner,
                    "nouveau_champ_no": nouveau_champ_no_destination,
                    "nouveau_champ_nom": nom_nouveau_champ,
                }
            ),
            200,
        )

    except psycopg2.Error as e_psy:
        if db and not db.closed:
            db.rollback()
        app.logger.error(f"Erreur psycopg2 API réassigner champ cours: {e_psy}")
        if hasattr(e_psy, "pgcode") and e_psy.pgcode == "23503":
            # Erreur de clé étrangère si le champ de destination n'existe pas.
            msg = f"Réassignation impossible: le champ de destination '{nouveau_champ_no_destination}' n'existe pas ou problème de référence."
            return jsonify({"success": False, "message": msg}), 400
        return jsonify({"success": False, "message": "Erreur de base de données lors de la réassignation du champ du cours."}), 500
    except Exception as e_gen:  # pylint: disable=broad-except
        if db and not db.closed:
            db.rollback()
        app.logger.error(f"Erreur générale Exception API réassigner champ cours: {e_gen}")
        msg = f"Erreur serveur inattendue lors de la réassignation du champ du cours: {str(e_gen)}"
        return jsonify({"success": False, "message": msg}), 500


@app.route("/api/champs/<string:champ_no>/basculer_verrou", methods=["POST"])
def api_basculer_verrou_champ(champ_no):
    """
    API pour basculer le statut de verrouillage d'un champ.
    Utilisée sur la page de sommaire pour verrouiller/déverrouiller les champs.
    """
    db = get_db()
    if not db:
        return jsonify({"success": False, "message": "Erreur de connexion à la base de données."}), 500

    nouveau_statut = toggle_champ_lock_status(champ_no)
    if nouveau_statut is None:
        return jsonify({"success": False, "message": f"Impossible de modifier le verrou du champ {champ_no}."}), 500

    message = f"Le champ {champ_no} a été {'verrouillé' if nouveau_statut else 'déverrouillé'}."
    return jsonify({"success": True, "message": message, "est_verrouille": nouveau_statut}), 200


# --- Fonctions utilitaires et routes pour l'importation de données Excel ---
def allowed_file(filename):
    """Vérifie si l'extension du fichier est autorisée pour l'importation."""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route("/administration/importer_cours_excel", methods=["POST"])
def api_importer_cours_excel():
    """
    Importe les données des cours depuis un fichier Excel.
    Cette opération est destructive : elle supprime tous les cours et attributions existantes.
    """
    db = get_db()
    if not db:
        flash("Erreur de connexion à la base de données. Importation des cours annulée.", "error")
        return redirect(url_for("page_administration_donnees"))

    if "fichier_cours" not in request.files:
        flash("Aucun fichier sélectionné pour l'importation des cours.", "warning")
        return redirect(url_for("page_administration_donnees"))

    file = request.files["fichier_cours"]
    if not file or not file.filename:
        flash("Nom de fichier vide pour l'importation des cours.", "warning")
        return redirect(url_for("page_administration_donnees"))

    if not allowed_file(file.filename):
        flash("Type de fichier non autorisé pour les cours. Seuls les fichiers .xlsx sont acceptés.", "error")
        return redirect(url_for("page_administration_donnees"))

    nouveaux_cours_a_importer = []
    try:
        workbook = openpyxl.load_workbook(file.stream)
        sheet = workbook.active  # Récupère la feuille active du classeur.
        # Vérifie que la feuille est bien un objet Worksheet.
        if not isinstance(sheet, Worksheet):
            flash("La feuille active du fichier Excel des cours est invalide.", "error")
            return redirect(url_for("page_administration_donnees"))

        iter_rows = iter(sheet.rows)
        try:
            next(iter_rows)  # Ignorer la première ligne (en-tête de colonne).
        except StopIteration:
            flash("Le fichier Excel des cours est vide ou ne contient que l'en-tête.", "warning")
            return redirect(url_for("page_administration_donnees"))

        lignes_ignorees_compt = 0
        # Parcourt les lignes restantes du fichier Excel pour extraire les données des cours.
        for row_idx, row in enumerate(iter_rows, start=2):  # row_idx commence à 2 pour correspondre aux numéros de ligne Excel.
            try:
                # Lecture des valeurs des cellules en utilisant les indices de colonne (base 0).
                # Colonne A: ChampNo
                champ_no_raw = row[0].value
                # Colonne B: CodeCours
                code_cours_raw = row[1].value
                # Colonne D: CoursDescriptif (colonne C est "Grille", ignorée)
                cours_descriptif_raw = row[3].value
                # Colonne E: NbGroupeInitial
                nb_groupe_initial_raw = row[4].value
                # Colonne F: NbPeriodes
                nb_periodes_raw = row[5].value
                # Colonne H: EstCoursAutre (colonne G est "Total période", ignorée)
                est_cours_autre_raw = row[7].value

                # Nettoyage et conversion des données lues.
                champ_no = str(champ_no_raw).strip() if champ_no_raw is not None else None
                code_cours = str(code_cours_raw).strip() if code_cours_raw is not None else None
                cours_descriptif = str(cours_descriptif_raw).strip() if cours_descriptif_raw is not None else None

                # Validation des données essentielles.
                if not all([champ_no, code_cours, cours_descriptif]):
                    flash(f"Ligne {row_idx} (Cours): Données essentielles (ChampNo, CodeCours, Descriptif) manquantes. Ligne ignorée.", "warning")
                    lignes_ignorees_compt += 1
                    continue

                # Conversion de NbGroupeInitial en entier, avec validation.
                nb_groupe_initial = 0
                if isinstance(nb_groupe_initial_raw, int | float):
                    nb_groupe_initial = int(nb_groupe_initial_raw)
                elif isinstance(nb_groupe_initial_raw, str) and nb_groupe_initial_raw.strip().isdigit():
                    nb_groupe_initial = int(nb_groupe_initial_raw.strip())
                elif nb_groupe_initial_raw is not None:
                    flash(
                        f"Ligne {row_idx} (Cours): Valeur non numérique ou incorrecte pour 'Nb Groupes Prévus' ('{nb_groupe_initial_raw}'). "
                        "Ligne ignorée.",
                        "warning",
                    )
                    lignes_ignorees_compt += 1
                    continue

                # Conversion de NbPeriodes en entier, avec validation.
                nb_periodes = 0
                if isinstance(nb_periodes_raw, int | float):
                    nb_periodes = int(nb_periodes_raw)
                elif isinstance(nb_periodes_raw, str) and nb_periodes_raw.strip().isdigit():
                    nb_periodes = int(nb_periodes_raw.strip())
                elif nb_periodes_raw is not None:
                    flash(
                        f"Ligne {row_idx} (Cours): Valeur non numérique ou incorrecte pour 'Périodes/GR' ('{nb_periodes_raw}'). Ligne ignorée.",
                        "warning",
                    )
                    lignes_ignorees_compt += 1
                    continue

                # Conversion de EstCoursAutre en booléen, avec gestion des différents formats (VRAI/FAUX, TRUE/FALSE, 1/0, OUI/NON).
                est_cours_autre = False
                if isinstance(est_cours_autre_raw, bool):
                    est_cours_autre = est_cours_autre_raw
                elif isinstance(est_cours_autre_raw, str):
                    val_str_upper = est_cours_autre_raw.strip().upper()
                    if val_str_upper in ("VRAI", "TRUE", "1", "OUI", "YES"):
                        est_cours_autre = True
                    elif val_str_upper in ("FAUX", "FALSE", "0", "NON", "NO", ""):
                        est_cours_autre = False
                    else:
                        flash(f"Ligne {row_idx} (Cours): Valeur inattendue pour 'EstCoursAutre' ('{est_cours_autre_raw}'). Assumée FAUX.", "warning")
                elif est_cours_autre_raw is not None:
                    flash(f"Ligne {row_idx} (Cours): Valeur inattendue pour 'EstCoursAutre' ('{est_cours_autre_raw}'). Assumée FAUX.", "warning")

                # Ajoute les données du cours à la liste d'importation.
                nouveaux_cours_a_importer.append(
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
                flash(f"Ligne {row_idx} (Cours): Nombre de colonnes insuffisant. La ligne est ignorée.", "warning")
                lignes_ignorees_compt += 1
                continue
            except (TypeError, ValueError) as te:
                flash(f"Ligne {row_idx} (Cours): Erreur de type de donnée ou de valeur. Ligne ignorée. Détails: {te}", "warning")
                lignes_ignorees_compt += 1
                continue

        if lignes_ignorees_compt > 0:
            flash(f"{lignes_ignorees_compt} ligne(s) du fichier cours ont été ignorée(s) en raison d'erreurs.", "info")

        if not nouveaux_cours_a_importer:
            flash("Aucun cours valide n'a été lu depuis le fichier. Aucune modification n'a été apportée à la base de données.", "warning")
            return redirect(url_for("page_administration_donnees"))

        with db.cursor() as cur:
            # Supprime toutes les attributions et tous les cours existants avant l'importation.
            # C'est une opération d'écrasement.
            cur.execute("DELETE FROM AttributionsCours;")
            cur.execute("DELETE FROM Cours;")

            cours_importes_count = 0
            for cours_data in nouveaux_cours_a_importer:
                try:
                    cur.execute(
                        """INSERT INTO Cours (CodeCours, ChampNo, CoursDescriptif, NbPeriodes, NbGroupeInitial, EstCoursAutre)
                           VALUES (%(codecours)s, %(champno)s, %(coursdescriptif)s, %(nbperiodes)s, %(nbgroupeinitial)s, %(estcoursautre)s);""",
                        cours_data,
                    )
                    cours_importes_count += 1
                except psycopg2.Error as e_insert:
                    # En cas d'erreur lors de l'insertion d'un cours, annule toute la transaction.
                    db.rollback()
                    err_details = e_insert.pgerror if hasattr(e_insert, "pgerror") else str(e_insert)
                    code_prob = cours_data.get("codecours", "INCONNU")
                    err_msg = (
                        f"Erreur lors de l'insertion du cours '{code_prob}' (ChampNo: {cours_data.get('champno')}): {err_details}. "
                        "L'importation des cours a été annulée. Aucune donnée n'a été modifiée."
                    )
                    flash(err_msg, "error")
                    app.logger.error(err_msg)
                    return redirect(url_for("page_administration_donnees"))
            db.commit()  # Valide toutes les insertions si aucune erreur n'est survenue.
            msg_succes = (
                f"{cours_importes_count} cours ont été importés avec succès. "
                "Les anciens cours et toutes les attributions existantes ont été supprimés."
            )
            flash(msg_succes, "success")

    except InvalidFileException:
        flash("Le fichier Excel des cours fourni est invalide ou corrompu.", "error")
    except AssertionError as ae:
        # Erreur potentielle si openpyxl ne renvoie pas un Worksheet, ou autre assertion.
        flash(f"Erreur de format ou de structure dans le fichier Excel des cours: {ae}", "error")
        app.logger.error(f"Erreur d'assertion lors de l'importation des cours: {ae}")
    except Exception as e:  # pylint: disable=broad-except
        # Gère toute autre exception inattendue et assure un rollback si une transaction est active.
        if db and not db.closed and not db.autocommit:
            db.rollback()
        app.logger.error(f"Erreur inattendue lors de l'importation des cours: {type(e).__name__} - {e}")
        msg_err_inatt = f"Une erreur inattendue est survenue lors de l'importation des cours: {type(e).__name__}. L'opération a été annulée."
        flash(msg_err_inatt, "error")
    return redirect(url_for("page_administration_donnees"))


@app.route("/administration/importer_enseignants_excel", methods=["POST"])
def api_importer_enseignants_excel():
    """
    Importe les données des enseignants depuis un fichier Excel.
    Cette opération est destructive : elle supprime tous les enseignants et attributions existantes.
    Les noms et prénoms sont séparés, et le NomComplet est généré à partir de ces champs.
    """
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
            next(iter_rows)  # Ignorer la première ligne (en-tête de colonne).
        except StopIteration:
            flash("Le fichier Excel des enseignants est vide ou ne contient que l'en-tête.", "warning")
            return redirect(url_for("page_administration_donnees"))

        lignes_ignorees_compt = 0
        # Parcourt les lignes restantes du fichier Excel pour extraire les données des enseignants.
        for row_idx, row in enumerate(iter_rows, start=2):
            try:
                # Lecture des valeurs des cellules en utilisant les indices de colonne (base 0).
                # Correction ici pour correspondre à votre structure Excel:
                # Colonne A: ChampNo
                champ_no_raw = row[0].value
                # Colonne C: NOM (Nom de famille)
                nom_famille_raw = row[2].value
                # Colonne D: PRÉNOM
                prenom_raw = row[3].value
                # Colonnes E: Temps plein
                temps_plein_raw = row[4].value

                # Nettoyage et conversion des données lues.
                champ_no = str(champ_no_raw).strip() if champ_no_raw is not None else None
                nom_famille = str(nom_famille_raw).strip() if nom_famille_raw is not None else None
                prenom = str(prenom_raw).strip() if prenom_raw is not None else None

                # Valider que les champs essentiels sont présents et non vides.
                if not all([champ_no, nom_famille, prenom]):
                    msg = f"Ligne {row_idx} (Enseignants): Données essentielles (ChampNo, Nom de famille, Prénom) manquantes ou vides. Ligne ignorée."
                    flash(msg, "warning")
                    lignes_ignorees_compt += 1
                    continue

                # Le champ NomComplet est construit comme "Prénom Nom" pour la base de données.
                nom_complet = f"{prenom} {nom_famille}"

                # Détermination du statut "EstTempsPlein" avec valeurs par défaut et gestion des formats.
                est_temps_plein = True  # Valeur par défaut si non spécifié ou erreur
                if isinstance(temps_plein_raw, bool):
                    est_temps_plein = temps_plein_raw
                elif isinstance(temps_plein_raw, str):
                    val_str_upper = temps_plein_raw.strip().upper()
                    if val_str_upper in ("VRAI", "TRUE", "1", "OUI", "YES"):
                        est_temps_plein = True
                    elif val_str_upper in ("FAUX", "FALSE", "0", "NON", "NO", ""):
                        est_temps_plein = False
                    else:
                        flash(f"Ligne {row_idx} (Ens): Valeur inattendue pour 'Temps Plein' ('{temps_plein_raw}'). Assumée VRAI.", "warning")
                elif temps_plein_raw is None:  # Si la case est vide, on assume Temps Plein par défaut
                    est_temps_plein = True
                else:  # Autres types de données non attendus
                    flash(f"Ligne {row_idx} (Ens): Type de donnée inattendu pour 'Temps Plein' ('{temps_plein_raw}'). Assumée VRAI.", "warning")

                # Ajoute les données de l'enseignant à la liste d'importation.
                nouveaux_enseignants_a_importer.append(
                    {
                        "nomcomplet": nom_complet,
                        "nom": nom_famille,  # Nom de famille
                        "prenom": prenom,  # Prénom
                        "champno": champ_no,
                        "esttempsplein": est_temps_plein,
                        "estfictif": False,  # Les enseignants importés ne sont pas fictifs par défaut.
                        "peutchoisirhorschampprincipal": False,  # Par défaut
                    }
                )
            except IndexError:
                flash(f"Ligne {row_idx} (Enseignants): Nombre de colonnes insuffisant. La ligne est ignorée.", "warning")
                lignes_ignorees_compt += 1
                continue
            except (TypeError, ValueError) as te:
                flash(f"Ligne {row_idx} (Enseignants): Erreur de type de donnée ou de valeur. Ligne ignorée. Détails: {te}", "warning")
                lignes_ignorees_compt += 1
                continue

        if lignes_ignorees_compt > 0:
            flash(f"{lignes_ignorees_compt} ligne(s) du fichier enseignants ont été ignorée(s) en raison d'erreurs.", "info")

        if not nouveaux_enseignants_a_importer:
            flash("Aucun enseignant valide n'a été lu. Aucune modification apportée à la base de données.", "warning")
            return redirect(url_for("page_administration_donnees"))

        with db.cursor() as cur:
            # Supprime toutes les attributions et tous les enseignants existants avant l'importation.
            # C'est une opération d'écrasement.
            cur.execute("DELETE FROM AttributionsCours;")
            cur.execute("DELETE FROM Enseignants;")

            ens_importes_count = 0
            for ens_data in nouveaux_enseignants_a_importer:
                try:
                    cur.execute(
                        """INSERT INTO Enseignants (NomComplet, Nom, Prenom, ChampNo, EstTempsPlein, EstFictif, PeutChoisirHorsChampPrincipal)
                           VALUES (%(nomcomplet)s, %(nom)s, %(prenom)s, %(champno)s, %(esttempsplein)s, %(estfictif)s, %(peutchoisirhorschampprincipal)s);""",
                        ens_data,
                    )
                    ens_importes_count += 1
                except psycopg2.Error as e_insert:
                    # En cas d'erreur lors de l'insertion d'un enseignant, annule toute la transaction.
                    db.rollback()
                    err_details = e_insert.pgerror if hasattr(e_insert, "pgerror") else str(e_insert)
                    nom_prob = ens_data.get("nomcomplet", "INCONNU")
                    err_msg = (
                        f"Erreur lors de l'insertion de l'enseignant '{nom_prob}' (ChampNo: {ens_data.get('champno')}): {err_details}. "
                        "L'importation des enseignants a été annulée. Aucune donnée n'a été modifiée."
                    )
                    flash(err_msg, "error")
                    app.logger.error(err_msg)
                    return redirect(url_for("page_administration_donnees"))
            db.commit()  # Valide toutes les insertions si aucune erreur n'est survenue.
            msg_succes = (
                f"{ens_importes_count} enseignants ont été importés avec succès. "
                "Les anciens enseignants (y compris fictifs) et toutes les attributions existantes ont été supprimés."
            )
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
    # Récupère le port depuis les variables d'environnement (par défaut 8080).
    port = int(os.environ.get("PORT", 8080))
    # Active le mode debug si FLASK_DEBUG est 'true' (ignorant la casse).
    debug_mode = os.environ.get("FLASK_DEBUG", "False").lower() == "true"
    # Démarre l'application Flask, accessible depuis n'importe quelle interface réseau (0.0.0.0).
    app.run(host="0.0.0.0", port=port, debug=debug_mode)