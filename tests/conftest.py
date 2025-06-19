# tests/conftest.py
"""
Ce fichier contient les fixtures pytest partagées pour la suite de tests.
Il utilise une base de données SQLite en mémoire et neutralise les effets
de bord de l'ancien code pour des tests parfaitement isolés.
"""

import logging
import os
import sys
from sqlite3 import Connection as SQLite3Connection

import pytest
from sqlalchemy import event
from sqlalchemy.engine import Engine

# Les imports de notre application sont maintenant ici, au bon endroit.
from mon_application import create_app
from mon_application.extensions import db as _db

# Configuration du logging pour voir les messages de diagnostic
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

# Ajoute manuellement le répertoire racine du projet au PYTHONPATH.
# Cette ligne doit être APRES les imports.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


# DÉFINITION GLOBALE DE L'ÉCOUTEUR D'ÉVÉNEMENT
# S'applique à tous les moteurs SQLAlchemy créés après le chargement de ce module.
@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """Active les contraintes de clé étrangère pour les connexions SQLite."""
    if isinstance(dbapi_connection, SQLite3Connection):
        log.info(">>>> [TEST] Connexion SQLite détectée. Activation de PRAGMA foreign_keys=ON. <<<<")
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


@pytest.fixture
def app(monkeypatch):
    """
    Crée une nouvelle instance de l'application POUR CHAQUE TEST.
    C'est la clé de l'isolation.
    """
    # Règle d'or : On neutralise l'ancien système de BDD pour les tests.
    monkeypatch.setattr("mon_application.load_active_school_year", lambda: None)

    app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "test-secret-key",
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "WTF_CSRF_ENABLED": False,
        }
    )

    with app.app_context():
        _db.create_all()
        yield app
        _db.drop_all()


@pytest.fixture
def client(app):
    """Fixture pour obtenir un client de test Flask."""
    return app.test_client()


@pytest.fixture
def db(app):
    """
    Fixture qui fournit l'objet de base de données.
    """
    return _db
