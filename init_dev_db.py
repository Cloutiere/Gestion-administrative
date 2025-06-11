# init_dev_db.py
"""
Script pour initialiser la base de données de développement.

Ce script réalise les opérations suivantes :
1. Lit les variables d'environnement DEV_PG... pour obtenir les informations de connexion.
2. Se connecte au serveur PostgreSQL (sur la base 'postgres' par défaut).
3. Crée la base de données de développement si elle n'existe pas déjà.
4. Se connecte à la nouvelle base de données de développement.
5. Lit le fichier 'schema.sql' et exécute son contenu pour créer les tables.

Prérequis :
- Les secrets DEV_PGHOST, DEV_PGDATABASE, DEV_PGUSER, DEV_PGPASSWORD doivent être
  configurés dans l'environnement (ex: onglet "Secrets" de Replit).
- L'utilisateur de la base de données doit avoir le droit de créer des bases de données.

Pour exécuter :
Ouvrez le terminal/shell et lancez : python init_dev_db.py
"""

import os
import sys

import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT


def main():
    """Fonction principale du script d'initialisation."""
    print("--- Début de l'initialisation de la base de données de développement ---")

    # 1. Récupérer les informations de connexion depuis les variables d'environnement
    try:
        db_host = os.environ["DEV_PGHOST"]
        db_name = os.environ["DEV_PGDATABASE"]
        db_user = os.environ["DEV_PGUSER"]
        db_pass = os.environ["DEV_PGPASSWORD"]
        db_port = os.environ.get("DEV_PGPORT", "5432")
    except KeyError as e:
        print(f"Erreur : Variable d'environnement manquante : {e}. Veuillez la définir dans les 'Secrets'.")
        sys.exit(1)

    # --- Étape A : Création de la base de données ---
    conn_admin = None
    try:
        # 2. Connexion au serveur (base de données 'postgres' qui existe par défaut)
        # pour pouvoir exécuter la commande CREATE DATABASE.
        print(f"Connexion au serveur PostgreSQL à l'adresse '{db_host}'...")
        conn_admin = psycopg2.connect(dbname="postgres", user=db_user, password=db_pass, host=db_host, port=db_port)
        conn_admin.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)

        with conn_admin.cursor() as cur:
            # 3. Vérifier si la base de données existe déjà pour éviter une erreur
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (db_name,))
            exists = cur.fetchone()
            if not exists:
                print(f"La base de données '{db_name}' n'existe pas. Création en cours...")
                cur.execute(f'CREATE DATABASE "{db_name}"')
                print(f"Base de données '{db_name}' créée avec succès.")
            else:
                print(f"La base de données '{db_name}' existe déjà. Aucune action de création requise.")

    except psycopg2.Error as e:
        print(f"Erreur lors de la création de la base de données : {e}")
        sys.exit(1)
    finally:
        if conn_admin:
            conn_admin.close()
            print("Connexion au serveur fermée.")

    # --- Étape B : Application du schéma ---
    conn_dev = None
    try:
        # 4. Connexion à la nouvelle base de données de DÉVELOPPEMENT
        print(f"\nConnexion à la nouvelle base de données '{db_name}'...")
        conn_dev = psycopg2.connect(dbname=db_name, user=db_user, password=db_pass, host=db_host, port=db_port)

        with conn_dev.cursor() as cur:
            # 5. Lecture et exécution du fichier schema.sql
            print("Lecture du fichier 'schema.sql'...")
            try:
                with open("schema.sql", encoding="utf-8") as f:
                    sql_commands = f.read()
            except FileNotFoundError:
                print("Erreur : Le fichier 'schema.sql' est introuvable à la racine du projet.")
                sys.exit(1)

            print("Application du schéma à la base de données (création des tables)...")
            cur.execute(sql_commands)
            conn_dev.commit()
            print("Schéma appliqué avec succès.")

    except psycopg2.Error as e:
        print(f"Erreur lors de l'application du schéma : {e}")
        if conn_dev:
            conn_dev.rollback()
        sys.exit(1)
    finally:
        if conn_dev:
            conn_dev.close()
            print(f"Connexion à '{db_name}' fermée.")

    print("\n--- Initialisation de la base de données de développement terminée avec succès ! ---")


if __name__ == "__main__":
    main()
