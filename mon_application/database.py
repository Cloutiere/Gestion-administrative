# mon_application/database.py
"""
Ce module centralise toutes les interactions avec la base de données PostgreSQL.

Il contient la configuration de la connexion, les fonctions pour gérer le cycle de
vie de la connexion dans le contexte de l'application Flask, et toutes les
fonctions DAO (Data Access Object) pour les opérations CRUD sur les
utilisateurs, champs, enseignants, cours et attributions.
"""

import os
from typing import Any

import psycopg2
import psycopg2.extras
from flask import Flask, current_app, g

# --- Gestion de la connexion à la base de données ---

DB_HOST = os.environ.get("PGHOST")
DB_NAME = os.environ.get("PGDATABASE")
DB_USER = os.environ.get("PGUSER")
DB_PASS = os.environ.get("PGPASSWORD")
DB_PORT = os.environ.get("PGPORT", "5432")


def get_db_connection_string() -> str:
    """Construit la chaîne de connexion PostgreSQL à partir des variables d'environnement."""
    return f"dbname='{DB_NAME}' user='{DB_USER}' host='{DB_HOST}' password='{DB_PASS}' port='{DB_PORT}'"


def get_db():
    """
    Ouvre une nouvelle connexion à la base de données si aucune n'existe pour la requête en cours.
    La connexion est stockée dans l'objet `g` de Flask, garantissant qu'elle est unique par requête.
    En cas d'échec de connexion, logue l'erreur et retourne `None`.
    """
    if "db" not in g:
        try:
            conn_string = get_db_connection_string()
            g.db = psycopg2.connect(conn_string)
        except psycopg2.OperationalError as e:
            current_app.logger.error(f"Erreur de connexion à la base de données: {e}")
            g.db = None
    return g.db


def close_db(_exception: BaseException | None = None) -> None:
    """
    Ferme la connexion à la base de données à la fin de la requête (teardown).
    Le paramètre _exception est fourni par Flask mais n'est pas utilisé ici.
    """
    db = g.pop("db", None)
    if db is not None and not db.closed:
        db.close()


def init_app(app: Flask) -> None:
    """
    Initialise l'application Flask pour la gestion de la base de données.
    Enregistre la fonction `close_db` pour qu'elle soit appelée après chaque requête.
    """
    app.teardown_appcontext(close_db)


# --- Fonctions DAO - Utilisateurs ---


def get_user_by_id(user_id: int) -> dict[str, Any] | None:
    """
    Récupère un utilisateur par son ID, incluant ses permissions d'accès aux champs.
    Retourne un dictionnaire de l'utilisateur ou None si non trouvé.
    """
    db = get_db()
    if not db:
        return None
    try:
        with db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """
                SELECT u.id, u.username, u.password_hash, u.is_admin,
                       ARRAY_AGG(uca.champ_no ORDER BY uca.champ_no) FILTER (WHERE uca.champ_no IS NOT NULL) AS allowed_champs
                FROM users u
                LEFT JOIN user_champ_access uca ON u.id = uca.user_id
                WHERE u.id = %s
                GROUP BY u.id;
                """,
                (user_id,),
            )
            if user_data := cur.fetchone():
                user_dict = dict(user_data)
                # Garantit que 'allowed_champs' est une liste vide plutôt que None ou [None].
                user_dict["allowed_champs"] = user_dict["allowed_champs"] or []
                return user_dict
            return None
    except psycopg2.Error as e:
        current_app.logger.error(f"Erreur DAO (get_user_by_id) pour ID {user_id}: {e}")
        return None


def get_user_by_username(username: str) -> dict[str, Any] | None:
    """Récupère un utilisateur par son nom d'utilisateur."""
    db = get_db()
    if not db:
        return None
    try:
        with db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT id, username, password_hash, is_admin FROM users WHERE username = %s;", (username,))
            return dict(user_data) if (user_data := cur.fetchone()) else None
    except psycopg2.Error as e:
        current_app.logger.error(f"Erreur DAO (get_user_by_username) pour '{username}': {e}")
        return None


def get_users_count() -> int:
    """Compte le nombre total d'utilisateurs."""
    db = get_db()
    if not db:
        return 0
    try:
        with db.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM users;")
            result = cur.fetchone()
            return result[0] if result else 0
    except psycopg2.Error as e:
        current_app.logger.error(f"Erreur DAO (get_users_count): {e}")
        return 0


def get_admin_count() -> int:
    """Compte le nombre d'utilisateurs administrateurs."""
    db = get_db()
    if not db:
        return 0
    try:
        with db.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM users WHERE is_admin = TRUE;")
            result = cur.fetchone()
            return result[0] if result else 0
    except psycopg2.Error as e:
        current_app.logger.error(f"Erreur DAO (get_admin_count): {e}")
        return 0


def create_user(username: str, password_hash: str, is_admin: bool = False) -> dict[str, Any] | None:
    """Crée un nouvel utilisateur."""
    db = get_db()
    if not db:
        return None
    try:
        with db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                "INSERT INTO users (username, password_hash, is_admin) VALUES (%s, %s, %s) RETURNING id, username, is_admin;",
                (username, password_hash, is_admin),
            )
            user_data = cur.fetchone()
            db.commit()
            return dict(user_data) if user_data else None
    except psycopg2.errors.UniqueViolation:
        db.rollback()
        current_app.logger.warning(f"Tentative de création d'un utilisateur existant: {username}")
        return None
    except psycopg2.Error as e:
        db.rollback()
        current_app.logger.error(f"Erreur DAO (create_user) pour {username}: {e}")
        return None


def get_all_users_with_access_info() -> list[dict[str, Any]]:
    """Récupère tous les utilisateurs avec la liste des champs auxquels ils ont accès."""
    db = get_db()
    if not db:
        return []
    try:
        with db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """
                SELECT u.id, u.username, u.is_admin,
                       ARRAY_AGG(uca.champ_no ORDER BY uca.champ_no) FILTER (WHERE uca.champ_no IS NOT NULL) AS allowed_champs
                FROM users u
                LEFT JOIN user_champ_access uca ON u.id = uca.user_id
                GROUP BY u.id
                ORDER BY u.username;
                """
            )
            users_data = []
            for row in cur.fetchall():
                user_dict = dict(row)
                user_dict["allowed_champs"] = user_dict["allowed_champs"] or []
                users_data.append(user_dict)
            return users_data
    except psycopg2.Error as e:
        current_app.logger.error(f"Erreur DAO (get_all_users_with_access_info): {e}")
        return []


def update_user_champ_access(user_id: int, champ_nos: list[str]) -> bool:
    """Met à jour les permissions d'accès aux champs pour un utilisateur."""
    db = get_db()
    if not db:
        return False
    try:
        with db.cursor() as cur:
            cur.execute("DELETE FROM user_champ_access WHERE user_id = %s;", (user_id,))
            if champ_nos:
                values = [(user_id, champ_no) for champ_no in champ_nos]
                psycopg2.extras.execute_values(cur, "INSERT INTO user_champ_access (user_id, champ_no) VALUES %s;", values)
            db.commit()
            return True
    except psycopg2.Error as e:
        db.rollback()
        current_app.logger.error(f"Erreur DAO (update_user_champ_access) pour user {user_id}: {e}")
        return False


def delete_user_data(user_id: int) -> bool:
    """Supprime un utilisateur et ses accès (par CASCADE)."""
    db = get_db()
    if not db:
        return False
    try:
        with db.cursor() as cur:
            cur.execute("DELETE FROM users WHERE id = %s;", (user_id,))
            db.commit()
            return cur.rowcount > 0  # True si une ligne a été supprimée
    except psycopg2.Error as e:
        db.rollback()
        current_app.logger.error(f"Erreur DAO (delete_user_data) pour user {user_id}: {e}")
        return False


# --- Fonctions DAO - Champs, Enseignants, Cours, Attributions ---


def get_all_champs() -> list[dict[str, Any]]:
    """Récupère tous les champs, triés par leur numéro."""
    db = get_db()
    if not db:
        return []
    try:
        with db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT champno, champnom, estverrouille FROM champs ORDER BY champno;")
            return [dict(row) for row in cur.fetchall()]
    except psycopg2.Error as e:
        current_app.logger.error(f"Erreur DAO (get_all_champs): {e}")
        return []


def get_champ_details(champ_no: str) -> dict[str, Any] | None:
    """Récupère les détails d'un champ spécifique."""
    db = get_db()
    if not db:
        return None
    try:
        with db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT champno, champnom, estverrouille FROM champs WHERE champno = %s;", (champ_no,))
            return dict(row) if (row := cur.fetchone()) else None
    except psycopg2.Error as e:
        current_app.logger.error(f"Erreur DAO (get_champ_details) pour {champ_no}: {e}")
        return None


def get_enseignants_par_champ(champ_no: str) -> list[dict[str, Any]]:
    """Récupère les enseignants d'un champ, triés par statut fictif puis par nom."""
    db = get_db()
    if not db:
        return []
    try:
        with db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """
                SELECT enseignantid, nomcomplet, nom, prenom, esttempsplein, estfictif, peutchoisirhorschampprincipal
                FROM enseignants WHERE champno = %s ORDER BY estfictif, nom, prenom;
                """,
                (champ_no,),
            )
            return [dict(e) for e in cur.fetchall()]
    except psycopg2.Error as e:
        current_app.logger.error(f"Erreur DAO (get_enseignants_par_champ) pour {champ_no}: {e}")
        return []


def get_enseignant_champ_no(enseignant_id: int) -> str | None:
    """Récupère le numéro de champ principal d'un enseignant."""
    db = get_db()
    if not db:
        return None
    try:
        with db.cursor() as cur:
            cur.execute("SELECT champno FROM enseignants WHERE enseignantid = %s;", (enseignant_id,))
            result = cur.fetchone()
            return result[0] if result else None
    except psycopg2.Error as e:
        current_app.logger.error(f"Erreur DAO (get_enseignant_champ_no) pour {enseignant_id}: {e}")
        return None


def get_all_enseignants_avec_details() -> list[dict[str, Any]]:
    """Récupère tous les enseignants avec les détails du champ et le calcul des périodes."""
    db = get_db()
    if not db:
        return []
    try:
        with db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """
                SELECT e.enseignantid, e.nomcomplet, e.nom, e.prenom, e.esttempsplein, e.estfictif,
                       e.champno, ch.champnom, e.peutchoisirhorschampprincipal, ch.estverrouille
                FROM enseignants e JOIN champs ch ON e.champno = ch.champno
                ORDER BY e.champno, e.estfictif, e.nom, e.prenom;
                """
            )
            enseignants_bruts = [dict(row) for row in cur.fetchall()]

        toutes_les_attributions = get_toutes_les_attributions()
        attributions_par_enseignant = {}
        for attr in toutes_les_attributions:
            attributions_par_enseignant.setdefault(attr["enseignantid"], []).append(attr)

        enseignants_complets = []
        for ens_brut in enseignants_bruts:
            attributions = attributions_par_enseignant.get(ens_brut["enseignantid"], [])
            periodes = calculer_periodes_pour_attributions(attributions)
            compte_pour_moyenne_champ = ens_brut["esttempsplein"] and not ens_brut["estfictif"]
            enseignants_complets.append({**ens_brut, **periodes, "compte_pour_moyenne_champ": compte_pour_moyenne_champ})
        return enseignants_complets
    except psycopg2.Error as e:
        current_app.logger.error(f"Erreur DAO (get_all_enseignants_avec_details): {e}")
        return []


def get_cours_disponibles_par_champ(champ_no: str) -> list[dict[str, Any]]:
    """
    Récupère les cours d'un champ en calculant les groupes restants.
    Toutes les attributions (y compris fictives) sont soustraites pour un calcul précis.
    """
    db = get_db()
    if not db:
        return []
    try:
        with db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """
                SELECT
                    c.codecours, c.coursdescriptif, c.nbperiodes, c.estcoursautre, c.nbgroupeinitial,
                    (c.nbgroupeinitial - COALESCE(SUM(ac.nbgroupespris), 0)) AS grprestant
                FROM cours c
                LEFT JOIN attributionscours ac ON c.codecours = ac.codecours
                WHERE c.champno = %s
                GROUP BY c.codecours
                ORDER BY c.estcoursautre, c.codecours;
                """,
                (champ_no,),
            )
            return [dict(cr) for cr in cur.fetchall()]
    except psycopg2.Error as e:
        current_app.logger.error(f"Erreur DAO (get_cours_disponibles_par_champ) pour {champ_no}: {e}")
        return []


def get_attributions_enseignant(enseignant_id: int) -> list[dict[str, Any]]:
    """Récupère toutes les attributions de cours pour un enseignant spécifique."""
    db = get_db()
    if not db:
        return []
    try:
        with db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """
                SELECT ac.attributionid, ac.codecours, ac.nbgroupespris, c.coursdescriptif,
                       c.nbperiodes, c.estcoursautre, c.champno AS champoriginecours
                FROM attributionscours ac JOIN cours c ON ac.codecours = c.codecours
                WHERE ac.enseignantid = %s
                ORDER BY c.estcoursautre, c.coursdescriptif;
                """,
                (enseignant_id,),
            )
            return [dict(a) for a in cur.fetchall()]
    except psycopg2.Error as e:
        current_app.logger.error(f"Erreur DAO (get_attributions_enseignant) pour {enseignant_id}: {e}")
        return []


def get_toutes_les_attributions() -> list[dict[str, Any]]:
    """Récupère toutes les attributions de la base de données."""
    db = get_db()
    if not db:
        return []
    try:
        with db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """
                SELECT ac.attributionid, ac.enseignantid, ac.codecours, ac.nbgroupespris,
                       c.coursdescriptif, c.nbperiodes, c.estcoursautre
                FROM attributionscours ac JOIN cours c ON ac.codecours = c.codecours
                ORDER BY ac.enseignantid, c.estcoursautre, c.coursdescriptif;
                """
            )
            return [dict(a) for a in cur.fetchall()]
    except psycopg2.Error as e:
        current_app.logger.error(f"Erreur DAO (get_toutes_les_attributions): {e}")
        return []


def calculer_periodes_pour_attributions(attributions: list[dict[str, Any]]) -> dict[str, float]:
    """
    Calcule les totaux de périodes (régulières, autres, total) à partir d'une liste d'attributions.
    Cette fonction est pure (sans appel DB) pour une meilleure testabilité et réutilisation.
    """
    periodes_cours = sum(float(a["nbperiodes"]) * a["nbgroupespris"] for a in attributions if not a["estcoursautre"])
    periodes_autres = sum(float(a["nbperiodes"]) * a["nbgroupespris"] for a in attributions if a["estcoursautre"])
    return {
        "periodes_cours": periodes_cours,
        "periodes_autres": periodes_autres,
        "total_periodes": periodes_cours + periodes_autres,
    }


def calculer_periodes_enseignant(enseignant_id: int) -> dict[str, float]:
    """Calcule les totaux de périodes pour un enseignant en récupérant ses attributions."""
    attributions = get_attributions_enseignant(enseignant_id)
    return calculer_periodes_pour_attributions(attributions)


def get_groupes_restants_pour_cours(code_cours: str) -> int:
    """Calcule le nombre de groupes restants pour un cours, en tenant compte de TOUTES les attributions."""
    db = get_db()
    if not db:
        return 0
    try:
        with db.cursor() as cur:
            cur.execute(
                """
                SELECT (c.nbgroupeinitial - COALESCE(SUM(ac.nbgroupespris), 0))
                FROM cours c
                LEFT JOIN attributionscours ac ON c.codecours = ac.codecours
                WHERE c.codecours = %s
                GROUP BY c.codecours;
                """,
                (code_cours,),
            )
            result = cur.fetchone()
            return int(result[0]) if result and result[0] is not None else 0
    except psycopg2.Error as e:
        current_app.logger.error(f"Erreur DAO (get_groupes_restants_pour_cours) pour {code_cours}: {e}")
        return 0


def get_all_cours_avec_details_champ() -> list[dict[str, Any]]:
    """Récupère tous les cours avec les détails de leur champ d'origine."""
    db = get_db()
    if not db:
        return []
    try:
        with db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """
                SELECT c.codecours, c.coursdescriptif, c.champno, ch.champnom
                FROM cours c JOIN champs ch ON c.champno = ch.champno ORDER BY c.codecours;
                """
            )
            return [dict(row) for row in cur.fetchall()]
    except psycopg2.Error as e:
        current_app.logger.error(f"Erreur DAO (get_all_cours_avec_details_champ): {e}")
        return []


def get_all_cours_grouped_by_champ() -> dict[str, dict[str, Any]]:
    """Récupère tous les cours et les regroupe par champ."""
    db = get_db()
    if not db:
        return {}
    try:
        with db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """
                SELECT c.codecours, c.coursdescriptif, c.nbperiodes, c.nbgroupeinitial, c.estcoursautre,
                       c.champno, ch.champnom
                FROM cours c JOIN champs ch ON c.champno = ch.champno
                ORDER BY ch.champno, c.codecours;
                """
            )
            cours_par_champ: dict[str, Any] = {}
            for row in cur.fetchall():
                champ_no = row["champno"]
                if champ_no not in cours_par_champ:
                    cours_par_champ[champ_no] = {"champ_nom": row["champnom"], "cours": []}
                cours_par_champ[champ_no]["cours"].append(dict(row))
            return cours_par_champ
    except psycopg2.Error as e:
        current_app.logger.error(f"Erreur DAO (get_all_cours_grouped_by_champ): {e}")
        return {}


def toggle_champ_lock_status(champ_no: str) -> bool | None:
    """Bascule le statut de verrouillage d'un champ et retourne le nouvel état."""
    db = get_db()
    if not db:
        return None
    try:
        with db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("UPDATE champs SET estverrouille = NOT estverrouille WHERE champno = %s RETURNING estverrouille;", (champ_no,))
            result = cur.fetchone()
            db.commit()
            return result["estverrouille"] if result else None
    except psycopg2.Error as e:
        db.rollback()
        current_app.logger.error(f"Erreur DAO (toggle_champ_lock_status) pour {champ_no}: {e}")
        return None


def get_verrou_info_enseignant(enseignant_id: int) -> dict[str, Any] | None:
    """Récupère le statut de verrouillage du champ d'un enseignant et son statut fictif."""
    db = get_db()
    if not db:
        return None
    try:
        with db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """
                SELECT e.estfictif, ch.estverrouille FROM enseignants e
                JOIN champs ch ON e.champno = ch.champno WHERE e.enseignantid = %s;
                """,
                (enseignant_id,),
            )
            return dict(row) if (row := cur.fetchone()) else None
    except psycopg2.Error as e:
        current_app.logger.error(f"Erreur DAO (get_verrou_info_enseignant) pour {enseignant_id}: {e}")
        return None


def add_attribution(enseignant_id: int, code_cours: str) -> int | None:
    """Ajoute une attribution de cours (1 groupe) à un enseignant."""
    db = get_db()
    if not db:
        return None
    try:
        with db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                "INSERT INTO attributionscours (enseignantid, codecours, nbgroupespris) VALUES (%s, %s, 1) RETURNING attributionid;",
                (enseignant_id, code_cours),
            )
            new_id = cur.fetchone()
            db.commit()
            return new_id["attributionid"] if new_id else None
    except psycopg2.Error as e:
        db.rollback()
        current_app.logger.error(f"Erreur DAO (add_attribution) pour ens {enseignant_id}, cours {code_cours}: {e}")
        return None


def get_attribution_info(attribution_id: int) -> dict[str, Any] | None:
    """Récupère les détails d'une attribution, y compris le statut de verrouillage du champ de l'enseignant."""
    db = get_db()
    if not db:
        return None
    try:
        with db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """
                SELECT ac.enseignantid, ac.codecours, e.estfictif, ch.estverrouille, e.champno
                FROM attributionscours ac
                JOIN enseignants e ON ac.enseignantid = e.enseignantid
                JOIN champs ch ON e.champno = ch.champno
                WHERE ac.attributionid = %s;
                """,
                (attribution_id,),
            )
            return dict(row) if (row := cur.fetchone()) else None
    except psycopg2.Error as e:
        current_app.logger.error(f"Erreur DAO (get_attribution_info) pour attr {attribution_id}: {e}")
        return None


def delete_attribution(attribution_id: int) -> bool:
    """Supprime une attribution de cours."""
    db = get_db()
    if not db:
        return False
    try:
        with db.cursor() as cur:
            cur.execute("DELETE FROM attributionscours WHERE attributionid = %s;", (attribution_id,))
            db.commit()
            return cur.rowcount > 0
    except psycopg2.Error as e:
        db.rollback()
        current_app.logger.error(f"Erreur DAO (delete_attribution) pour attr {attribution_id}: {e}")
        return False


def create_fictif_enseignant(champ_no: str) -> dict[str, Any] | None:
    """Crée un nouvel enseignant fictif (tâche restante) pour un champ, avec un nom unique."""
    db = get_db()
    if not db:
        return None
    try:
        with db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                "SELECT nomcomplet FROM enseignants WHERE champno = %s AND estfictif = TRUE AND nomcomplet LIKE %s;",
                (champ_no, f"{champ_no}-Tâche restante-%"),
            )
            numeros = [int(row["nomcomplet"].split("-")[-1]) for row in cur.fetchall() if row["nomcomplet"].split("-")[-1].isdigit()]
            next_num = max(numeros) + 1 if numeros else 1
            nom_tache = f"{champ_no}-Tâche restante-{next_num}"

            cur.execute(
                """
                INSERT INTO enseignants (nomcomplet, champno, esttempsplein, estfictif) VALUES (%s, %s, TRUE, TRUE)
                RETURNING enseignantid, nomcomplet, nom, prenom, esttempsplein, estfictif, peutchoisirhorschampprincipal, champno;
                """,
                (nom_tache, champ_no),
            )
            new_fictif_data = cur.fetchone()
            db.commit()
            return dict(new_fictif_data) if new_fictif_data else None
    except psycopg2.Error as e:
        db.rollback()
        current_app.logger.error(f"Erreur DAO (create_fictif_enseignant) pour champ {champ_no}: {e}")
        return None


def get_affected_cours_for_enseignant(enseignant_id: int) -> list[str]:
    """Récupère les codes des cours attribués à un enseignant (utile avant suppression)."""
    db = get_db()
    if not db:
        return []
    try:
        with db.cursor() as cur:
            cur.execute("SELECT DISTINCT codecours FROM attributionscours WHERE enseignantid = %s;", (enseignant_id,))
            return [row[0] for row in cur.fetchall()]
    except psycopg2.Error as e:
        current_app.logger.error(f"Erreur DAO (get_affected_cours_for_enseignant) pour ens {enseignant_id}: {e}")
        return []


def delete_enseignant(enseignant_id: int) -> bool:
    """Supprime un enseignant et ses attributions (par CASCADE)."""
    db = get_db()
    if not db:
        return False
    try:
        with db.cursor() as cur:
            cur.execute("DELETE FROM enseignants WHERE enseignantid = %s;", (enseignant_id,))
            db.commit()
            return cur.rowcount > 0
    except psycopg2.Error as e:
        db.rollback()
        current_app.logger.error(f"Erreur DAO (delete_enseignant) pour ens {enseignant_id}: {e}")
        return False


def reassign_cours_to_champ(code_cours: str, nouveau_champ_no: str) -> dict[str, Any] | None:
    """Réassigne un cours à un nouveau champ."""
    db = get_db()
    if not db:
        return None
    try:
        with db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT champnom FROM champs WHERE champno = %s;", (nouveau_champ_no,))
            if not (new_champ := cur.fetchone()):
                current_app.logger.warning(f"Tentative de réassignation de {code_cours} à un champ inexistant: {nouveau_champ_no}")
                return None

            cur.execute("UPDATE cours SET champno = %s WHERE codecours = %s;", (nouveau_champ_no, code_cours))
            if cur.rowcount == 0:
                current_app.logger.warning(f"Cours {code_cours} non trouvé pour réassignation.")
                db.rollback()
                return None

            db.commit()
            return {"nouveau_champ_no": nouveau_champ_no, "nouveau_champ_nom": new_champ["champnom"]}
    except psycopg2.Error as e:
        db.rollback()
        current_app.logger.error(f"Erreur DAO (reassign_cours_to_champ) pour {code_cours} -> {nouveau_champ_no}: {e}")
        return None


# --- Fonctions CRUD pour la gestion manuelle (API d'administration) ---


def create_cours(data: dict[str, Any]) -> dict[str, Any] | None:
    """Crée un nouveau cours. Propage l'exception en cas d'erreur de contrainte (ex: PK déjà existante)."""
    db = get_db()
    if not db:
        return None
    try:
        with db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """
                INSERT INTO cours (codecours, champno, coursdescriptif, nbperiodes, nbgroupeinitial, estcoursautre)
                VALUES (%(codecours)s, %(champno)s, %(coursdescriptif)s, %(nbperiodes)s, %(nbgroupeinitial)s, %(estcoursautre)s)
                RETURNING *;
                """,
                data,
            )
            new_cours = cur.fetchone()
            db.commit()
            return dict(new_cours) if new_cours else None
    except psycopg2.Error as e:
        db.rollback()
        current_app.logger.error(f"Erreur DAO (create_cours): {e}")
        raise  # Propage l'erreur pour une gestion au niveau de l'API (ex: HTTP 409 Conflict)


def get_cours_details(code_cours: str) -> dict[str, Any] | None:
    """Récupère les détails complets d'un cours."""
    db = get_db()
    if not db:
        return None
    try:
        with db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT * FROM cours WHERE codecours = %s;", (code_cours,))
            return dict(row) if (row := cur.fetchone()) else None
    except psycopg2.Error as e:
        current_app.logger.error(f"Erreur DAO (get_cours_details) pour {code_cours}: {e}")
        return None


def update_cours(code_cours: str, data: dict[str, Any]) -> dict[str, Any] | None:
    """Met à jour un cours. Propage l'exception pour gestion par l'API."""
    db = get_db()
    if not db:
        return None
    try:
        with db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """
                UPDATE cours
                SET champno = %(champno)s, coursdescriptif = %(coursdescriptif)s,
                    nbperiodes = %(nbperiodes)s, nbgroupeinitial = %(nbgroupeinitial)s,
                    estcoursautre = %(estcoursautre)s
                WHERE codecours = %(original_codecours)s
                RETURNING *;
                """,
                {**data, "original_codecours": code_cours},
            )
            updated_cours = cur.fetchone()
            db.commit()
            return dict(updated_cours) if updated_cours else None
    except psycopg2.Error as e:
        db.rollback()
        current_app.logger.error(f"Erreur DAO (update_cours) pour {code_cours}: {e}")
        raise


def delete_cours(code_cours: str) -> tuple[bool, str]:
    """
    Supprime un cours. Échoue avec un message clair s'il a des attributions.
    Retourne un tuple (succès, message).
    """
    db = get_db()
    if not db:
        return False, "Erreur de connexion à la base de données."
    try:
        with db.cursor() as cur:
            cur.execute("DELETE FROM cours WHERE codecours = %s;", (code_cours,))
            db.commit()
            if cur.rowcount > 0:
                return True, "Cours supprimé avec succès."
            return False, "Cours non trouvé."
    except psycopg2.errors.ForeignKeyViolation:
        db.rollback()
        msg = "Impossible de supprimer: ce cours est attribué à un ou plusieurs enseignants."
        current_app.logger.warning(f"Échec suppression cours {code_cours}: {msg}")
        return False, msg
    except psycopg2.Error as e:
        db.rollback()
        current_app.logger.error(f"Erreur DAO (delete_cours) pour {code_cours}: {e}")
        return False, "Une erreur de base de données est survenue."


def create_enseignant(data: dict[str, Any]) -> dict[str, Any] | None:
    """Crée un nouvel enseignant (non fictif). Propage l'exception pour gestion par l'API."""
    db = get_db()
    if not db:
        return None
    try:
        with db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            data["nomcomplet"] = f"{data['prenom']} {data['nom']}"
            cur.execute(
                """
                INSERT INTO enseignants (nomcomplet, nom, prenom, champno, esttempsplein, estfictif)
                VALUES (%(nomcomplet)s, %(nom)s, %(prenom)s, %(champno)s, %(esttempsplein)s, FALSE)
                RETURNING *;
                """,
                data,
            )
            new_enseignant = cur.fetchone()
            db.commit()
            return dict(new_enseignant) if new_enseignant else None
    except psycopg2.Error as e:
        db.rollback()
        current_app.logger.error(f"Erreur DAO (create_enseignant): {e}")
        raise


def get_enseignant_details(enseignant_id: int) -> dict[str, Any] | None:
    """Récupère les détails d'un enseignant spécifique."""
    db = get_db()
    if not db:
        return None
    try:
        with db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT * FROM enseignants WHERE enseignantid = %s;", (enseignant_id,))
            return dict(row) if (row := cur.fetchone()) else None
    except psycopg2.Error as e:
        current_app.logger.error(f"Erreur DAO (get_enseignant_details) pour {enseignant_id}: {e}")
        return None


def update_enseignant(enseignant_id: int, data: dict[str, Any]) -> dict[str, Any] | None:
    """Met à jour un enseignant (non fictif). Propage l'exception pour gestion par l'API."""
    db = get_db()
    if not db:
        return None
    try:
        with db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            data["nomcomplet"] = f"{data['prenom']} {data['nom']}"
            cur.execute(
                """
                UPDATE enseignants
                SET nomcomplet = %(nomcomplet)s, nom = %(nom)s, prenom = %(prenom)s,
                    champno = %(champno)s, esttempsplein = %(esttempsplein)s
                WHERE enseignantid = %(enseignantid)s AND estfictif = FALSE
                RETURNING *;
                """,
                {**data, "enseignantid": enseignant_id},
            )
            updated_enseignant = cur.fetchone()
            db.commit()
            return dict(updated_enseignant) if updated_enseignant else None
    except psycopg2.Error as e:
        db.rollback()
        current_app.logger.error(f"Erreur DAO (update_enseignant) pour {enseignant_id}: {e}")
        raise


def get_all_enseignants_grouped_by_champ() -> dict[str, dict[str, Any]]:
    """Récupère tous les enseignants non fictifs, regroupés par champ."""
    db = get_db()
    if not db:
        return {}
    try:
        with db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """
                SELECT e.enseignantid, e.nomcomplet, e.esttempsplein,
                       e.champno, ch.champnom
                FROM enseignants e
                JOIN champs ch ON e.champno = ch.champno
                WHERE e.estfictif = FALSE
                ORDER BY ch.champno, e.nom, e.prenom;
                """
            )
            enseignants_par_champ: dict[str, Any] = {}
            for row in cur.fetchall():
                champ_no = row["champno"]
                if champ_no not in enseignants_par_champ:
                    enseignants_par_champ[champ_no] = {"champ_nom": row["champnom"], "enseignants": []}
                enseignants_par_champ[champ_no]["enseignants"].append(dict(row))
            return enseignants_par_champ
    except psycopg2.Error as e:
        current_app.logger.error(f"Erreur DAO (get_all_enseignants_grouped_by_champ): {e}")
        return {}
