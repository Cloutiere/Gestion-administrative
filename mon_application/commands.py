# mon_application/commands.py
"""
Ce module définit les commandes CLI personnalisées pour l'application Flask.

Ces commandes sont utiles pour des tâches de gestion et de maintenance,
comme l'initialisation de la base de données. L'utilisation de commandes CLI
intégrées garantit que les opérations s'exécutent dans le contexte de
l'application, ce qui permet d'accéder facilement à la configuration et aux
extensions comme la base de données.

Pour utiliser les commandes définies ici, exécutez depuis le terminal :
`flask --app mon_application <nom_de_la_commande>`
Par exemple : `flask --app mon_application init-db`
"""

import os

import click
import psycopg2
from flask import Flask, current_app
from flask.cli import with_appcontext

from .database import get_db


@click.command("init-db")
@with_appcontext
def init_db_command() -> None:
    """
    Initialise la base de données en exécutant le schéma SQL.

    Cette commande lit le fichier `schema.sql` à la racine du projet et
    l'exécute sur la base de données configurée pour l'environnement actuel.
    ATTENTION : Ceci supprime les données existantes et recrée les tables.
    """
    click.echo("--- Début de l'initialisation de la base de données via la commande CLI ---")
    db_conn = get_db()
    if not db_conn:
        click.secho(
            "Erreur: Impossible d'établir une connexion à la base de données. "
            "Vérifiez vos variables d'environnement.",
            fg="red",
        )
        return

    schema_path = os.path.join(
        os.path.dirname(current_app.root_path), "schema.sql"
    )

    try:
        with db_conn.cursor() as cur:
            click.echo(f"Lecture du fichier de schéma : '{schema_path}'...")
            try:
                with open(schema_path, encoding="utf-8") as f:
                    sql_commands = f.read()
            except FileNotFoundError:
                click.secho(
                    f"Erreur : Le fichier '{schema_path}' est introuvable.", fg="red"
                )
                return

            click.echo("Application du schéma (création des tables)...")
            cur.execute(sql_commands)
            db_conn.commit()
            click.secho(
                "La base de données a été initialisée avec succès.", fg="green"
            )

    except psycopg2.Error as e:
        db_conn.rollback()
        click.secho(f"Erreur lors de l'application du schéma : {e}", fg="red")

    click.echo("--- Initialisation terminée. ---")


def init_app(app: Flask) -> None:
    """
    Enregistre les commandes CLI auprès de l'instance de l'application Flask.

    Args:
        app: L'instance de l'application Flask.
    """
    app.cli.add_command(init_db_command)