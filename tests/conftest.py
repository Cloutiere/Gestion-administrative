# tests/conftest.py
"""
Ce fichier contient les fixtures pytest partagées pour la suite de tests.
Il utilise une base de données SQLite en mémoire et neutralise complètement
l'ancien système de base de données pour des tests purs.
"""
import os
import sys

# Ajoute manuellement le répertoire racine du projet au PYTHONPATH.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
from mon_application import create_app
from mon_application.extensions import db as _db

@pytest.fixture
def app(monkeypatch): # Demande la fixture monkeypatch
    """
    Crée une nouvelle instance de l'application pour chaque test.
    """
    # **LA SOLUTION FINALE ET DÉFINITIVE**
    # Nous patchons les fonctions de l'ANCIEN module de BDD pour qu'elles ne
    # contactent jamais la base PostgreSQL pendant les tests.
    monkeypatch.setattr("mon_application.database.get_all_annees", lambda: [])
    monkeypatch.setattr("mon_application.database.get_annee_courante", lambda: None)

    app = create_app({
        "TESTING": True,
        "SECRET_KEY": "test-secret-key",
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "WTF_CSRF_ENABLED": False,
    })

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