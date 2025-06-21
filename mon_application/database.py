# mon_application/database.py
"""
Ce module gère la connexion "legacy" à la base de données PostgreSQL.

IMPORTANT : Ce module est en cours de dépréciation. TOUTE la logique d'accès
aux données (DAO) a été migrée vers l'ORM SQLAlchemy via les modèles
(models.py) et les services (services.py).

Les fonctions restantes ici ne servent qu'à maintenir la compatibilité
avec le hook d'application `teardown_appcontext` qui ferme les connexions
psycopg2, tant que ce dernier n'est pas entièrement supprimé.
Il ne contient PLUS de fonctions d'accès aux données.
"""

import os

import psycopg2
import psycopg2.extras
import psycopg2.sql
from flask import Flask, current_app, g
from psycopg2.extensions import connection as PgConnection


# --- Gestion de la connexion à la base de données ---
def get_db_connection_string() -> str:
    """
    Construit la chaîne de connexion à la BDD en fonction de l'environnement.
    """
    app_env = os.environ.get("APP_ENV", "development")

    if app_env == "production":
        prefix = "PROD_"
    elif app_env == "test":
        prefix = "TEST_"
    else:
        prefix = "DEV_"

    if current_app:
        current_app.logger.info(f"Configuration de la base de données pour l'environnement : {app_env.upper()} avec le préfixe '{prefix}'")

    db_host = os.environ.get(f"{prefix}PGHOST")
    db_name = os.environ.get(f"{prefix}PGDATABASE")
    db_user = os.environ.get(f"{prefix}PGUSER")
    db_pass = os.environ.get(f"{prefix}PGPASSWORD")
    db_port = os.environ.get(f"{prefix}PGPORT", "5432")

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
        log_message = f"Variables de connexion à la base de données préfixées manquantes pour l'environnement '{app_env}': {', '.join(missing_vars)}"
        if current_app:
            current_app.logger.critical(log_message)
        return ""

    ssl_mode = "require" if "neon.tech" in db_host else "prefer"
    connection_string = f"dbname='{db_name}' user='{db_user}' host='{db_host}' password='{db_pass}' port='{db_port}' sslmode='{ssl_mode}'"
    return connection_string


def get_db() -> PgConnection | None:
    """Ouvre et réutilise une connexion à la base de données pour la durée d'une requête."""
    if "db" not in g:
        try:
            conn_string = get_db_connection_string()
            if not conn_string:
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
    app.teardown_appcontext(close_db)

# L'ancienne fonction get_periodes_restantes_for_export a été supprimée de ce fichier.
# Ce module ne contient plus aucune fonction d'accès aux données métier.