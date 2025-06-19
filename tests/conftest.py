# tests/conftest.py
import os
import sys
import pytest

# Ajoute manuellement le répertoire racine du projet au PYTHONPATH.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from mon_application import create_app
from mon_application.extensions import db as _db

@pytest.fixture
def app(monkeypatch):
    """
    Crée une nouvelle instance de l'application POUR CHAQUE TEST.
    C'est la clé de l'isolation.
    """
    # Neutralise les appels à l'ancien système de BDD qui polluent les tests.
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