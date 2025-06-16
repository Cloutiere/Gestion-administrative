# tests/test_factory.py
"""
Tests pour la factory de l'application et la configuration de base.
"""

from flask import Flask
from flask.testing import FlaskClient


def test_config(app: Flask):
    assert app.config["TESTING"] is True

def test_login_page(client: FlaskClient): # <-- init_database a été retiré
    response = client.get("/auth/login")
    assert response.status_code == 200
    assert b"Connexion" in response.data