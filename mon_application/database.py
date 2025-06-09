# mon_application/database.py
"""
Ce module gère toutes les interactions avec la base de données PostgreSQL.

Il inclut la configuration de la connexion, les fonctions pour ouvrir et fermer
la connexion dans le contexte de l'application Flask, ainsi que toutes les
fonctions DAO (Data Access Object) pour manipuler les données des utilisateurs,
champs, enseignants, cours et attributions.
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
    """Construit la chaîne de connexion à la base de données à partir des variables d'environnement."""
    return f"dbname='{DB_NAME}' user='{DB_USER}' host='{DB_HOST}' password='{DB_PASS}' port='{DB_PORT}'"


def get_db():
    """
    Ouvre et réutilise une connexion à la base de données pour la durée d'une requête.
    La connexion est stockée dans l'objet 'g' de Flask, qui est propre à chaque requête.
    Si la connexion échoue, elle est journalisée et 'g.db' est défini sur None.
    """
    if "db" not in g:
        try:
            conn_string = get_db_connection_string()
            g.db = psycopg2.connect(conn_string)
        except psycopg2.OperationalError as e:
            current_app.logger.error(f"Erreur de connexion à la base de données: {e}")
            g.db = None  # S'assure que g.db est explicitement None en cas d'échec
    return g.db


def close_db(_exception: BaseException | None = None) -> None:
    """
    Ferme la connexion à la base de données à la fin de la requête (teardown).
    Le paramètre _exception est capturé par Flask mais n'est pas utilisé ici,
    d'où le préfixe underscore pour indiquer qu'il est intentionnellement inutilisé.
    """
    db = g.pop("db", None)
    if db is not None and not db.closed:
        db.close()


def init_app(app: Flask) -> None:
    """
    Initialise la gestion de la base de données pour l'application Flask.
    Enregistre la fonction `close_db` pour qu'elle soit appelée après chaque requête
    afin de garantir que la connexion à la base de données est toujours fermée.
    """
    app.teardown_appcontext(close_db)


# --- Fonctions d'accès aux données (DAO) - Utilisateurs ---


def get_user_by_id(user_id: int) -> dict[str, Any] | None:
    """
    Récupère un utilisateur par son ID, y compris ses permissions d'accès aux champs.
    Retourne un dictionnaire avec toutes les informations de l'utilisateur,
    y compris une liste `allowed_champs` (qui peut être vide si aucune permission).
    Retourne None si l'utilisateur n'est pas trouvé ou en cas d'erreur de base de données.
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
                FROM Users u
                LEFT JOIN user_champ_access uca ON u.id = uca.user_id
                WHERE u.id = %s
                GROUP BY u.id;
                """,
                (user_id,),
            )
            user_data = cur.fetchone()
            if user_data:
                user_dict = dict(user_data)
                # Assure que 'allowed_champs' est une liste, même si elle est vide (au lieu de [None] ou None).
                user_dict["allowed_champs"] = user_dict["allowed_champs"] or []
                return user_dict
            return None
    except psycopg2.Error as e:
        current_app.logger.error(f"Erreur DAO get_user_by_id pour {user_id}: {e}")
        return None


def get_user_by_username(username: str) -> dict[str, Any] | None:
    """
    Récupère un utilisateur par son nom d'utilisateur.
    Retourne un dictionnaire avec les informations de l'utilisateur ou None si non trouvé.
    """
    db = get_db()
    if not db:
        return None
    try:
        with db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT id, username, password_hash, is_admin FROM Users WHERE username = %s;", (username,))
            user_data = cur.fetchone()
            return dict(user_data) if user_data else None
    except psycopg2.Error as e:
        current_app.logger.error(f"Erreur DAO get_user_by_username pour {username}: {e}")
        # Un simple SELECT ne nécessite généralement pas de rollback, car il ne modifie pas l'état de la DB.
        return None


def get_users_count() -> int:
    """
    Compte le nombre total d'utilisateurs dans la base de données.
    Retourne le nombre d'utilisateurs ou 0 en cas d'erreur.
    """
    db = get_db()
    if not db:
        return 0
    try:
        with db.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM Users;")
            # COUNT(*) retourne toujours une ligne; fetchone ne sera pas None dans ce cas.
            result = cur.fetchone()
            return result[0] if result else 0
    except psycopg2.Error as e:
        current_app.logger.error(f"Erreur DAO get_users_count: {e}")
        return 0


def get_admin_count() -> int:
    """
    Compte le nombre total d'utilisateurs avec le statut administrateur (is_admin = TRUE).
    Retourne le nombre d'administrateurs ou 0 en cas d'erreur.
    """
    db = get_db()
    if not db:
        return 0
    try:
        with db.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM Users WHERE is_admin = TRUE;")
            result = cur.fetchone()
            return result[0] if result else 0
    except psycopg2.Error as e:
        current_app.logger.error(f"Erreur DAO get_admin_count: {e}")
        return 0


def create_user(username: str, password_hash: str, is_admin: bool = False) -> dict[str, Any] | None:
    """
    Crée un nouvel utilisateur dans la base de données avec le nom d'utilisateur, le hash du mot de passe
    et le statut administrateur.
    Retourne un dictionnaire avec l'ID, le nom d'utilisateur et le statut admin du nouvel utilisateur,
    ou None si la création échoue (par exemple, nom d'utilisateur déjà existant ou erreur DB).
    """
    db = get_db()
    if not db:
        return None
    try:
        with db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                "INSERT INTO Users (username, password_hash, is_admin) VALUES (%s, %s, %s) RETURNING id, username, is_admin;",
                (username, password_hash, is_admin),
            )
            user_data = cur.fetchone()
            db.commit()
            return dict(user_data) if user_data else None
    except psycopg2.errors.UniqueViolation:
        # Gère le cas où le nom d'utilisateur existe déjà
        db.rollback()
        current_app.logger.warning(f"Tentative de création d'un utilisateur existant: {username}")
        return None
    except psycopg2.Error as e:
        # Gère toutes les autres erreurs de base de données
        current_app.logger.error(f"Erreur DAO create_user pour {username}: {e}")
        db.rollback()
        return None


def get_all_users_with_access_info() -> list[dict[str, Any]]:
    """
    Récupère tous les utilisateurs enregistrés dans la base de données,
    chacun avec la liste des numéros de champs auxquels il a accès.
    Retourne une liste de dictionnaires, chaque dictionnaire représentant un utilisateur.
    La liste `allowed_champs` est garantie d'être présente et une liste (potentiellement vide).
    """
    db = get_db()
    if not db:
        return []
    try:
        with db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """
                SELECT u.id, u.username, u.is_admin,
                       ARRAY_AGG(uca.champ_no ORDER BY uca.champ_no) FILTER (WHERE uca.champ_no IS NOT NULL) AS allowed_champs
                FROM Users u
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
        current_app.logger.error(f"Erreur DAO get_all_users_with_access_info: {e}")
        # Un rollback n'est pas strictement nécessaire pour un SELECT, mais n'est pas nuisible non plus.
        db.rollback()
        return []


def update_user_champ_access(user_id: int, champ_nos: list[str]) -> bool:
    """
    Met à jour les permissions d'accès aux champs pour un utilisateur spécifique.
    Supprime toutes les permissions existantes pour cet utilisateur et insère les nouvelles.
    Retourne True si l'opération réussit, False en cas d'erreur.
    """
    db = get_db()
    if not db:
        return False
    try:
        with db.cursor() as cur:
            # Supprime toutes les attributions de champs existantes pour cet utilisateur
            cur.execute("DELETE FROM user_champ_access WHERE user_id = %s;", (user_id,))
            # Insère les nouvelles attributions de champs, si la liste n'est pas vide
            if champ_nos:
                values = [(user_id, champ_no) for champ_no in champ_nos]
                psycopg2.extras.execute_values(cur, "INSERT INTO user_champ_access (user_id, champ_no) VALUES %s;", values)
            db.commit()
            return True
    except psycopg2.Error as e:
        db.rollback()
        current_app.logger.error(f"Erreur DAO update_user_champ_access pour user {user_id}: {e}")
        return False


def delete_user_data(user_id: int) -> bool:
    """
    Supprime un utilisateur de la base de données par son ID.
    Les accès aux champs associés à cet utilisateur sont supprimés automatiquement par CASCADE.
    Retourne True si l'utilisateur a été supprimé (au moins une ligne affectée), False sinon.
    """
    db = get_db()
    if not db:
        return False
    try:
        with db.cursor() as cur:
            cur.execute("DELETE FROM Users WHERE id = %s;", (user_id,))
            db.commit()
            return cur.rowcount > 0  # Retourne True si une ligne a été supprimée
    except psycopg2.Error as e:
        db.rollback()
        current_app.logger.error(f"Erreur DAO delete_user_data pour user {user_id}: {e}")
        return False


# --- Fonctions d'accès aux données (DAO) - Champs, Enseignants, Cours, Attributions ---


def get_all_champs() -> list[dict[str, Any]]:
    """
    Récupère tous les champs disponibles dans la base de données, triés par leur numéro de champ.
    Retourne une liste de dictionnaires, chacun représentant un champ.
    """
    db = get_db()
    if not db:
        return []
    try:
        with db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT ChampNo, ChampNom, EstVerrouille FROM Champs ORDER BY ChampNo;")
            return [dict(row) for row in cur.fetchall()]
    except psycopg2.Error as e:
        current_app.logger.error(f"Erreur DAO get_all_champs: {e}")
        db.rollback()  # Un rollback est généralement prudent après une erreur, même pour un SELECT.
        return []


def get_champ_details(champ_no: str) -> dict[str, Any] | None:
    """
    Récupère les détails d'un champ spécifique par son numéro de champ.
    Retourne un dictionnaire avec les détails du champ ou None si non trouvé.
    """
    db = get_db()
    if not db:
        return None
    try:
        with db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT ChampNo, ChampNom, EstVerrouille FROM Champs WHERE ChampNo = %s;", (champ_no,))
            return dict(row) if (row := cur.fetchone()) else None
    except psycopg2.Error as e:
        current_app.logger.error(f"Erreur DAO get_champ_details pour {champ_no}: {e}")
        db.rollback()
        return None


def get_enseignants_par_champ(champ_no: str) -> list[dict[str, Any]]:
    """
    Récupère tous les enseignants associés à un champ spécifique,
    triés par leur statut (fictif/réel) puis par nom et prénom.
    Retourne une liste de dictionnaires, chacun représentant un enseignant.
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
        current_app.logger.error(f"Erreur DAO get_enseignants_par_champ pour {champ_no}: {e}")
        db.rollback()
        return []


def get_enseignant_champ_no(enseignant_id: int) -> str | None:
    """
    Récupère le numéro de champ principal d'un enseignant par son ID.
    Retourne le numéro de champ sous forme de chaîne ou None si l'enseignant n'est pas trouvé.
    """
    db = get_db()
    if not db:
        return None
    try:
        with db.cursor() as cur:
            cur.execute("SELECT ChampNo FROM Enseignants WHERE EnseignantID = %s;", (enseignant_id,))
            result = cur.fetchone()
            return result[0] if result else None
    except psycopg2.Error as e:
        current_app.logger.error(f"Erreur DAO get_enseignant_champ_no pour {enseignant_id}: {e}")
        return None


def get_all_enseignants_avec_details() -> list[dict[str, Any]]:
    """
    Récupère tous les enseignants avec des détails enrichis, incluant les informations
    de leur champ et les périodes calculées à partir de leurs attributions.
    Cela prépare les données pour un affichage sommaire ou des calculs globaux.
    Retourne une liste de dictionnaires, chacun représentant un enseignant complet.
    """
    db = get_db()
    if not db:
        return []
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

        # Récupère toutes les attributions en une seule fois pour optimiser
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
        current_app.logger.error(f"Erreur DAO get_all_enseignants_avec_details: {e}")
        db.rollback()
        return []


def get_cours_disponibles_par_champ(champ_no: str) -> list[dict[str, Any]]:
    """
    Récupère les cours associés à un champ spécifique, en calculant le nombre
    de groupes restants. Un cours assigné à un enseignant fictif (tâche restante)
    est toujours considéré comme disponible.
    Retourne une liste de dictionnaires, chacun représentant un cours.
    """
    db = get_db()
    if not db:
        return []
    try:
        with db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            # CORRECTION : Seules les attributions à des enseignants NON fictifs
            # sont soustraites pour calculer les groupes restants.
            cur.execute(
                """
                SELECT
                    c.CodeCours, c.CoursDescriptif, c.NbPeriodes, c.EstCoursAutre, c.NbGroupeInitial,
                    (c.NbGroupeInitial - COALESCE(SUM(ac.NbGroupesPris) FILTER (WHERE e.EstFictif = FALSE), 0)) AS grprestant
                FROM Cours c
                LEFT JOIN AttributionsCours ac ON c.CodeCours = ac.CodeCours
                LEFT JOIN Enseignants e ON ac.EnseignantID = e.EnseignantID
                WHERE c.ChampNo = %s
                GROUP BY c.CodeCours
                ORDER BY c.EstCoursAutre, c.CodeCours;
                """,
                (champ_no,),
            )
            return [dict(cr) for cr in cur.fetchall()]
    except psycopg2.Error as e:
        current_app.logger.error(f"Erreur DAO get_cours_disponibles_par_champ pour {champ_no}: {e}")
        db.rollback()
        return []


def get_attributions_enseignant(enseignant_id: int) -> list[dict[str, Any]]:
    """
    Récupère toutes les attributions de cours pour un enseignant spécifique.
    Inclut des détails sur le cours (description, périodes, type).
    Retourne une liste de dictionnaires, chacune représentant une attribution.
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
        current_app.logger.error(f"Erreur DAO get_attributions_enseignant pour {enseignant_id}: {e}")
        db.rollback()
        return []


def get_toutes_les_attributions() -> list[dict[str, Any]]:
    """
    Récupère toutes les attributions de cours présentes dans la base de données.
    Utilisée principalement pour des calculs de masse ou des sommaires.
    Retourne une liste de dictionnaires, chacune représentant une attribution.
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
        current_app.logger.error(f"Erreur DAO get_toutes_les_attributions: {e}")
        db.rollback()
        return []


def calculer_periodes_pour_attributions(attributions: list[dict[str, Any]]) -> dict[str, float]:
    """
    Calcule les totaux de périodes (cours réguliers, autres activités et total général)
    à partir d'une liste d'attributions fournie.
    Cette fonction est pure et ne fait pas d'appels à la base de données.
    """
    periodes_cours = sum(float(a["nbperiodes"]) * a["nbgroupespris"] for a in attributions if not a["estcoursautre"])
    periodes_autres = sum(float(a["nbperiodes"]) * a["nbgroupespris"] for a in attributions if a["estcoursautre"])
    return {
        "periodes_cours": periodes_cours,
        "periodes_autres": periodes_autres,
        "total_periodes": periodes_cours + periodes_autres,
    }


def calculer_periodes_enseignant(enseignant_id: int) -> dict[str, float]:
    """
    Calcule les totaux de périodes pour un enseignant spécifique en interrogeant la base de données
    pour ses attributions, puis en utilisant `calculer_periodes_pour_attributions`.
    """
    attributions = get_attributions_enseignant(enseignant_id)
    return calculer_periodes_pour_attributions(attributions)


def get_groupes_restants_pour_cours(code_cours: str) -> int:
    """
    Calcule le nombre de groupes restants disponibles pour un cours donné,
    en soustrayant TOUS les groupes déjà attribués.
    Retourne le nombre de groupes restants ou 0 en cas d'erreur ou si le cours n'existe pas.
    """
    db = get_db()
    if not db:
        return 0
    try:
        with db.cursor() as cur:
            # CORRECTION: Suppression du "FILTER" et de la jointure sur Enseignants qui est maintenant inutile ici.
            # On compte toutes les attributions pour ce cours.
            cur.execute(
                """
                SELECT (c.NbGroupeInitial - COALESCE(SUM(ac.NbGroupesPris), 0))
                FROM Cours c
                LEFT JOIN AttributionsCours ac ON c.CodeCours = ac.CodeCours
                WHERE c.CodeCours = %s
                GROUP BY c.CodeCours;
                """,
                (code_cours,),
            )
            result = cur.fetchone()
            # Si result est None (cours non trouvé) ou le calcul est None, retourne 0.
            return int(result[0]) if result and result[0] is not None else 0
    except psycopg2.Error as e:
        current_app.logger.error(f"Erreur DAO get_groupes_restants_pour_cours pour {code_cours}: {e}")
        db.rollback()
        return 0


def get_all_cours_avec_details_champ() -> list[dict[str, Any]]:
    """
    Récupère tous les cours avec les détails de leur champ d'origine (numéro et nom).
    Utilisé pour des listes globales de cours, par exemple dans une interface d'administration.
    Retourne une liste de dictionnaires, chacun représentant un cours avec ses détails.
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
        current_app.logger.error(f"Erreur DAO get_all_cours_avec_details_champ: {e}")
        db.rollback()
        return []


def toggle_champ_lock_status(champ_no: str) -> bool | None:
    """
    Bascule le statut de verrouillage d'un champ (de verrouillé à déverrouillé, ou vice-versa).
    Retourne le nouvel état de verrouillage (True pour verrouillé, False pour déverrouillé)
    ou None si le champ n'existe pas ou en cas d'erreur.
    """
    db = get_db()
    if not db:
        return None
    try:
        with db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("UPDATE Champs SET EstVerrouille = NOT EstVerrouille WHERE ChampNo = %s RETURNING EstVerrouille;", (champ_no,))
            result = cur.fetchone()
            db.commit()
            return result["estverrouille"] if result else None
    except psycopg2.Error as e:
        db.rollback()
        current_app.logger.error(f"Erreur DAO toggle_champ_lock_status pour {champ_no}: {e}")
        return None


def get_verrou_info_enseignant(enseignant_id: int) -> dict[str, Any] | None:
    """
    Récupère le statut de verrouillage du champ principal de l'enseignant et si l'enseignant est fictif.
    Ces informations sont cruciales pour déterminer si des modifications sont autorisées.
    Retourne un dictionnaire avec 'estfictif' et 'estverrouille' ou None si l'enseignant n'est pas trouvé.
    """
    db = get_db()
    if not db:
        return None
    try:
        with db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """
                SELECT e.EstFictif, ch.EstVerrouille FROM Enseignants e
                JOIN Champs ch ON e.ChampNo = ch.ChampNo WHERE e.EnseignantID = %s;
                """,
                (enseignant_id,),
            )
            return dict(row) if (row := cur.fetchone()) else None
    except psycopg2.Error as e:
        current_app.logger.error(f"Erreur DAO get_verrou_info_enseignant pour {enseignant_id}: {e}")
        return None


def add_attribution(enseignant_id: int, code_cours: str) -> int | None:
    """
    Ajoute une nouvelle attribution de cours à un enseignant, avec un groupe.
    Retourne l'ID de la nouvelle attribution ou None en cas d'échec.
    """
    db = get_db()
    if not db:
        return None
    try:
        with db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                "INSERT INTO AttributionsCours (EnseignantID, CodeCours, NbGroupesPris) VALUES (%s, %s, 1) RETURNING AttributionID;",
                (enseignant_id, code_cours),
            )
            new_id = cur.fetchone()
            db.commit()
            return new_id["attributionid"] if new_id else None
    except psycopg2.Error as e:
        db.rollback()
        current_app.logger.error(f"Erreur DAO add_attribution pour enseignant {enseignant_id}, cours {code_cours}: {e}")
        return None


def get_attribution_info(attribution_id: int) -> dict[str, Any] | None:
    """
    Récupère les informations détaillées d'une attribution spécifique,
    y compris si l'enseignant est fictif, si le champ est verrouillé, et le champ de l'enseignant.
    Ces informations sont utilisées pour valider les suppressions d'attributions.
    Retourne un dictionnaire avec ces informations ou None si l'attribution n'existe pas.
    """
    db = get_db()
    if not db:
        return None
    try:
        with db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """
                SELECT ac.EnseignantID, ac.CodeCours, e.EstFictif, ch.EstVerrouille, e.ChampNo
                FROM AttributionsCours ac
                JOIN Enseignants e ON ac.EnseignantID = e.EnseignantID
                JOIN Champs ch ON e.ChampNo = ch.ChampNo
                WHERE ac.AttributionID = %s;
                """,
                (attribution_id,),
            )
            return dict(row) if (row := cur.fetchone()) else None
    except psycopg2.Error as e:
        current_app.logger.error(f"Erreur DAO get_attribution_info pour attribution {attribution_id}: {e}")
        return None


def delete_attribution(attribution_id: int) -> bool:
    """
    Supprime une attribution de cours de la base de données.
    Retourne True si l'attribution a été supprimée, False sinon.
    """
    db = get_db()
    if not db:
        return False
    try:
        with db.cursor() as cur:
            cur.execute("DELETE FROM AttributionsCours WHERE AttributionID = %s;", (attribution_id,))
            db.commit()
            return cur.rowcount > 0
    except psycopg2.Error as e:
        db.rollback()
        current_app.logger.error(f"Erreur DAO delete_attribution pour attribution {attribution_id}: {e}")
        return False


def create_fictif_enseignant(champ_no: str) -> dict[str, Any] | None:
    """
    Crée un nouvel enseignant fictif (représentant la "tâche restante") pour un champ donné.
    Le nom de l'enseignant fictif est généré dynamiquement pour être unique.
    Retourne un dictionnaire avec les détails du nouvel enseignant fictif créé, ou None en cas d'erreur.
    """
    db = get_db()
    if not db:
        return None
    try:
        with db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            # Recherche des noms existants pour déterminer le prochain numéro séquentiel
            cur.execute(
                "SELECT NomComplet FROM Enseignants WHERE ChampNo = %s AND EstFictif = TRUE AND NomComplet LIKE %s;",
                (champ_no, f"{champ_no}-Tâche restante-%"),
            )
            # Extrait les numéros suffixés des noms existants et trouve le plus grand
            numeros = [int(row["nomcomplet"].split("-")[-1]) for row in cur.fetchall() if row["nomcomplet"].split("-")[-1].isdigit()]
            next_num = max(numeros) + 1 if numeros else 1
            nom_tache = f"{champ_no}-Tâche restante-{next_num}"

            # Insère le nouvel enseignant fictif
            cur.execute(
                """
                INSERT INTO Enseignants (NomComplet, ChampNo, EstTempsPlein, EstFictif) VALUES (%s, %s, TRUE, TRUE)
                RETURNING EnseignantID, NomComplet, Nom, Prenom, EstTempsPlein, EstFictif, PeutChoisirHorsChampPrincipal, ChampNo;
                """,
                (nom_tache, champ_no),
            )
            new_fictif_data = cur.fetchone()
            db.commit()
            return dict(new_fictif_data) if new_fictif_data else None
    except psycopg2.Error as e:
        db.rollback()
        current_app.logger.error(f"Erreur DAO create_fictif_enseignant pour champ {champ_no}: {e}")
        return None


def get_affected_cours_for_enseignant(enseignant_id: int) -> list[str]:
    """
    Récupère les codes des cours qui sont actuellement attribués à un enseignant.
    Cette fonction est utile avant la suppression d'un enseignant pour savoir quels cours
    pourraient potentiellement avoir besoin d'être réassignés.
    Retourne une liste de chaînes de caractères (codes de cours).
    """
    db = get_db()
    if not db:
        return []
    try:
        with db.cursor() as cur:
            cur.execute("SELECT DISTINCT CodeCours FROM AttributionsCours WHERE EnseignantID = %s;", (enseignant_id,))
            return [row[0] for row in cur.fetchall()]
    except psycopg2.Error as e:
        current_app.logger.error(f"Erreur DAO get_affected_cours_for_enseignant pour enseignant {enseignant_id}: {e}")
        return []


def delete_enseignant(enseignant_id: int) -> bool:
    """
    Supprime un enseignant de la base de données par son ID.
    Les attributions de cours associées à cet enseignant sont supprimées automatiquement
    par la contrainte CASCADE de la base de données.
    Retourne True si l'enseignant a été supprimé (au moins une ligne affectée), False sinon.
    """
    db = get_db()
    if not db:
        return False
    try:
        with db.cursor() as cur:
            cur.execute("DELETE FROM Enseignants WHERE EnseignantID = %s;", (enseignant_id,))
            db.commit()
            return cur.rowcount > 0
    except psycopg2.Error as e:
        db.rollback()
        current_app.logger.error(f"Erreur DAO delete_enseignant pour enseignant {enseignant_id}: {e}")
        return False


def reassign_cours_to_champ(code_cours: str, nouveau_champ_no: str) -> dict[str, Any] | None:
    """
    Réassigne un cours existant à un nouveau champ.
    Retourne un dictionnaire avec le nouveau numéro et nom de champ si la réaffectation réussit,
    ou None si le cours ou le nouveau champ n'existe pas, ou en cas d'erreur.
    """
    db = get_db()
    if not db:
        return None
    try:
        with db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            # Vérifie si le champ de destination existe
            cur.execute("SELECT ChampNom FROM Champs WHERE ChampNo = %s;", (nouveau_champ_no,))
            new_champ = cur.fetchone()
            if not new_champ:
                current_app.logger.warning(f"Tentative de réaffectation du cours {code_cours} vers un champ inexistant: {nouveau_champ_no}")
                return None  # Le champ de destination n'existe pas

            # Met à jour le champ du cours
            cur.execute("UPDATE Cours SET ChampNo = %s WHERE CodeCours = %s;", (nouveau_champ_no, code_cours))
            if cur.rowcount == 0:
                # Le cours n'existe peut-être pas
                current_app.logger.warning(f"Cours {code_cours} non trouvé pour réaffectation au champ {nouveau_champ_no}.")
                db.rollback()  # Aucune modification n'a eu lieu, mais un rollback ne coûte rien
                return None

            db.commit()

            return {
                "nouveau_champ_no": nouveau_champ_no,
                "nouveau_champ_nom": new_champ["champnom"],
            }
    except psycopg2.Error as e:
        db.rollback()
        current_app.logger.error(f"Erreur DAO reassign_cours_to_champ pour cours {code_cours} vers champ {nouveau_champ_no}: {e}")
        return None
