import os

import psycopg2
import psycopg2.extras  # Nécessaire pour DictCursor
from flask import Flask, g, jsonify, render_template, request

# --- Configuration de l'application Flask ---
app = Flask(__name__)
# Une clé secrète est nécessaire pour les sessions Flask, même si non utilisées
# directement ici, c'est une bonne pratique.
app.secret_key = os.urandom(24)

# --- Configuration de la base de données ---
# Récupération des informations de connexion depuis les variables d'environnement
DB_HOST = os.environ.get("PGHOST")
DB_NAME = os.environ.get("PGDATABASE")
DB_USER = os.environ.get("PGUSER")
DB_PASS = os.environ.get("PGPASSWORD")
DB_PORT = os.environ.get("PGPORT", "5432")  # Port par défaut pour PostgreSQL


def get_db_connection_string():
    """Construit la chaîne de connexion à la base de données."""
    return f"dbname='{DB_NAME}' user='{DB_USER}' host='{DB_HOST}' password='{DB_PASS}' port='{DB_PORT}'"


def get_db():
    """
    Ouvre une nouvelle connexion à la base de données si aucune n'existe
    pour le contexte applicatif actuel (g).
    La connexion est stockée dans `g.db` pour être réutilisée au sein
    de la même requête.
    """
    if "db" not in g:
        try:
            conn_string = get_db_connection_string()
            g.db = psycopg2.connect(conn_string)
        except psycopg2.Error as e:
            # Loggue l'erreur de connexion pour le débogage côté serveur
            print(f"Erreur de connexion à la base de données: {e}")
            # Ne pas retourner None directement ici, laisser les routes gérer
            # l'absence de g.db ou les erreurs de get_db()
            g.db = None  # S'assurer que g.db est None si la connexion échoue
    return g.db


@app.teardown_appcontext
def close_db(_exception=None):  # _exception est intentionnellement non utilisé
    """Ferme la connexion à la base de données à la fin de la requête."""
    db = g.pop("db", None)
    if db is not None and not db.closed:
        try:
            db.close()
        except psycopg2.Error as e:
            print(f"Erreur lors de la fermeture de la connexion DB: {e}")


# --- Fonctions d'accès aux données (DAO) ---


def get_all_champs():
    """Récupère tous les champs de la base de données, ordonnés par leur numéro."""
    db = get_db()
    if not db:
        return []  # Retourne une liste vide si la connexion a échoué
    try:
        with db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT ChampNo, ChampNom FROM Champs ORDER BY ChampNo;")
            # Convertit chaque Row de DictCursor en un dictionnaire standard
            return [dict(row) for row in cur.fetchall()]
    except psycopg2.Error as e:
        print(f"Erreur lors de la récupération des champs: {e}")
        if db and not db.closed:  # Vérifie si db existe et n'est pas déjà fermé
            db.rollback()  # Annule la transaction en cas d'erreur
        return []


def get_champ_details(champ_no):
    """Récupère les détails d'un champ spécifique par son numéro."""
    db = get_db()
    if not db:
        return None
    try:
        with db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT ChampNo, ChampNom FROM Champs WHERE ChampNo = %s;", (champ_no,))
            champ_row = cur.fetchone()
        return dict(champ_row) if champ_row else None
    except psycopg2.Error as e:
        print(f"Erreur lors de la récupération des détails du champ {champ_no}: {e}")
        if db and not db.closed:
            db.rollback()
        return None


def get_enseignants_par_champ(champ_no):
    """
    Récupère tous les enseignants d'un champ spécifique, ordonnés par fictif
    puis nom.
    """
    db = get_db()
    if not db:
        return []
    try:
        with db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """
                SELECT EnseignantID, NomComplet, EstTempsPlein, EstFictif,
                       PeutChoisirHorsChampPrincipal
                FROM Enseignants
                WHERE ChampNo = %s
                ORDER BY EstFictif, NomComplet;
            """,
                (champ_no,),
            )
            return [dict(e) for e in cur.fetchall()]
    except psycopg2.Error as e:
        print(f"Erreur récupération enseignants champ {champ_no}: {e}")
        if db and not db.closed:
            db.rollback()
        return []


def get_cours_disponibles_par_champ(champ_no):
    """
    Récupère les cours disponibles pour un champ, avec le nombre de groupes restants.
    """
    db = get_db()
    if not db:
        return []
    try:
        with db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            # Cette requête inclut tous les cours du champ, même ceux avec 0 groupe
            # restant. Le front-end gère l'affichage et la logique d'attribution.
            cur.execute(
                """
                SELECT
                    c.CodeCours, c.CoursDescriptif, c.NbPeriodes, c.EstCoursAutre,
                    c.NbGroupeInitial,
                    (c.NbGroupeInitial - COALESCE(SUM(ac.NbGroupesPris), 0))
                        AS grprestant
                FROM Cours c
                LEFT JOIN AttributionsCours ac ON c.CodeCours = ac.CodeCours
                WHERE c.ChampNo = %s
                GROUP BY c.CodeCours, c.CoursDescriptif, c.NbPeriodes,
                         c.EstCoursAutre, c.NbGroupeInitial
                ORDER BY c.EstCoursAutre, c.CodeCours;
            """,
                (champ_no,),
            )
            return [dict(cr) for cr in cur.fetchall()]
    except psycopg2.Error as e:
        print(f"Erreur lors de la récupération des cours du champ {champ_no}: {e}")
        if db and not db.closed:
            db.rollback()
        return []


def get_attributions_enseignant(enseignant_id):
    """Récupère toutes les attributions de cours pour un enseignant donné."""
    db = get_db()
    if not db:
        return []
    try:
        with db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """
                SELECT ac.AttributionID, ac.CodeCours, ac.NbGroupesPris,
                       c.CoursDescriptif, c.NbPeriodes, c.EstCoursAutre,
                       c.ChampNo AS ChampOrigineCours
                FROM AttributionsCours ac
                JOIN Cours c ON ac.CodeCours = c.CodeCours
                WHERE ac.EnseignantID = %s;
            """,
                (enseignant_id,),
            )
            return [dict(a) for a in cur.fetchall()]
    except psycopg2.Error as e:
        print(f"Erreur lors de la récupération des attributions pour l'enseignant {enseignant_id}: {e}")
        if db and not db.closed:
            db.rollback()
        return []


def calculer_periodes_enseignant(enseignant_id):
    """Calcule le total des périodes pour un enseignant donné."""
    attributions = get_attributions_enseignant(enseignant_id)
    periodes_enseignement = sum(attr["nbperiodes"] * attr["nbgroupespris"] for attr in attributions if not attr["estcoursautre"])
    periodes_autres = sum(attr["nbperiodes"] * attr["nbgroupespris"] for attr in attributions if attr["estcoursautre"])
    return {
        "periodes_cours": periodes_enseignement,
        "periodes_autres": periodes_autres,
        "total_periodes": periodes_enseignement + periodes_autres,
    }


def get_groupes_restants_pour_cours(code_cours):
    """Calcule le nombre de groupes restants pour un cours spécifique."""
    db = get_db()
    if not db:
        return -1  # Indique une erreur ou l'incapacité de calculer
    try:
        with db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """
                SELECT (c.NbGroupeInitial - COALESCE(SUM(ac.NbGroupesPris), 0))
                       AS grprestant
                FROM Cours c
                LEFT JOIN AttributionsCours ac ON c.CodeCours = ac.CodeCours
                WHERE c.CodeCours = %s
                GROUP BY c.NbGroupeInitial;
            """,
                (code_cours,),
            )
            result = cur.fetchone()
        # Si un cours n'existe pas ou n'a jamais été attribué et COALESCE
        # ne s'applique pas (e.g., cours inexistant), result peut être None.
        return (
            result["grprestant"] if result and result["grprestant"] is not None else 0  # Par défaut à 0 si non trouvé ou si grprestant est NULL
        )
    except psycopg2.Error as e:
        print(f"Erreur get_groupes_restants_pour_cours pour {code_cours}: {e}")
        if db and not db.closed:
            db.rollback()
        return -1  # Indique une erreur


# --- ROUTES DE L'APPLICATION (Pages HTML) ---
@app.route("/")
def index():
    """Affiche la page d'accueil avec la liste des champs."""
    champs = get_all_champs()
    return render_template("index.html", champs=champs)


@app.route("/champ/<string:champ_no>")
def page_champ(champ_no):
    """Affiche la page détaillée d'un champ."""
    champ_details = get_champ_details(champ_no)
    if not champ_details:
        return "Champ non trouvé", 404

    enseignants_du_champ_bruts = get_enseignants_par_champ(champ_no)
    cours_du_champ_disponibles = get_cours_disponibles_par_champ(champ_no)

    # Sépare les cours d'enseignement des autres tâches pour l'affichage
    cours_enseignement_champ = [c for c in cours_du_champ_disponibles if not c["estcoursautre"]]
    cours_autres_taches_champ = [c for c in cours_du_champ_disponibles if c["estcoursautre"]]

    # Enrichit les données des enseignants avec leurs attributions et totaux de périodes
    enseignants_avec_attributions = []
    taches_sommaire_champ_data = []  # Pour le tableau récapitulatif
    total_periodes_temps_plein_champ = 0
    nb_enseignants_temps_plein_champ = 0

    for ens_brut in enseignants_du_champ_bruts:
        attributions = get_attributions_enseignant(ens_brut["enseignantid"])
        periodes = calculer_periodes_enseignant(ens_brut["enseignantid"])
        enseignants_avec_attributions.append({**ens_brut, "attributions": attributions, "periodes_actuelles": periodes})

        # Collecte des données pour le sommaire des tâches du champ
        taches_sommaire_champ_data.append(
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
        # Calcul pour la moyenne des périodes des enseignants à temps plein (non fictifs)
        if ens_brut["esttempsplein"] and not ens_brut["estfictif"]:
            total_periodes_temps_plein_champ += periodes["total_periodes"]
            nb_enseignants_temps_plein_champ += 1

    # Calcul de la moyenne des périodes pour les enseignants à temps plein du champ
    moyenne_champ = (total_periodes_temps_plein_champ / nb_enseignants_temps_plein_champ) if nb_enseignants_temps_plein_champ > 0 else 0

    return render_template(
        "page_champ.html",
        champ=champ_details,
        enseignants=enseignants_avec_attributions,
        cours_enseignement_champ=cours_enseignement_champ,
        cours_autres_taches_champ=cours_autres_taches_champ,
        cours_disponibles_pour_tableau_restant=cours_du_champ_disponibles,
        taches_sommaire_champ=taches_sommaire_champ_data,
        moyenne_champ_initiale=moyenne_champ,
    )


# --- API ENDPOINTS ---
@app.route("/api/attributions/ajouter", methods=["POST"])
def api_ajouter_attribution():
    """API pour ajouter une attribution de cours à un enseignant."""
    db = get_db()
    if not db:
        return jsonify({"success": False, "message": "Erreur de connexion BDD"}), 500

    data = request.get_json()
    if not data:
        return jsonify({"success": False, "message": "Aucune donnée JSON reçue"}), 400

    enseignant_id = data.get("enseignant_id")
    code_cours = data.get("code_cours")
    nb_groupes_a_prendre = 1  # Par défaut, on attribue un groupe à la fois

    if not enseignant_id or not code_cours:
        return jsonify({"success": False, "message": "Données manquantes (id ou code_cours)"}), 400

    attribution_id = None
    periodes_enseignant_maj = {}
    groupes_restants_cours_maj = 0

    try:
        with db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            # Vérifie la disponibilité des groupes pour le cours
            cur.execute(
                """
                SELECT (NbGroupeInitial - COALESCE((
                    SELECT SUM(NbGroupesPris)
                    FROM AttributionsCours
                    WHERE CodeCours = %s), 0)
                ) as grp_dispo
                FROM Cours WHERE CodeCours = %s;
            """,
                (code_cours, code_cours),
            )
            cours_info = cur.fetchone()

            if not cours_info or cours_info["grp_dispo"] < nb_groupes_a_prendre:
                return jsonify(
                    {
                        "success": False,
                        "message": "Plus de groupes disponibles ou cours inexistant.",
                    }
                ), 409  # Conflit: la ressource n'est pas dans l'état attendu

            # Insère la nouvelle attribution
            cur.execute(
                """
                INSERT INTO AttributionsCours (EnseignantID, CodeCours, NbGroupesPris)
                VALUES (%s, %s, %s) RETURNING AttributionID;
            """,
                (enseignant_id, code_cours, nb_groupes_a_prendre),
            )
            insert_result_row = cur.fetchone()

            if insert_result_row is None:
                db.rollback()
                print("Erreur critique: INSERT n'a pas retourné d'ID pour l'attribution.")
                return jsonify(
                    {
                        "success": False,
                        "message": "Erreur interne (pas de retour ID attribution).",
                    }
                ), 500
            attribution_id = insert_result_row["attributionid"]
            db.commit()  # Valide la transaction

        # Calculs post-commit pour la réponse JSON
        try:
            periodes_enseignant_maj = calculer_periodes_enseignant(enseignant_id)
            groupes_restants_cours_maj = get_groupes_restants_pour_cours(code_cours)
            if groupes_restants_cours_maj == -1:  # Indique une erreur de la fonction DAO
                raise Exception("Erreur calcul groupes restants post-attribution.")
        except Exception as calc_error:
            # L'attribution a réussi, mais les calculs pour la réponse ont échoué
            print(f"Erreur post-attribution (calculs): {calc_error}")
            return jsonify(
                {
                    "success": True,
                    "message": "Cours attribué, mais erreur màj des totaux affichés.",
                    "attribution_id": attribution_id,
                    "enseignant_id": enseignant_id,
                    "code_cours": code_cours,
                    # Retourne les valeurs même si potentiellement incomplètes ou par défaut
                    "periodes_enseignant": periodes_enseignant_maj,
                    "groupes_restants_cours": groupes_restants_cours_maj,
                }
            ), 201  # Créé, mais avec un avertissement potentiel

        # Récupère les informations de l'enseignant pour la réponse
        with db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                "SELECT ChampNo, EstTempsPlein, EstFictif FROM Enseignants WHERE EnseignantID = %s",
                (enseignant_id,),
            )
            enseignant_info_row = cur.fetchone()

        if enseignant_info_row is None:
            # Cela ne devrait pas arriver si l'enseignant_id est valide
            print(f"Erreur critique: Enseignant {enseignant_id} non trouvé après attribution et commit.")
            return jsonify(
                {
                    "success": True,  # L'attribution a réussi
                    "message": "Cours attribué, mais erreur récupération détails enseignant.",
                    "attribution_id": attribution_id,
                    # Autres infos potentiellement utiles même si l'enseignant n'est pas trouvé
                }
            ), 500  # Erreur serveur car état final potentiellement inconsistant
        enseignant_info_dict = dict(enseignant_info_row)

        return (
            jsonify(
                {
                    "success": True,
                    "message": "Cours attribué avec succès!",
                    "attribution_id": attribution_id,
                    "enseignant_id": enseignant_id,
                    "code_cours": code_cours,
                    "periodes_enseignant": periodes_enseignant_maj,
                    "groupes_restants_cours": groupes_restants_cours_maj,
                    "champ_enseignant": enseignant_info_dict.get("champno"),
                    "est_temps_plein": enseignant_info_dict.get("esttempsplein", False),
                    "est_fictif": enseignant_info_dict.get("estfictif", False),
                }
            ),
            201,  # Code HTTP pour "Created"
        )

    except psycopg2.Error as e:
        if db and not db.closed:
            db.rollback()
        print(f"Erreur psycopg2 API ajouter attribution: {e}")
        return jsonify({"success": False, "message": "Erreur base de données lors de l'ajout."}), 500
    except Exception as e:
        # Ce bloc catch les erreurs non-psycopg2 (ex: erreurs de logique Python)
        if db and not db.closed:
            db.rollback()  # Assure un rollback si une transaction était en cours
        print(f"Erreur Exception API ajouter attribution: {e}")
        return jsonify({"success": False, "message": "Erreur serveur inattendue lors de l'ajout."}), 500


@app.route("/api/attributions/supprimer", methods=["POST"])
def api_supprimer_attribution():
    """API pour supprimer une attribution de cours."""
    db = get_db()
    if not db:
        return jsonify({"success": False, "message": "Erreur de connexion BDD"}), 500

    data = request.get_json()
    if not data:
        return jsonify({"success": False, "message": "Aucune donnée JSON reçue"}), 400

    attribution_id_req = data.get("attribution_id")
    if not attribution_id_req:
        return jsonify({"success": False, "message": "ID d'attribution manquant"}), 400

    enseignant_id = None
    code_cours = None
    periodes_enseignant_maj = {}
    groupes_restants_cours_maj = 0
    nb_periodes_cours_libere = 0
    enseignant_data_dict = {}

    try:
        with db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            # Récupère les infos de l'attribution avant suppression
            cur.execute(
                """
                SELECT ac.EnseignantID, ac.CodeCours, c.NbPeriodes AS PeriodesDuCours
                FROM AttributionsCours ac JOIN Cours c ON ac.CodeCours = c.CodeCours
                WHERE ac.AttributionID = %s;
            """,
                (attribution_id_req,),
            )
            attribution_info_row = cur.fetchone()

            if not attribution_info_row:
                return jsonify({"success": False, "message": "Attribution non trouvée"}), 404

            attribution_info = dict(attribution_info_row)
            enseignant_id = attribution_info["enseignantid"]
            code_cours = attribution_info["codecours"]
            nb_periodes_cours_libere = attribution_info.get("periodesducours", 0)

            # Supprime l'attribution
            cur.execute(
                "DELETE FROM AttributionsCours WHERE AttributionID = %s;",
                (attribution_id_req,),
            )
            db.commit()  # Valide la suppression

            # Calculs post-suppression pour la réponse
            try:
                periodes_enseignant_maj = calculer_periodes_enseignant(enseignant_id)
                groupes_restants_cours_maj = get_groupes_restants_pour_cours(code_cours)
                if groupes_restants_cours_maj == -1:
                    raise Exception("Erreur calcul groupes restants post-suppression.")
            except Exception as calc_error:
                print(f"Erreur post-suppression attribution (calculs): {calc_error}")
                # La suppression a réussi, mais les calculs pour la réponse ont échoué
                return jsonify(
                    {
                        "success": True,
                        "message": "Attribution supprimée, mais erreur màj des totaux.",
                        "enseignant_id": enseignant_id,
                        "code_cours": code_cours,
                        "nb_periodes_cours_libere": nb_periodes_cours_libere,
                        "periodes_enseignant": periodes_enseignant_maj,
                        "groupes_restants_cours": groupes_restants_cours_maj,
                    }
                ), 200  # OK, mais avec un avertissement

            # Récupère les infos de l'enseignant concerné
            with db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur_ens:
                cur_ens.execute(
                    "SELECT ChampNo, EstTempsPlein, EstFictif FROM Enseignants WHERE EnseignantID = %s",
                    (enseignant_id,),
                )
                enseignant_data_row = cur_ens.fetchone()
                if not enseignant_data_row:
                    print(f"Avertissement: Enseignant {enseignant_id} non trouvé après suppression attribution pour màj détails.")
                    # enseignant_data_dict restera vide, .get() gérera cela dans la réponse
                else:
                    enseignant_data_dict = dict(enseignant_data_row)

        return (
            jsonify(
                {
                    "success": True,
                    "message": "Attribution supprimée avec succès!",
                    "enseignant_id": enseignant_id,
                    "code_cours": code_cours,
                    "periodes_enseignant": periodes_enseignant_maj,
                    "groupes_restants_cours": groupes_restants_cours_maj,
                    "nb_periodes_cours_libere": nb_periodes_cours_libere,
                    "champ_enseignant": enseignant_data_dict.get("champno"),
                    "est_temps_plein": enseignant_data_dict.get("esttempsplein", False),
                    "est_fictif": enseignant_data_dict.get("estfictif", False),
                }
            ),
            200,  # OK
        )

    except psycopg2.Error as e:
        if db and not db.closed:
            db.rollback()
        print(f"Erreur psycopg2 API supprimer attribution: {e}")
        # Vérifie spécifiquement le code d'erreur pour violation de contrainte FK
        if e.pgcode == "23503":  # Foreign key violation
            return (
                jsonify(
                    {
                        "success": False,
                        "message": ("Impossible de supprimer cette attribution car elle est référencée ailleurs (contrainte de clé étrangère)."),
                    }
                ),
                409,  # Conflit
            )
        return jsonify({"success": False, "message": "Erreur base de données lors de la suppression."}), 500
    except Exception as e:
        if db and not db.closed:
            db.rollback()
        print(f"Erreur Exception API supprimer attribution: {e}")
        return jsonify({"success": False, "message": f"Erreur serveur inattendue: {str(e)}"}), 500


@app.route("/api/champs/<string:champ_no>/taches_restantes/creer", methods=["POST"])
def api_creer_tache_restante(champ_no):
    """API pour créer une nouvelle tâche restante (enseignant fictif) dans un champ."""
    db = get_db()
    if not db:
        return jsonify({"success": False, "message": "Erreur de connexion BDD"}), 500
    try:
        with db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            # Détermine le prochain numéro pour le nom de la tâche restante
            cur.execute(
                """
                SELECT NomComplet FROM Enseignants
                WHERE ChampNo = %s AND EstFictif = TRUE AND NomComplet LIKE %s;
            """,
                (champ_no, f"{champ_no}-Tâche restante-%"),
            )
            taches_existantes = cur.fetchall()

            max_num = 0
            for tache in taches_existantes:
                try:
                    # Extrait le numéro à la fin du nom de la tâche
                    num_str = tache["nomcomplet"].split("-")[-1].strip()
                    num = int(num_str)
                    if num > max_num:
                        max_num = num
                except (ValueError, IndexError):
                    # Ignore les noms qui ne correspondent pas au format attendu
                    continue

            # Crée le nom de la nouvelle tâche
            nom_tache_restante = f"{champ_no}-Tâche restante-{max_num + 1}"

            # Insère le nouvel enseignant fictif
            cur.execute(
                """
                INSERT INTO Enseignants (NomComplet, ChampNo, EstTempsPlein, EstFictif, PeutChoisirHorsChampPrincipal)
                VALUES (%s, %s, FALSE, TRUE, FALSE)
                RETURNING EnseignantID, NomComplet, EstTempsPlein, EstFictif, PeutChoisirHorsChampPrincipal;
            """,
                (nom_tache_restante, champ_no),
            )
            nouvel_enseignant_fictif_row = cur.fetchone()
            db.commit()

            if nouvel_enseignant_fictif_row is None:
                print(f"Erreur critique: INSERT tâche restante pour {nom_tache_restante} n'a rien retourné.")
                return jsonify(
                    {
                        "success": False,
                        "message": "Erreur interne lors de la création (pas de retour).",
                    }
                ), 500
            nouvel_enseignant_fictif_dict = dict(nouvel_enseignant_fictif_row)

        return (
            jsonify(
                {
                    "success": True,
                    "message": "Tâche restante créée avec succès!",
                    "enseignant": nouvel_enseignant_fictif_dict,
                    # Initialise les périodes pour le nouvel enseignant fictif
                    "periodes_actuelles": {
                        "periodes_cours": 0,
                        "periodes_autres": 0,
                        "total_periodes": 0,
                    },
                    "attributions": [],  # Un nouvel enseignant n'a pas d'attributions
                }
            ),
            201,
        )

    except psycopg2.Error as e:
        if db and not db.closed:
            db.rollback()
        print(f"Erreur psycopg2 API créer tâche restante: {e}")
        return jsonify({"success": False, "message": "Erreur base de données lors de la création."}), 500
    except Exception as e:
        if db and not db.closed:
            db.rollback()
        print(f"Erreur Exception API créer tâche restante: {e}")
        return jsonify({"success": False, "message": "Erreur serveur inattendue lors de la création."}), 500


@app.route("/api/enseignants/<int:enseignant_id>/supprimer", methods=["POST"])
def api_supprimer_enseignant(enseignant_id):
    """
    API pour supprimer un enseignant.
    Retourne les détails des cours libérés pour mise à jour de l'interface.
    """
    db = get_db()
    if not db:
        return jsonify({"success": False, "message": "Erreur de connexion BDD"}), 500

    try:
        with db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            # 1. Vérifier l'existence de l'enseignant
            cur.execute(
                "SELECT ChampNo FROM Enseignants WHERE EnseignantID = %s;",
                (enseignant_id,),
            )
            enseignant_info_row = cur.fetchone()
            if not enseignant_info_row:
                return jsonify({"success": False, "message": "Enseignant non trouvé."}), 404
            # _enseignant_info_dict = dict(enseignant_info_row) # Non utilisé directement

            # 2. Récupérer les cours affectés à cet enseignant AVANT suppression
            # Ceci est nécessaire pour savoir quels cours mettre à jour côté client
            cur.execute(
                """
                SELECT ac.CodeCours, c.NbPeriodes
                FROM AttributionsCours ac
                JOIN Cours c ON ac.CodeCours = c.CodeCours
                WHERE ac.EnseignantID = %s;
            """,
                (enseignant_id,),
            )
            cours_affectes_avant_suppression = cur.fetchall()

            # 3. Supprimer l'enseignant.
            # La contrainte ON DELETE CASCADE sur AttributionsCours.EnseignantID
            # devrait s'occuper de supprimer les attributions associées.
            cur.execute("DELETE FROM Enseignants WHERE EnseignantID = %s;", (enseignant_id,))
            db.commit()  # Valider la suppression de l'enseignant et de ses attributions

            # 4. Calculer les nouveaux groupes restants pour chaque cours qui était affecté
            cours_liberes_details = []
            if cours_affectes_avant_suppression:
                # Obtenir la liste unique des codes de cours affectés
                codes_cours_uniques = list(set(ca["codecours"] for ca in cours_affectes_avant_suppression))

                for code_cours in codes_cours_uniques:
                    nouveaux_groupes_restants = get_groupes_restants_pour_cours(code_cours)
                    if nouveaux_groupes_restants == -1:  # Erreur DAO
                        # Remonter une exception pour la gestion d'erreur globale
                        raise Exception(f"Erreur calcul des groupes restants pour {code_cours} après suppression enseignant.")

                    # Récupère le nombre de périodes du cours (pour information)
                    nb_periodes_cours = next(
                        (c["nbperiodes"] for c in cours_affectes_avant_suppression if c["codecours"] == code_cours),
                        0,  # Valeur par défaut si non trouvé (ne devrait pas arriver)
                    )

                    cours_liberes_details.append(
                        {
                            "code_cours": code_cours,
                            "nouveaux_groupes_restants": nouveaux_groupes_restants,
                            "nb_periodes": nb_periodes_cours,
                        }
                    )

        # 5. Construire et envoyer la réponse JSON
        return (
            jsonify(
                {
                    "success": True,
                    "message": ("Enseignant supprimé avec succès. Les cours ont été libérés."),
                    "enseignant_id": enseignant_id,  # ID de l'enseignant supprimé
                    "cours_liberes_details": cours_liberes_details,  # Détails des cours mis à jour
                }
            ),
            200,  # OK
        )

    except psycopg2.Error as e:
        if db and not db.closed:
            db.rollback()
        # Gérer spécifiquement l'erreur de violation de clé étrangère si ON DELETE CASCADE
        # n'est pas configuré ou si une autre contrainte FK bloque.
        if e.pgcode == "23503":  # Foreign key violation
            print(f"Erreur psycopg2 (FK violation) API supprimer enseignant: {e}")
            return (
                jsonify(
                    {
                        "success": False,
                        "message": (
                            "Impossible de supprimer cet enseignant car il est "
                            "référencé par d'autres enregistrements qui ne peuvent "
                            "pas être supprimés automatiquement (contrainte de clé étrangère)."
                        ),
                    }
                ),
                409,  # Conflit
            )
        print(f"Erreur psycopg2 API supprimer enseignant: {e}")
        return jsonify({"success": False, "message": "Erreur base de données lors de la suppression."}), 500
    except Exception as e:
        # Gère les erreurs inattendues (ex: problème de logique dans les calculs post-suppression)
        # Le commit principal a peut-être déjà eu lieu.
        # Un rollback ici est pour toute transaction implicite que Python ou Flask pourrait gérer.
        if db and not db.closed:
            db.rollback()
        print(f"Erreur Exception API supprimer enseignant: {e}")
        return jsonify({"success": False, "message": f"Erreur serveur inattendue: {str(e)}"}), 500


# --- Démarrage de l'application ---
if __name__ == "__main__":
    # Exécute l'application Flask en mode débogage
    # 'host="0.0.0.0"' rend l'application accessible depuis d'autres machines sur le réseau
    app.run(host="0.0.0.0", port=8080, debug=True)
