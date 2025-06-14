# mon_application/database.py
"""
Ce module gère toutes les interactions avec la base de données PostgreSQL.

Il inclut la configuration de la connexion, qui s'adapte à l'environnement
(production ou développement) via la variable d'environnement APP_ENV.
Il contient aussi les fonctions pour gérer le cycle de vie de la connexion
dans le contexte de l'application Flask, ainsi que toutes les fonctions DAO
(Data Access Object) pour manipuler les données.
"""

import os
from collections import defaultdict
from typing import Any

import psycopg2
import psycopg2.extras
import psycopg2.sql
from flask import Flask, current_app, g

# --- Gestion de la connexion à la base de données ---


def get_db_connection_string() -> str:
    """
    Construit la chaîne de connexion à la base de données en fonction de l'environnement.

    Utilise la variable d'environnement 'APP_ENV'. Si 'APP_ENV' est 'production',
    il utilise les variables préfixées par 'PROD_'. Sinon, il utilise par défaut
    les variables préfixées par 'DEV_' pour l'environnement de développement.

    Returns:
        La chaîne de connexion pour psycopg2, ou une chaîne vide si les
        informations de connexion requises sont manquantes.
    """
    app_env = os.environ.get("APP_ENV", "development")

    prefix = "PROD_" if app_env == "production" else "DEV_"

    if current_app:
        # Log l'environnement utilisé pour la clarté lors du débogage
        current_app.logger.info(
            "Configuration de la base de données pour l'environnement : "
            f"{app_env.upper()}"
        )

    db_host = os.environ.get(f"{prefix}PGHOST")
    db_name = os.environ.get(f"{prefix}PGDATABASE")
    db_user = os.environ.get(f"{prefix}PGUSER")
    db_pass = os.environ.get(f"{prefix}PGPASSWORD")
    db_port = os.environ.get(f"{prefix}PGPORT", "5432")

    # Vérification critique que les variables nécessaires sont définies
    if not all([db_host, db_name, db_user, db_pass]):
        missing_vars = [
            var
            for var, val in {
                f"{prefix}PGHOST": db_host,
                f"{prefix}PGDATABASE": db_name,
                f"{prefix}PGUSER": db_user,
                f"{prefix}PGPASSWORD": db_pass,
            }.items()
            if not val
        ]
        log_message = (
            "Variables de connexion à la base de données manquantes pour "
            f"l'environnement '{app_env}': {', '.join(missing_vars)}"
        )
        if current_app:
            current_app.logger.critical(log_message)
        # Retourner une chaîne vide provoquera une erreur contrôlée dans get_db
        return ""

    return (
        f"dbname='{db_name}' user='{db_user}' host='{db_host}' "
        f"password='{db_pass}' port='{db_port}'"
    )


def get_db() -> psycopg2.extensions.connection | None:
    """Ouvre et réutilise une connexion à la base de données pour la durée d'une requête."""
    if "db" not in g:
        try:
            conn_string = get_db_connection_string()
            if not conn_string:
                # Si la chaîne de connexion est vide, les logs critiques ont déjà été émis.
                # On empêche la tentative de connexion.
                g.db = None
                return None
            g.db = psycopg2.connect(conn_string)
        except psycopg2.OperationalError as e:
            if current_app:
                current_app.logger.error(f"Erreur de connexion à la base de données: {e}")
            g.db = None
    return g.db


def close_db(_exception: BaseException | None = None) -> None:
    """Ferme la connexion à la base de données à la fin de la requête (teardown)."""
    db_conn = g.pop("db", None)
    if db_conn is not None and not db_conn.closed:
        db_conn.close()


def init_app(app: Flask) -> None:
    """Initialise la gestion de la base de données pour l'application Flask."""
    # Enregistre close_db pour qu'elle soit appelée à la fin de chaque requête.
    app.teardown_appcontext(close_db)


# --- Fonctions d'accès aux données (DAO) - Années Scolaires ---


def get_all_annees() -> list[dict[str, Any]]:
    """Récupère toutes les années scolaires, ordonnées par libellé décroissant (plus récent en premier)."""
    db_conn = get_db()
    if not db_conn:
        return []
    try:
        with db_conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                "SELECT annee_id, libelle_annee, est_courante "
                "FROM anneesscolaires ORDER BY libelle_annee DESC;"
            )
            return [dict(row) for row in cur.fetchall()]
    except psycopg2.Error as e:
        current_app.logger.error(f"Erreur DAO get_all_annees: {e}")
        return []


def get_annee_courante() -> dict[str, Any] | None:
    """Récupère l'année scolaire marquée comme courante."""
    db_conn = get_db()
    if not db_conn:
        return None
    try:
        with db_conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                "SELECT annee_id, libelle_annee, est_courante "
                "FROM anneesscolaires WHERE est_courante = TRUE;"
            )
            return dict(row) if (row := cur.fetchone()) else None
    except psycopg2.Error as e:
        current_app.logger.error(f"Erreur DAO get_annee_courante: {e}")
        return None


def create_annee_scolaire(libelle: str) -> dict[str, Any] | None:
    """Crée une nouvelle année scolaire."""
    db_conn = get_db()
    if not db_conn:
        return None
    try:
        with db_conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                "INSERT INTO anneesscolaires (libelle_annee) VALUES (%s) "
                "RETURNING annee_id, libelle_annee, est_courante;",
                (libelle,),
            )
            new_annee = cur.fetchone()
            db_conn.commit()
            return dict(new_annee) if new_annee else None
    except psycopg2.errors.UniqueViolation:
        db_conn.rollback()
        current_app.logger.warning(
            f"Tentative de création d'une année scolaire existante: {libelle}"
        )
        return None
    except psycopg2.Error as e:
        db_conn.rollback()
        current_app.logger.error(f"Erreur DAO create_annee_scolaire: {e}")
        return None


def set_annee_courante(annee_id: int) -> bool:
    """Définit une année scolaire comme courante, en s'assurant que toutes les autres ne le sont pas."""
    db_conn = get_db()
    if not db_conn:
        return False
    try:
        with db_conn.cursor() as cur:
            # Transaction pour assurer l'atomicité
            cur.execute("UPDATE anneesscolaires SET est_courante = FALSE;")
            cur.execute(
                "UPDATE anneesscolaires SET est_courante = TRUE WHERE annee_id = %s;",
                (annee_id,),
            )
            db_conn.commit()
            return cur.rowcount > 0
    except psycopg2.Error as e:
        db_conn.rollback()
        current_app.logger.error(
            f"Erreur DAO set_annee_courante pour annee_id {annee_id}: {e}"
        )
        return False


# --- Fonctions d'accès aux données (DAO) - Utilisateurs ---


def get_user_by_id(user_id: int) -> dict[str, Any] | None:
    """Récupère un utilisateur par son ID, y compris ses permissions d'accès aux champs."""
    db_conn = get_db()
    if not db_conn:
        return None
    try:
        with db_conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """
                SELECT u.id, u.username, u.password_hash, u.is_admin, u.is_dashboard_only,
                       ARRAY_AGG(uca.champ_no ORDER BY uca.champ_no)
                           FILTER (WHERE uca.champ_no IS NOT NULL) AS allowed_champs
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
                # S'assure que allowed_champs est une liste, même si ARRAY_AGG retourne NULL.
                user_dict["allowed_champs"] = user_dict["allowed_champs"] or []
                return user_dict
            return None
    except psycopg2.Error as e:
        current_app.logger.error(f"Erreur DAO get_user_by_id pour {user_id}: {e}")
        return None


def get_user_by_username(username: str) -> dict[str, Any] | None:
    """Récupère un utilisateur par son nom d'utilisateur."""
    db_conn = get_db()
    if not db_conn:
        return None
    try:
        with db_conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                "SELECT id, username, password_hash, is_admin, is_dashboard_only "
                "FROM Users WHERE username = %s;",
                (username,),
            )
            user_data = cur.fetchone()
            return dict(user_data) if user_data else None
    except psycopg2.Error as e:
        current_app.logger.error(
            f"Erreur DAO get_user_by_username pour {username}: {e}"
        )
        return None


def get_users_count() -> int:
    """Compte le nombre total d'utilisateurs."""
    db_conn = get_db()
    if not db_conn:
        return 0
    try:
        with db_conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM Users;")
            result = cur.fetchone()
            return result[0] if result else 0
    except psycopg2.Error as e:
        current_app.logger.error(f"Erreur DAO get_users_count: {e}")
        return 0


def get_admin_count() -> int:
    """Compte le nombre total d'administrateurs."""
    db_conn = get_db()
    if not db_conn:
        return 0
    try:
        with db_conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM Users WHERE is_admin = TRUE;")
            result = cur.fetchone()
            return result[0] if result else 0
    except psycopg2.Error as e:
        current_app.logger.error(f"Erreur DAO get_admin_count: {e}")
        return 0


def create_user(
    username: str,
    password_hash: str,
    is_admin: bool = False,
    is_dashboard_only: bool = False,
) -> dict[str, Any] | None:
    """Crée un nouvel utilisateur avec un rôle spécifique."""
    db_conn = get_db()
    if not db_conn:
        return None
    try:
        with db_conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                "INSERT INTO Users (username, password_hash, is_admin, is_dashboard_only) "
                "VALUES (%s, %s, %s, %s) RETURNING id, username, is_admin, is_dashboard_only;",
                (username, password_hash, is_admin, is_dashboard_only),
            )
            user_data = cur.fetchone()
            db_conn.commit()
            return dict(user_data) if user_data else None
    except psycopg2.errors.UniqueViolation:
        db_conn.rollback()
        return None
    except psycopg2.Error as e:
        db_conn.rollback()
        current_app.logger.error(f"Erreur DAO create_user pour {username}: {e}")
        return None


def get_all_users_with_access_info() -> list[dict[str, Any]]:
    """Récupère tous les utilisateurs avec leurs accès."""
    db_conn = get_db()
    if not db_conn:
        return []
    try:
        with db_conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """
                SELECT u.id, u.username, u.is_admin, u.is_dashboard_only,
                       ARRAY_AGG(uca.champ_no ORDER BY uca.champ_no)
                           FILTER (WHERE uca.champ_no IS NOT NULL) AS allowed_champs
                FROM Users u
                LEFT JOIN user_champ_access uca ON u.id = uca.user_id
                GROUP BY u.id
                ORDER BY u.username;
                """
            )
            users_data = []
            for row in cur.fetchall():
                user_dict = dict(row)
                # S'assure que allowed_champs est une liste, même si ARRAY_AGG retourne NULL.
                user_dict["allowed_champs"] = user_dict["allowed_champs"] or []
                users_data.append(user_dict)
            return users_data
    except psycopg2.Error as e:
        current_app.logger.error(f"Erreur DAO get_all_users_with_access_info: {e}")
        return []


def update_user_role_and_access(
    user_id: int,
    is_admin: bool,
    is_dashboard_only: bool,
    allowed_champs: list[str],
) -> bool:
    """
    Met à jour le rôle et les accès d'un utilisateur de manière transactionnelle.

    Cette fonction garantit que la mise à jour des rôles et des accès aux champs
    est atomique. Si le rôle est admin ou dashboard_only, les accès aux champs
    sont supprimés. Sinon, ils sont mis à jour selon la liste fournie.
    """
    db_conn = get_db()
    if not db_conn:
        return False
    try:
        with db_conn.cursor() as cur:
            # Mettre à jour les booléens de rôle pour l'utilisateur.
            cur.execute(
                "UPDATE Users SET is_admin = %s, is_dashboard_only = %s WHERE id = %s;",
                (is_admin, is_dashboard_only, user_id),
            )

            # Supprimer les anciens accès pour garantir un état propre.
            cur.execute("DELETE FROM user_champ_access WHERE user_id = %s;", (user_id,))

            # Si l'utilisateur est un utilisateur standard avec des accès spécifiques,
            # les insérer. Sinon, la table des accès reste vide pour cet utilisateur.
            if not is_admin and not is_dashboard_only and allowed_champs:
                psycopg2.extras.execute_values(
                    cur,
                    "INSERT INTO user_champ_access (user_id, champ_no) VALUES %s;",
                    [(user_id, c) for c in allowed_champs],
                )

            db_conn.commit()
            return True
    except psycopg2.Error as e:
        db_conn.rollback()
        current_app.logger.error(
            f"Erreur DAO update_user_role_and_access pour user {user_id}: {e}"
        )
        return False


def delete_user_data(user_id: int) -> bool:
    """Supprime un utilisateur."""
    db_conn = get_db()
    if not db_conn:
        return False
    try:
        with db_conn.cursor() as cur:
            cur.execute("DELETE FROM Users WHERE id = %s;", (user_id,))
            db_conn.commit()
            return cur.rowcount > 0
    except psycopg2.Error as e:
        db_conn.rollback()
        current_app.logger.error(f"Erreur DAO delete_user_data pour user {user_id}: {e}")
        return False


# --- Fonctions d'accès aux données (DAO) - Champs ---


def get_all_champs() -> list[dict[str, Any]]:
    """Récupère tous les champs, triés par leur numéro."""
    db_conn = get_db()
    if not db_conn:
        return []
    try:
        with db_conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT ChampNo, ChampNom FROM Champs ORDER BY ChampNo;")
            return [dict(row) for row in cur.fetchall()]
    except psycopg2.Error as e:
        current_app.logger.error(f"Erreur DAO get_all_champs: {e}")
        return []


def get_champ_details(champ_no: str, annee_id: int) -> dict[str, Any] | None:
    """Récupère les détails d'un champ et ses statuts pour une année donnée."""
    db_conn = get_db()
    if not db_conn:
        return None
    try:
        with db_conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """
                SELECT
                    ch.ChampNo,
                    ch.ChampNom,
                    COALESCE(cas.est_verrouille, FALSE) AS est_verrouille,
                    COALESCE(cas.est_confirme, FALSE) AS est_confirme
                FROM Champs ch
                LEFT JOIN champ_annee_statuts cas
                    ON ch.ChampNo = cas.champ_no AND cas.annee_id = %s
                WHERE ch.ChampNo = %s;
                """,
                (annee_id, champ_no),
            )
            return dict(row) if (row := cur.fetchone()) else None
    except psycopg2.Error as e:
        current_app.logger.error(
            f"Erreur DAO get_champ_details pour {champ_no}, annee {annee_id}: {e}"
        )
        return None


def get_all_champ_statuses_for_year(annee_id: int) -> dict[str, dict[str, bool]]:
    """
    Récupère les statuts (verrouillé/confirmé) de tous les champs pour une année.

    Args:
        annee_id: L'ID de l'année scolaire.

    Returns:
        Un dictionnaire mappant champ_no à un dictionnaire de ses statuts.
        Ex: {"10A": {"est_verrouille": True, "est_confirme": False}, ...}
    """
    db_conn = get_db()
    if not db_conn:
        return {}
    statuses = {}
    try:
        with db_conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """
                SELECT champ_no, est_verrouille, est_confirme
                FROM champ_annee_statuts
                WHERE annee_id = %s;
                """,
                (annee_id,),
            )
            for row in cur.fetchall():
                statuses[row["champ_no"]] = {
                    "est_verrouille": row["est_verrouille"],
                    "est_confirme": row["est_confirme"],
                }
        return statuses
    except psycopg2.Error as e:
        current_app.logger.error(
            "Erreur DAO get_all_champ_statuses_for_year pour annee "
            f"{annee_id}: {e}"
        )
        return {}


def _toggle_champ_annee_status(
    champ_no: str, annee_id: int, status_column: str
) -> bool | None:
    """
    Fonction utilitaire pour basculer un statut booléen pour un champ/année.

    Crée l'entrée dans champ_annee_statuts si elle n'existe pas (UPSERT).

    Args:
        champ_no: Le numéro du champ.
        annee_id: L'ID de l'année scolaire.
        status_column: Le nom de la colonne à basculer ('est_verrouille' ou 'est_confirme').

    Returns:
        Le nouvel état du statut (bool) ou None en cas d'erreur.
    """
    db_conn = get_db()
    if not db_conn:
        return None
    if status_column not in ("est_verrouille", "est_confirme"):
        current_app.logger.error(
            f"Tentative de basculer une colonne de statut invalide: {status_column}"
        )
        return None

    try:
        with db_conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            query = psycopg2.sql.SQL(
                """
                INSERT INTO champ_annee_statuts (champ_no, annee_id, {col})
                VALUES (%s, %s, TRUE)
                ON CONFLICT (champ_no, annee_id)
                DO UPDATE SET {col} = NOT champ_annee_statuts.{col}
                RETURNING {col};
                """
            ).format(col=psycopg2.sql.Identifier(status_column))

            cur.execute(query, (champ_no, annee_id))
            result = cur.fetchone()
            db_conn.commit()
            return result[status_column] if result else None
    except psycopg2.Error as e:
        db_conn.rollback()
        current_app.logger.error(
            "Erreur DAO _toggle_champ_annee_status pour "
            f"{champ_no}, annee {annee_id}: {e}"
        )
        return None


def toggle_champ_annee_lock_status(champ_no: str, annee_id: int) -> bool | None:
    """Bascule le statut de verrouillage d'un champ pour une année donnée."""
    return _toggle_champ_annee_status(champ_no, annee_id, "est_verrouille")


def toggle_champ_annee_confirm_status(champ_no: str, annee_id: int) -> bool | None:
    """Bascule le statut de confirmation d'un champ pour une année donnée."""
    return _toggle_champ_annee_status(champ_no, annee_id, "est_confirme")


# --- Fonctions DAO - Types de Financement ---


def get_all_financements() -> list[dict[str, Any]]:
    """Récupère tous les types de financement, triés par code."""
    db_conn = get_db()
    if not db_conn:
        return []
    try:
        with db_conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT code, libelle FROM typesfinancement ORDER BY code;")
            return [dict(row) for row in cur.fetchall()]
    except psycopg2.Error as e:
        current_app.logger.error(f"Erreur DAO get_all_financements: {e}")
        return []


def create_financement(code: str, libelle: str) -> dict[str, Any] | None:
    """Crée un nouveau type de financement."""
    db_conn = get_db()
    if not db_conn:
        return None
    try:
        with db_conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                "INSERT INTO typesfinancement (code, libelle) VALUES (%s, %s) RETURNING *;",
                (code, libelle),
            )
            new_financement = cur.fetchone()
            db_conn.commit()
            return dict(new_financement) if new_financement else None
    except psycopg2.Error:
        db_conn.rollback()
        raise


def update_financement(code: str, libelle: str) -> dict[str, Any] | None:
    """Met à jour le libellé d'un type de financement (le code est immuable)."""
    db_conn = get_db()
    if not db_conn:
        return None
    try:
        with db_conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                "UPDATE typesfinancement SET libelle = %s WHERE code = %s RETURNING *;",
                (libelle, code),
            )
            updated_financement = cur.fetchone()
            db_conn.commit()
            return dict(updated_financement) if updated_financement else None
    except psycopg2.Error:
        db_conn.rollback()
        raise


def delete_financement(code: str) -> tuple[bool, str]:
    """Supprime un type de financement."""
    db_conn = get_db()
    if not db_conn:
        return False, "Erreur de connexion."
    try:
        with db_conn.cursor() as cur:
            cur.execute("DELETE FROM typesfinancement WHERE code = %s;", (code,))
            db_conn.commit()
            if cur.rowcount > 0:
                return True, "Type de financement supprimé."
            return False, "Type de financement non trouvé."
    except psycopg2.errors.ForeignKeyViolation:
        db_conn.rollback()
        msg = "Impossible de supprimer : ce financement est utilisé par des cours."
        return False, msg
    except psycopg2.Error as e:
        db_conn.rollback()
        current_app.logger.error(f"Erreur DAO delete_financement pour {code}: {e}")
        return False, "Erreur base de données."


# --- Fonctions DAO - Année-dépendantes (Enseignants, Cours, Attributions) ---


def get_total_periodes_disponibles_par_champ(annee_id: int) -> dict[str, float]:
    """
    Calcule le total des périodes disponibles pour chaque champ pour une année donnée.

    Le calcul est SUM(NbPeriodes * NbGroupeInitial) pour tous les cours d'un champ.

    Args:
        annee_id: L'ID de l'année scolaire.

    Returns:
        Un dictionnaire mappant le ChampNo au total des périodes disponibles.
    """
    db_conn = get_db()
    if not db_conn:
        return {}
    try:
        with db_conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """
                SELECT ChampNo, SUM(NbPeriodes * NbGroupeInitial) as total_disponible
                FROM Cours
                WHERE annee_id = %s
                GROUP BY ChampNo;
                """,
                (annee_id,),
            )
            # COALESCE est utilisé pour s'assurer que si la somme est NULL (aucun cours), on retourne 0.
            return {
                row["champno"]: float(row["total_disponible"] or 0.0)
                for row in cur.fetchall()
            }
    except psycopg2.Error as e:
        current_app.logger.error(
            "Erreur DAO get_total_periodes_disponibles_par_champ pour annee "
            f"{annee_id}: {e}"
        )
        return {}


def get_enseignants_par_champ(
    champ_no: str, annee_id: int
) -> list[dict[str, Any]]:
    """Récupère les enseignants d'un champ pour une année donnée."""
    db_conn = get_db()
    if not db_conn:
        return []
    try:
        with db_conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """
                SELECT EnseignantID, NomComplet, Nom, Prenom, EstTempsPlein,
                       EstFictif, PeutChoisirHorsChampPrincipal
                FROM Enseignants
                WHERE ChampNo = %s AND annee_id = %s
                ORDER BY EstFictif,
                         Nom COLLATE "fr-CA-x-icu",
                         Prenom COLLATE "fr-CA-x-icu";
                """,
                (champ_no, annee_id),
            )
            return [dict(e) for e in cur.fetchall()]
    except psycopg2.Error as e:
        current_app.logger.error(
            "Erreur DAO get_enseignants_par_champ pour champ "
            f"{champ_no}, annee {annee_id}: {e}"
        )
        return []


def get_all_enseignants_avec_details(annee_id: int) -> list[dict[str, Any]]:
    """Récupère tous les enseignants d'une année avec des détails enrichis, y compris les statuts du champ."""
    db_conn = get_db()
    if not db_conn:
        return []
    try:
        with db_conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """
                SELECT
                    e.EnseignantID, e.NomComplet, e.Nom, e.Prenom, e.EstTempsPlein,
                    e.EstFictif, e.ChampNo, ch.ChampNom,
                    e.PeutChoisirHorsChampPrincipal,
                    COALESCE(cas.est_verrouille, FALSE) AS est_verrouille,
                    COALESCE(cas.est_confirme, FALSE) AS est_confirme
                FROM Enseignants e
                JOIN Champs ch ON e.ChampNo = ch.ChampNo
                LEFT JOIN champ_annee_statuts cas
                    ON e.ChampNo = cas.champ_no AND e.annee_id = cas.annee_id
                WHERE e.annee_id = %s
                ORDER BY e.ChampNo,
                         e.EstFictif,
                         e.Nom COLLATE "fr-CA-x-icu",
                         e.Prenom COLLATE "fr-CA-x-icu";
                """,
                (annee_id,),
            )
            enseignants_bruts = [dict(row) for row in cur.fetchall()]

        toutes_les_attributions = get_toutes_les_attributions(annee_id)
        attributions_par_enseignant: dict[int, list[Any]] = defaultdict(list)
        for attr in toutes_les_attributions:
            attributions_par_enseignant[attr["enseignantid"]].append(attr)

        enseignants_complets = []
        for ens_brut in enseignants_bruts:
            attributions = attributions_par_enseignant.get(
                ens_brut["enseignantid"], []
            )
            periodes = calculer_periodes_pour_attributions(attributions)
            compte_pour_moyenne = (
                ens_brut["esttempsplein"] and not ens_brut["estfictif"]
            )
            enseignants_complets.append(
                {**ens_brut, **periodes, "compte_pour_moyenne_champ": compte_pour_moyenne}
            )
        return enseignants_complets
    except psycopg2.Error as e:
        current_app.logger.error(
            "Erreur DAO get_all_enseignants_avec_details pour annee "
            f"{annee_id}: {e}"
        )
        return []


def get_cours_disponibles_par_champ(
    champ_no: str, annee_id: int
) -> list[dict[str, Any]]:
    """Récupère les cours d'un champ pour une année, avec le nb de groupes restants."""
    db_conn = get_db()
    if not db_conn:
        return []
    try:
        with db_conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """
                SELECT
                    c.CodeCours, c.CoursDescriptif, c.NbPeriodes, c.EstCoursAutre,
                    c.NbGroupeInitial, c.annee_id, c.financement_code,
                    (c.NbGroupeInitial - COALESCE(SUM(ac.NbGroupesPris), 0))
                        AS grprestant
                FROM Cours c
                LEFT JOIN AttributionsCours ac
                    ON c.CodeCours = ac.CodeCours AND c.annee_id = ac.annee_id_cours
                WHERE c.ChampNo = %s AND c.annee_id = %s
                GROUP BY c.CodeCours, c.annee_id
                ORDER BY c.EstCoursAutre, c.CodeCours;
                """,
                (champ_no, annee_id),
            )
            return [dict(cr) for cr in cur.fetchall()]
    except psycopg2.Error as e:
        current_app.logger.error(
            "Erreur DAO get_cours_disponibles_par_champ pour champ "
            f"{champ_no}, annee {annee_id}: {e}"
        )
        return []


def get_attributions_enseignant(enseignant_id: int) -> list[dict[str, Any]]:
    """Récupère les attributions d'un enseignant (l'ID est unique à une année)."""
    db_conn = get_db()
    if not db_conn:
        return []
    try:
        with db_conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """
                SELECT ac.AttributionID, ac.CodeCours, ac.NbGroupesPris,
                       c.CoursDescriptif, c.NbPeriodes, c.EstCoursAutre,
                       c.annee_id, c.financement_code
                FROM AttributionsCours ac
                JOIN Cours c
                    ON ac.CodeCours = c.CodeCours AND ac.annee_id_cours = c.annee_id
                WHERE ac.EnseignantID = %s
                ORDER BY c.EstCoursAutre, c.CoursDescriptif;
                """,
                (enseignant_id,),
            )
            return [dict(a) for a in cur.fetchall()]
    except psycopg2.Error as e:
        current_app.logger.error(
            f"Erreur DAO get_attributions_enseignant pour {enseignant_id}: {e}"
        )
        return []


def get_toutes_les_attributions(annee_id: int) -> list[dict[str, Any]]:
    """Récupère toutes les attributions pour une année scolaire donnée."""
    db_conn = get_db()
    if not db_conn:
        return []
    try:
        with db_conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """
                SELECT ac.AttributionID, ac.EnseignantID, ac.CodeCours, ac.NbGroupesPris,
                       c.CoursDescriptif, c.NbPeriodes, c.EstCoursAutre, c.financement_code
                FROM AttributionsCours ac
                JOIN Cours c
                    ON ac.CodeCours = c.CodeCours AND ac.annee_id_cours = c.annee_id
                JOIN Enseignants e ON ac.EnseignantID = e.EnseignantID
                WHERE e.annee_id = %s
                ORDER BY ac.EnseignantID, c.EstCoursAutre, c.CoursDescriptif;
                """,
                (annee_id,),
            )
            return [dict(a) for a in cur.fetchall()]
    except psycopg2.Error as e:
        current_app.logger.error(
            f"Erreur DAO get_toutes_les_attributions pour annee {annee_id}: {e}"
        )
        return []


def calculer_periodes_pour_attributions(
    attributions: list[dict[str, Any]]
) -> dict[str, float]:
    """Calcule les totaux de périodes à partir d'une liste d'attributions."""
    periodes_cours = sum(
        float(a["nbperiodes"]) * a["nbgroupespris"]
        for a in attributions
        if not a["estcoursautre"]
    )
    periodes_autres = sum(
        float(a["nbperiodes"]) * a["nbgroupespris"]
        for a in attributions
        if a["estcoursautre"]
    )
    return {
        "periodes_cours": periodes_cours,
        "periodes_autres": periodes_autres,
        "total_periodes": periodes_cours + periodes_autres,
    }


def calculer_periodes_enseignant(enseignant_id: int) -> dict[str, float]:
    """Calcule les totaux de périodes pour un enseignant spécifique."""
    attributions = get_attributions_enseignant(enseignant_id)
    return calculer_periodes_pour_attributions(attributions)


def get_groupes_restants_pour_cours(code_cours: str, annee_id: int) -> int:
    """Calcule les groupes restants pour un cours d'une année donnée."""
    db_conn = get_db()
    if not db_conn:
        return 0
    try:
        with db_conn.cursor() as cur:
            cur.execute(
                """
                SELECT (c.NbGroupeInitial - COALESCE(SUM(ac.NbGroupesPris), 0))
                FROM Cours c
                LEFT JOIN AttributionsCours ac
                    ON c.CodeCours = ac.CodeCours AND c.annee_id = ac.annee_id_cours
                WHERE c.CodeCours = %s AND c.annee_id = %s
                GROUP BY c.CodeCours, c.annee_id;
                """,
                (code_cours, annee_id),
            )
            result = cur.fetchone()
            return int(result[0]) if result and result[0] is not None else 0
    except psycopg2.Error as e:
        current_app.logger.error(
            "Erreur DAO get_groupes_restants_pour_cours pour "
            f"{code_cours}, annee {annee_id}: {e}"
        )
        return 0


def get_all_cours_grouped_by_champ(annee_id: int) -> dict[str, dict[str, Any]]:
    """Récupère tous les cours d'une année, regroupés par champ."""
    db_conn = get_db()
    if not db_conn:
        return {}
    try:
        with db_conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """
                SELECT c.CodeCours, c.CoursDescriptif, c.NbPeriodes,
                       c.NbGroupeInitial, c.EstCoursAutre, c.financement_code,
                       c.ChampNo, ch.ChampNom
                FROM Cours c JOIN Champs ch ON c.ChampNo = ch.ChampNo
                WHERE c.annee_id = %s
                ORDER BY ch.ChampNo, c.CodeCours;
                """,
                (annee_id,),
            )
            cours_par_champ: dict[str, Any] = defaultdict(
                lambda: {"champ_nom": "", "cours": []}
            )
            for row in cur.fetchall():
                champ_no = row["champno"]
                if not cours_par_champ[champ_no]["champ_nom"]:
                    cours_par_champ[champ_no]["champ_nom"] = row["champnom"]
                cours_par_champ[champ_no]["cours"].append(dict(row))
            return dict(cours_par_champ)
    except psycopg2.Error as e:
        current_app.logger.error(
            f"Erreur DAO get_all_cours_grouped_by_champ pour annee {annee_id}: {e}"
        )
        return {}


def get_verrou_info_enseignant(enseignant_id: int) -> dict[str, Any] | None:
    """Récupère le statut de verrouillage (spécifique à l'année), fictif et le champno pour un enseignant."""
    db_conn = get_db()
    if not db_conn:
        return None
    try:
        with db_conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """
                SELECT
                    e.EstFictif,
                    e.ChampNo,
                    e.annee_id,
                    COALESCE(cas.est_verrouille, FALSE) AS est_verrouille
                FROM Enseignants e
                LEFT JOIN champ_annee_statuts cas
                    ON e.ChampNo = cas.champ_no AND e.annee_id = cas.annee_id
                WHERE e.EnseignantID = %s;
                """,
                (enseignant_id,),
            )
            return dict(row) if (row := cur.fetchone()) else None
    except psycopg2.Error as e:
        current_app.logger.error(
            f"Erreur DAO get_verrou_info_enseignant pour {enseignant_id}: {e}"
        )
        return None


def add_attribution(
    enseignant_id: int, code_cours: str, annee_id_cours: int
) -> int | None:
    """Ajoute une attribution de cours à un enseignant pour une année donnée."""
    db_conn = get_db()
    if not db_conn:
        return None
    try:
        with db_conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                "INSERT INTO AttributionsCours (EnseignantID, CodeCours, "
                "annee_id_cours, NbGroupesPris) VALUES (%s, %s, %s, 1) "
                "RETURNING AttributionID;",
                (enseignant_id, code_cours, annee_id_cours),
            )
            new_id = cur.fetchone()
            db_conn.commit()
            return new_id["attributionid"] if new_id else None
    except psycopg2.Error as e:
        db_conn.rollback()
        current_app.logger.error(
            "Erreur DAO add_attribution pour enseignant "
            f"{enseignant_id}, cours {code_cours}: {e}"
        )
        return None


def get_attribution_info(attribution_id: int) -> dict[str, Any] | None:
    """Récupère les informations détaillées d'une attribution, y compris le statut de verrouillage du champ pour l'année concernée."""
    db_conn = get_db()
    if not db_conn:
        return None
    try:
        with db_conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """
                SELECT
                    ac.EnseignantID, ac.CodeCours, ac.annee_id_cours,
                    e.EstFictif, e.ChampNo,
                    COALESCE(cas.est_verrouille, FALSE) AS est_verrouille
                FROM AttributionsCours ac
                JOIN Enseignants e ON ac.EnseignantID = e.EnseignantID
                LEFT JOIN champ_annee_statuts cas
                    ON e.ChampNo = cas.champ_no AND e.annee_id = cas.annee_id
                WHERE ac.AttributionID = %s;
                """,
                (attribution_id,),
            )
            return dict(row) if (row := cur.fetchone()) else None
    except psycopg2.Error as e:
        current_app.logger.error(
            f"Erreur DAO get_attribution_info pour attribution {attribution_id}: {e}"
        )
        return None


def delete_attribution(attribution_id: int) -> bool:
    """Supprime une attribution de cours."""
    db_conn = get_db()
    if not db_conn:
        return False
    try:
        with db_conn.cursor() as cur:
            cur.execute(
                "DELETE FROM AttributionsCours WHERE AttributionID = %s;",
                (attribution_id,),
            )
            db_conn.commit()
            return cur.rowcount > 0
    except psycopg2.Error as e:
        db_conn.rollback()
        current_app.logger.error(
            f"Erreur DAO delete_attribution pour attribution {attribution_id}: {e}"
        )
        return False


def create_fictif_enseignant(champ_no: str, annee_id: int) -> dict[str, Any] | None:
    """Crée un enseignant fictif pour une année donnée."""
    db_conn = get_db()
    if not db_conn:
        return None
    try:
        with db_conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            # Les % wildcards pour LIKE sont échappés en %% pour psycopg2
            cur.execute(
                "SELECT NomComplet FROM Enseignants WHERE ChampNo = %s AND "
                "EstFictif = TRUE AND NomComplet LIKE %s AND annee_id = %s;",
                (champ_no, f"{champ_no}-Tâche restante-%", annee_id),
            )
            numeros = [
                int(r["nomcomplet"].split("-")[-1])
                for r in cur.fetchall()
                if r["nomcomplet"].split("-")[-1].isdigit()
            ]
            next_num = max(numeros) + 1 if numeros else 1
            nom_tache = f"{champ_no}-Tâche restante-{next_num}"

            cur.execute(
                """
                INSERT INTO Enseignants (NomComplet, ChampNo, annee_id,
                                         EstTempsPlein, EstFictif)
                VALUES (%s, %s, %s, TRUE, TRUE)
                RETURNING EnseignantID, NomComplet, Nom, Prenom, EstTempsPlein,
                          EstFictif, PeutChoisirHorsChampPrincipal, ChampNo, annee_id;
                """,
                (nom_tache, champ_no, annee_id),
            )
            new_fictif_data = cur.fetchone()
            db_conn.commit()
            return dict(new_fictif_data) if new_fictif_data else None
    except psycopg2.Error as e:
        db_conn.rollback()
        current_app.logger.error(
            "Erreur DAO create_fictif_enseignant pour champ "
            f"{champ_no}, annee {annee_id}: {e}"
        )
        return None


def get_affected_cours_for_enseignant(enseignant_id: int) -> list[dict[str, Any]]:
    """Récupère les cours affectés à un enseignant (code et année)."""
    db_conn = get_db()
    if not db_conn:
        return []
    try:
        with db_conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                "SELECT DISTINCT CodeCours, annee_id_cours FROM AttributionsCours "
                "WHERE EnseignantID = %s;",
                (enseignant_id,),
            )
            return [dict(row) for row in cur.fetchall()]
    except psycopg2.Error as e:
        current_app.logger.error(
            "Erreur DAO get_affected_cours_for_enseignant pour enseignant "
            f"{enseignant_id}: {e}"
        )
        return []


def delete_enseignant(enseignant_id: int) -> bool:
    """Supprime un enseignant (et ses attributions par CASCADE)."""
    db_conn = get_db()
    if not db_conn:
        return False
    try:
        with db_conn.cursor() as cur:
            cur.execute(
                "DELETE FROM Enseignants WHERE EnseignantID = %s;", (enseignant_id,)
            )
            db_conn.commit()
            return cur.rowcount > 0
    except psycopg2.Error as e:
        db_conn.rollback()
        current_app.logger.error(
            f"Erreur DAO delete_enseignant pour enseignant {enseignant_id}: {e}"
        )
        return False


def reassign_cours_to_champ(
    code_cours: str, annee_id: int, nouveau_champ_no: str
) -> dict[str, Any] | None:
    """Réassigne un cours à un nouveau champ pour une année donnée."""
    db_conn = get_db()
    if not db_conn:
        return None
    try:
        with db_conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                "SELECT ChampNom FROM Champs WHERE ChampNo = %s;", (nouveau_champ_no,)
            )
            if not (new_champ := cur.fetchone()):
                return None  # Champ de destination n'existe pas

            cur.execute(
                "UPDATE Cours SET ChampNo = %s "
                "WHERE CodeCours = %s AND annee_id = %s;",
                (nouveau_champ_no, code_cours, annee_id),
            )
            if cur.rowcount == 0:
                db_conn.rollback()
                return None  # Cours non trouvé pour cette année

            db_conn.commit()
            return {
                "nouveau_champ_no": nouveau_champ_no,
                "nouveau_champ_nom": new_champ["champnom"],
            }
    except psycopg2.Error as e:
        db_conn.rollback()
        current_app.logger.error(
            "Erreur DAO reassign_cours_to_champ pour cours "
            f"{code_cours}, annee {annee_id}: {e}"
        )
        return None


# --- Nouvelles fonctions CRUD pour la gestion manuelle (année-dépendantes) ---


def create_cours(data: dict[str, Any], annee_id: int) -> dict[str, Any] | None:
    """Crée un nouveau cours pour une année donnée, en gérant la logique pour le financement."""
    db_conn = get_db()
    if not db_conn:
        return None

    # Gère la valeur de 'financement_code' (une chaîne vide doit devenir NULL).
    data["financement_code"] = data.get("financement_code") or None

    try:
        with db_conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """
                INSERT INTO Cours (CodeCours, annee_id, ChampNo, CoursDescriptif,
                                   NbPeriodes, NbGroupeInitial, EstCoursAutre, financement_code)
                VALUES (%(codecours)s, %(annee_id)s, %(champno)s, %(coursdescriptif)s,
                        %(nbperiodes)s, %(nbgroupeinitial)s, %(estcoursautre)s,
                        %(financement_code)s)
                RETURNING *;
                """,
                {**data, "annee_id": annee_id},
            )
            new_cours = cur.fetchone()
            db_conn.commit()
            return dict(new_cours) if new_cours else None
    except psycopg2.Error:
        db_conn.rollback()
        raise


def get_cours_details(code_cours: str, annee_id: int) -> dict[str, Any] | None:
    """Récupère les détails d'un cours spécifique pour une année."""
    db_conn = get_db()
    if not db_conn:
        return None
    try:
        with db_conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                "SELECT * FROM Cours WHERE CodeCours = %s AND annee_id = %s;",
                (code_cours, annee_id),
            )
            return dict(row) if (row := cur.fetchone()) else None
    except psycopg2.Error as e:
        current_app.logger.error(
            f"Erreur DAO get_cours_details pour {code_cours}, annee {annee_id}: {e}"
        )
        return None


def update_cours(
    code_cours: str, annee_id: int, data: dict[str, Any]
) -> dict[str, Any] | None:
    """Met à jour un cours pour une année, en gérant la logique pour le financement."""
    db_conn = get_db()
    if not db_conn:
        return None

    # Gère la valeur de 'financement_code' (une chaîne vide doit devenir NULL).
    data["financement_code"] = data.get("financement_code") or None

    try:
        with db_conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """
                UPDATE Cours
                SET ChampNo = %(champno)s, CoursDescriptif = %(coursdescriptif)s,
                    NbPeriodes = %(nbperiodes)s,
                    NbGroupeInitial = %(nbgroupeinitial)s,
                    EstCoursAutre = %(estcoursautre)s, financement_code = %(financement_code)s
                WHERE CodeCours = %(original_codecours)s AND annee_id = %(annee_id)s
                RETURNING *;
                """,
                {**data, "original_codecours": code_cours, "annee_id": annee_id},
            )
            updated_cours = cur.fetchone()
            db_conn.commit()
            return dict(updated_cours) if updated_cours else None
    except psycopg2.Error:
        db_conn.rollback()
        raise


def delete_cours(code_cours: str, annee_id: int) -> tuple[bool, str]:
    """Supprime un cours pour une année."""
    db_conn = get_db()
    if not db_conn:
        return False, "Erreur de connexion."
    try:
        with db_conn.cursor() as cur:
            cur.execute(
                "DELETE FROM Cours WHERE CodeCours = %s AND annee_id = %s;",
                (code_cours, annee_id),
            )
            db_conn.commit()
            if cur.rowcount > 0:
                return True, "Cours supprimé."
            return False, "Cours non trouvé."
    except psycopg2.errors.ForeignKeyViolation:
        db_conn.rollback()
        msg = "Impossible de supprimer: cours attribué à un ou plusieurs enseignants."
        return False, msg
    except psycopg2.Error as e:
        db_conn.rollback()
        current_app.logger.error(
            f"Erreur DAO delete_cours pour {code_cours}, annee {annee_id}: {e}"
        )
        return False, "Erreur base de données."


def reassign_cours_to_financement(
    code_cours: str, annee_id: int, nouveau_financement_code: str | None
) -> bool:
    """Réassigne un cours à un nouveau type de financement pour une année donnée."""
    db_conn = get_db()
    if not db_conn:
        return False
    try:
        with db_conn.cursor() as cur:
            cur.execute(
                "UPDATE Cours SET financement_code = %s "
                "WHERE CodeCours = %s AND annee_id = %s;",
                (nouveau_financement_code, code_cours, annee_id),
            )
            if cur.rowcount == 0:
                db_conn.rollback()
                return False  # Cours non trouvé pour cette année
            db_conn.commit()
            return True
    except psycopg2.Error as e:
        db_conn.rollback()
        current_app.logger.error(
            "Erreur DAO reassign_cours_to_financement pour cours "
            f"{code_cours}, annee {annee_id}: {e}"
        )
        return False


def create_enseignant(data: dict[str, Any], annee_id: int) -> dict[str, Any] | None:
    """Crée un nouvel enseignant pour une année."""
    db_conn = get_db()
    if not db_conn:
        return None
    try:
        with db_conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            data["nomcomplet"] = f"{data['prenom']} {data['nom']}"
            cur.execute(
                """
                INSERT INTO Enseignants (annee_id, NomComplet, Nom, Prenom,
                                         ChampNo, EstTempsPlein, EstFictif)
                VALUES (%(annee_id)s, %(nomcomplet)s, %(nom)s, %(prenom)s,
                        %(champno)s, %(esttempsplein)s, FALSE)
                RETURNING *;
                """,
                {**data, "annee_id": annee_id},
            )
            new_enseignant = cur.fetchone()
            db_conn.commit()
            return dict(new_enseignant) if new_enseignant else None
    except psycopg2.Error:
        db_conn.rollback()
        raise


def get_enseignant_details(enseignant_id: int) -> dict[str, Any] | None:
    """Récupère les détails d'un enseignant par son ID unique."""
    db_conn = get_db()
    if not db_conn:
        return None
    try:
        with db_conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                "SELECT * FROM Enseignants WHERE EnseignantID = %s;", (enseignant_id,)
            )
            return dict(row) if (row := cur.fetchone()) else None
    except psycopg2.Error as e:
        current_app.logger.error(
            f"Erreur DAO get_enseignant_details pour {enseignant_id}: {e}"
        )
        return None


def update_enseignant(
    enseignant_id: int, data: dict[str, Any]
) -> dict[str, Any] | None:
    """Met à jour un enseignant (cible par ID unique)."""
    db_conn = get_db()
    if not db_conn:
        return None
    try:
        with db_conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            data["nomcomplet"] = f"{data['prenom']} {data['nom']}"
            cur.execute(
                """
                UPDATE Enseignants
                SET NomComplet = %(nomcomplet)s, Nom = %(nom)s, Prenom = %(prenom)s,
                    ChampNo = %(champno)s, EstTempsPlein = %(esttempsplein)s
                WHERE EnseignantID = %(enseignantid)s AND EstFictif = FALSE
                RETURNING *;
                """,
                {**data, "enseignantid": enseignant_id},
            )
            updated_enseignant = cur.fetchone()
            db_conn.commit()
            return dict(updated_enseignant) if updated_enseignant else None
    except psycopg2.Error:
        db_conn.rollback()
        raise


def get_all_enseignants_grouped_by_champ(annee_id: int) -> dict[str, dict[str, Any]]:
    """Récupère tous les enseignants d'une année, regroupés par champ."""
    db_conn = get_db()
    if not db_conn:
        return {}
    try:
        with db_conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """
                SELECT e.EnseignantID, e.NomComplet, e.EstTempsPlein,
                       e.ChampNo, ch.ChampNom
                FROM Enseignants e
                JOIN Champs ch ON e.ChampNo = ch.ChampNo
                WHERE e.EstFictif = FALSE AND e.annee_id = %s
                ORDER BY ch.ChampNo,
                         e.Nom COLLATE "fr-CA-x-icu",
                         e.Prenom COLLATE "fr-CA-x-icu";
                """,
                (annee_id,),
            )
            enseignants_par_champ: dict[str, Any] = defaultdict(
                lambda: {"champ_nom": "", "enseignants": []}
            )
            for row in cur.fetchall():
                champ_no = row["champno"]
                if not enseignants_par_champ[champ_no]["champ_nom"]:
                    enseignants_par_champ[champ_no]["champ_nom"] = row["champnom"]
                enseignants_par_champ[champ_no]["enseignants"].append(dict(row))
            return dict(enseignants_par_champ)
    except psycopg2.Error as e:
        current_app.logger.error(
            "Erreur DAO get_all_enseignants_grouped_by_champ pour annee "
            f"{annee_id}: {e}"
        )
        return {}


def delete_all_attributions_for_year(annee_id: int) -> int:
    """Supprime TOUTES les attributions pour une année donnée. Retourne le nombre de lignes supprimées."""
    db_conn = get_db()
    if not db_conn:
        return 0
    try:
        with db_conn.cursor() as cur:
            # On joint sur enseignants pour être sûr de ne supprimer que les attributions de l'année
            cur.execute(
                """
                DELETE FROM AttributionsCours ac USING Enseignants e
                WHERE ac.EnseignantID = e.EnseignantID AND e.annee_id = %s;
                """,
                (annee_id,),
            )
            deleted_count = cur.rowcount
            # Pas de commit ici si la fonction est utilisée dans une transaction plus large
            return deleted_count
    except psycopg2.Error as e:
        db_conn.rollback()
        current_app.logger.error(
            f"Erreur DAO delete_all_attributions_for_year pour annee {annee_id}: {e}"
        )
        raise


def delete_all_cours_for_year(annee_id: int) -> int:
    """Supprime TOUS les cours pour une année donnée. Retourne le nombre de lignes supprimées."""
    db_conn = get_db()
    if not db_conn:
        return 0
    try:
        with db_conn.cursor() as cur:
            cur.execute("DELETE FROM Cours WHERE annee_id = %s;", (annee_id,))
            deleted_count = cur.rowcount
            # Pas de commit ici si la fonction est utilisée dans une transaction plus large
            return deleted_count
    except psycopg2.Error as e:
        db_conn.rollback()
        current_app.logger.error(
            f"Erreur DAO delete_all_cours_for_year pour annee {annee_id}: {e}"
        )
        raise


def delete_all_enseignants_for_year(annee_id: int) -> int:
    """Supprime TOUS les enseignants pour une année donnée. Retourne le nombre de lignes supprimées."""
    db_conn = get_db()
    if not db_conn:
        return 0
    try:
        with db_conn.cursor() as cur:
            cur.execute("DELETE FROM Enseignants WHERE annee_id = %s;", (annee_id,))
            deleted_count = cur.rowcount
            # Pas de commit ici si la fonction est utilisée dans une transaction plus large
            return deleted_count
    except psycopg2.Error as e:
        db_conn.rollback()
        current_app.logger.error(
            f"Erreur DAO delete_all_enseignants_for_year pour annee {annee_id}: {e}"
        )
        raise


def get_all_attributions_for_export(annee_id: int) -> list[dict[str, Any]]:
    """
    Récupère toutes les attributions de cours pour une année donnée, formatées pour l'export.

    Cette fonction joint les informations des attributions, enseignants, cours et champs.
    Elle regroupe les attributions par enseignant/cours et somme le nombre de groupes.
    Elle exclut les enseignants fictifs et trie les résultats pour l'export.

    Args:
        annee_id: L'ID de l'année scolaire à exporter.

    Returns:
        Une liste de dictionnaires, chaque dictionnaire représentant une ligne
        de données agrégées pour le fichier Excel.
    """
    db_conn = get_db()
    if not db_conn:
        return []
    try:
        with db_conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """
                SELECT
                    ch.ChampNo, ch.ChampNom, e.Nom, e.Prenom, c.CodeCours,
                    c.CoursDescriptif, c.EstCoursAutre, c.financement_code,
                    SUM(ac.NbGroupesPris) AS total_groupes_pris, c.NbPeriodes
                FROM AttributionsCours AS ac
                JOIN Enseignants AS e ON ac.EnseignantID = e.EnseignantID
                JOIN Cours AS c
                    ON ac.CodeCours = c.CodeCours AND ac.annee_id_cours = c.annee_id
                JOIN Champs AS ch ON c.ChampNo = ch.ChampNo
                WHERE
                    e.annee_id = %s AND e.EstFictif = FALSE
                GROUP BY
                    ch.ChampNo, ch.ChampNom, e.Nom, e.Prenom, c.CodeCours,
                    c.CoursDescriptif, c.EstCoursAutre, c.financement_code, c.NbPeriodes
                ORDER BY
                    ch.ChampNo ASC,
                    e.Nom COLLATE "fr-CA-x-icu" ASC,
                    e.Prenom COLLATE "fr-CA-x-icu" ASC,
                    c.CodeCours ASC;
                """,
                (annee_id,),
            )
            return [dict(row) for row in cur.fetchall()]
    except psycopg2.Error as e:
        current_app.logger.error(
            "Erreur DAO get_all_attributions_for_export pour annee "
            f"{annee_id}: {e}"
        )
        return []


def get_periodes_restantes_for_export(annee_id: int) -> list[dict[str, Any]]:
    """
    Récupère les périodes restantes en "dégroupant" chaque groupe sur une ligne
    et en appliquant un tri spécifique pour le rapport.

    Combine deux sources de "tâches restantes" pour une année donnée :
    1. Les cours/groupes assignés à des enseignants marqués comme "fictifs".
    2. Les groupes de cours qui ne sont assignés à aucun enseignant.

    La fonction utilise `generate_series` pour "exploser" les décomptes de
    groupes en plusieurs lignes. Le tri final place les tâches "Non attribuées"
    après les tâches fictives nommées, qui sont elles-mêmes triées numériquement.

    Args:
        annee_id: L'ID de l'année scolaire.

    Returns:
        Une liste de dictionnaires où chaque dictionnaire représente un seul
        groupe de cours restant, trié pour l'affichage.
    """
    db_conn = get_db()
    if not db_conn:
        return []
    try:
        with db_conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """
                WITH remaining_groups_aggregated AS (
                    WITH total_assigned AS (
                        SELECT CodeCours, annee_id_cours, SUM(NbGroupesPris) as total_pris
                        FROM AttributionsCours
                        GROUP BY CodeCours, annee_id_cours
                    )
                    SELECT
                        ch.ChampNo, ch.ChampNom, e.NomComplet AS tache_restante,
                        c.CodeCours, c.CoursDescriptif, c.EstCoursAutre,
                        c.NbPeriodes, c.financement_code, SUM(ac.NbGroupesPris) AS nb_groupes_total
                    FROM AttributionsCours AS ac
                    JOIN Enseignants AS e ON ac.EnseignantID = e.EnseignantID
                    JOIN Cours AS c
                        ON ac.CodeCours = c.CodeCours AND ac.annee_id_cours = c.annee_id
                    JOIN Champs AS ch ON c.ChampNo = ch.ChampNo
                    WHERE e.annee_id = %(annee_id)s AND e.EstFictif = TRUE
                    GROUP BY ch.ChampNo, ch.ChampNom, e.NomComplet, c.CodeCours,
                             c.CoursDescriptif, c.EstCoursAutre, c.NbPeriodes, c.financement_code
                    UNION ALL
                    SELECT
                        ch.ChampNo, ch.ChampNom, 'Non attribuées' AS tache_restante,
                        c.CodeCours, c.CoursDescriptif, c.EstCoursAutre,
                        c.NbPeriodes, c.financement_code,
                        (c.NbGroupeInitial - COALESCE(ta.total_pris, 0)) AS nb_groupes_total
                    FROM Cours AS c
                    JOIN Champs AS ch ON c.ChampNo = ch.ChampNo
                    LEFT JOIN total_assigned AS ta
                        ON c.CodeCours = ta.CodeCours AND c.annee_id = ta.annee_id_cours
                    WHERE c.annee_id = %(annee_id)s
                      AND (c.NbGroupeInitial - COALESCE(ta.total_pris, 0)) > 0
                )
                SELECT
                    r.ChampNo, r.ChampNom, r.tache_restante, r.CodeCours,
                    r.CoursDescriptif, r.EstCoursAutre, r.NbPeriodes, r.financement_code,
                    1 AS nb_groupes
                FROM
                    remaining_groups_aggregated r,
                    generate_series(1, r.nb_groupes_total)
                ORDER BY
                    r.ChampNo,
                    CASE WHEN r.tache_restante = 'Non attribuées' THEN 1 ELSE 0 END,
                    CASE
                        WHEN r.tache_restante LIKE '%%-Tâche restante-%%'
                        THEN CAST(substring(r.tache_restante FROM '-(\\d+)$') AS INTEGER)
                        ELSE NULL
                    END,
                    r.CodeCours;
                """,
                {"annee_id": annee_id},
            )
            return [dict(row) for row in cur.fetchall()]
    except psycopg2.Error as e:
        current_app.logger.error(
            "Erreur DAO get_periodes_restantes_for_export pour annee "
            f"{annee_id}: {e}",
            exc_info=True,
        )
        return []


def get_data_for_org_scolaire_export(annee_id: int) -> list[dict[str, Any]]:
    """
    Récupère les données brutes pour l'export "Organisation Scolaire".

    Cette fonction ne pivote PAS les données. Elle retourne les données agrégées
    par enseignant/tâche et par type de cours/financement, prêtes à être
    pivotées en Python. Elle combine les attributions (réels et fictifs)
    et les périodes non attribuées.

    Args:
        annee_id: L'ID de l'année scolaire.

    Returns:
        Une liste de dictionnaires contenant les données brutes pour l'export.
        Chaque dictionnaire inclut des informations sur l'enseignant, le champ,
        le type de cours (`financement_code`, `CodeCours`, `EstCoursAutre`) et
        le total des périodes associées.
    """
    db_conn = get_db()
    if not db_conn:
        return []
    try:
        with db_conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            query_sql = """
                WITH all_tasks_raw AS (
                    -- Part 1: Attributions existantes
                    SELECT
                        e.annee_id,
                        ch.ChampNo,
                        ch.ChampNom,
                        e.Nom,
                        e.Prenom,
                        e.NomComplet,
                        e.EstFictif,
                        c.financement_code,
                        c.CodeCours,
                        c.EstCoursAutre,
                        c.NbPeriodes * ac.NbGroupesPris AS periodes_calculees
                    FROM AttributionsCours AS ac
                    JOIN Enseignants AS e ON ac.EnseignantID = e.EnseignantID
                    JOIN Cours AS c ON ac.CodeCours = c.CodeCours AND ac.annee_id_cours = c.annee_id
                    JOIN Champs AS ch ON e.ChampNo = ch.ChampNo
                    WHERE e.annee_id = %(annee_id)s

                    UNION ALL

                    -- Part 2: Cours non attribués
                    SELECT
                        c.annee_id,
                        ch.ChampNo,
                        ch.ChampNom,
                        'Non attribué' AS Nom,
                        NULL AS Prenom,
                        'Non attribué' AS NomComplet,
                        TRUE AS EstFictif,
                        c.financement_code,
                        c.CodeCours,
                        c.EstCoursAutre,
                        c.NbPeriodes * (c.NbGroupeInitial - COALESCE(ta.total_pris, 0)) AS periodes_calculees
                    FROM Cours AS c
                    JOIN Champs AS ch ON c.ChampNo = ch.ChampNo
                    LEFT JOIN (
                        SELECT CodeCours, annee_id_cours, SUM(NbGroupesPris) AS total_pris
                        FROM AttributionsCours
                        GROUP BY CodeCours, annee_id_cours
                    ) AS ta ON c.CodeCours = ta.CodeCours AND c.annee_id = ta.annee_id_cours
                    WHERE c.annee_id = %(annee_id)s AND (c.NbGroupeInitial - COALESCE(ta.total_pris, 0)) > 0
                )
                SELECT
                    ChampNo,
                    ChampNom,
                    Nom,
                    Prenom,
                    CASE
                        WHEN EstFictif = TRUE AND NomComplet LIKE ChampNo || '-Tâche restante-%%'
                        THEN regexp_replace(NomComplet, '^' || ChampNo || '[-\\s]*', '')
                        ELSE NomComplet
                    END AS NomComplet,
                    EstFictif,
                    financement_code,
                    CodeCours,
                    EstCoursAutre,
                    SUM(periodes_calculees) as total_periodes
                FROM all_tasks_raw
                GROUP BY ChampNo, ChampNom, Nom, Prenom, NomComplet, EstFictif, financement_code, CodeCours, EstCoursAutre
                HAVING SUM(periodes_calculees) > 0
                ORDER BY
                    ChampNo,
                    CASE
                        WHEN EstFictif = FALSE THEN 0
                        WHEN NomComplet LIKE '%%-Tâche restante-%%' THEN 1
                        WHEN NomComplet = 'Non attribué' THEN 2
                        ELSE 3
                    END,
                    CASE
                        WHEN EstFictif = TRUE AND NomComplet LIKE '%%-Tâche restante-%%'
                        THEN CAST(substring(NomComplet FROM '-(\\d+)$') AS INTEGER)
                        ELSE NULL
                    END,
                    Nom COLLATE "fr-CA-x-icu",
                    Prenom COLLATE "fr-CA-x-icu";
            """
            cur.execute(query_sql, {"annee_id": annee_id})
            return [dict(row) for row in cur.fetchall()]
    except psycopg2.Error as e:
        current_app.logger.error(
            "Erreur DAO get_data_for_org_scolaire_export pour annee "
            f"{annee_id}: {e}",
            exc_info=True,
        )
        return []