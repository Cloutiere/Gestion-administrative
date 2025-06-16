# tests/conftest.py
"""
Ce fichier contient les fixtures pytest partagées pour l'ensemble des tests.

Les fixtures sont des fonctions qui préparent un environnement de test réutilisable.
pytest les détecte automatiquement grâce au décorateur @pytest.fixture.
"""

import os
import subprocess

import pytest
from flask.testing import FlaskClient

from mon_application import create_app


@pytest.fixture(scope="session")
def app():
    """
    Fixture pour créer une seule instance de l'application pour toute la session de test.
    Le scope "session" améliore les performances en ne recréant pas l'app à chaque test.
    """
    app_instance = create_app({"TESTING": True})
    return app_instance


@pytest.fixture
def client(app):
    """
    Fixture qui fournit un client de test pour l'application.
    Permet de faire des requêtes (GET, POST, etc.) aux endpoints.
    """
    return app.test_client()


@pytest.fixture(autouse=True)
def init_database():
    """
    Fixture pour initialiser la base de données de test avant chaque test.

    Grâce à `autouse=True`, cette fixture sera automatiquement exécutée
    pour chaque fonction de test, garantissant un état de base de données propre.

    Elle exécute simplement le script `schema.sql`, qui contient maintenant
    la logique pour supprimer les anciennes tables avant de les recréer.
    """
    # MODIFICATION DÉFINITIVE : On trouve la racine du projet en partant du chemin
    # de ce fichier (conftest.py), ce qui est 100% fiable.
    # os.path.dirname(__file__) -> /home/runner/workspace/tests
    # os.path.dirname(...) -> /home/runner/workspace
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    schema_path = os.path.join(project_root, "schema.sql")

    if not os.path.exists(schema_path):
        pytest.fail(f"Le fichier schema.sql n'a pas été trouvé à l'emplacement: {schema_path}")

    # Récupération du nom de la base de données de test depuis les variables d'environnement
    db_name = os.environ.get("TEST_PGDATABASE")
    if not db_name:
        pytest.fail("La variable d'environnement TEST_PGDATABASE n'est pas définie.")

    try:
        # Construction de la chaîne de connexion complète pour psql
        conn_uri = (
            f"postgresql://{os.environ['TEST_PGUSER']}:{os.environ['TEST_PGPASSWORD']}"
            f"@{os.environ['TEST_PGHOST']}:{os.environ['TEST_PGPORT']}/{db_name}"
        )

        # Exécution de psql avec l'URI de connexion et le fichier de schéma.
        command = f'psql "{conn_uri}" -q -f {schema_path}'
        result = subprocess.run(command, shell=True, capture_output=True, text=True, check=True)

    except subprocess.CalledProcessError as e:
        pytest.fail(f"Échec de l'initialisation du schéma via psql. Erreur: {e.stderr}")
    except KeyError as e:
        pytest.fail(f"Variable d'environnement de test manquante : {e}")
    except Exception as e:
        pytest.fail(f"Une erreur imprévue est survenue lors de l'initialisation de la BDD: {e}")

    yield