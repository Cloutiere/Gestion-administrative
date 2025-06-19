# tests/test_admin.py
"""
Tests pour le blueprint 'admin' et ses routes, en accord avec l'architecture
réelle de l'application (pages HTML + endpoints API).
"""
import pytest

from mon_application.models import Champ, User
from mon_application.extensions import db


@pytest.fixture
def admin_client(client, db):
    """
    Fixture qui crée un utilisateur admin, le connecte, et retourne le client de test.
    Ceci nous évite de répéter le code de connexion dans chaque test.
    """
    admin_user = User(username="testadmin", is_admin=True)
    admin_user.set_password("a-secure-password")
    db.session.add(admin_user)
    db.session.commit()

    # Connexion de l'utilisateur
    client.post("/auth/login", data={"username": "testadmin", "password": "a-secure-password"})
    yield client


def test_page_administration_utilisateurs_se_charge(admin_client):
    """
    Vérifie que la page HTML (la coquille) de l'administration des utilisateurs
    se charge correctement pour un admin.
    """
    # --- Act ---
    response = admin_client.get("/admin/utilisateurs")

    # --- Assert ---
    assert response.status_code == 200
    # On vérifie la présence d'un élément statique de la coquille HTML.
    assert b"Cr\xc3\xa9er un nouvel utilisateur" in response.data  # Utilise les bytes pour l'encodage


def test_api_get_all_users_renvoie_les_utilisateurs(admin_client, db):
    """
    Vérifie que l'endpoint API qui alimente la table des utilisateurs
    renvoie bien un JSON avec les bonnes données. C'est ici que l'on teste la logique.
    """
    # --- Arrange ---
    # La fixture a déjà créé 'testadmin'.
    # Nous ajoutons les autres utilisateurs comme avant.
    champ_math = Champ(champno="01", champnom="Mathématiques")

    dashboard_user = User()
    dashboard_user.username = "dash_user"
    dashboard_user.is_admin = False
    dashboard_user.is_dashboard_only = True
    dashboard_user.set_password("pwd")

    specific_user = User()
    specific_user.username = "specific_user"
    specific_user.is_admin = False
    specific_user.is_dashboard_only = False
    specific_user.set_password("pwd")
    specific_user.champs_autorises.append(champ_math)

    db.session.add_all([champ_math, dashboard_user, specific_user])
    db.session.commit()

    # --- Act ---
    # On appelle directement l'endpoint API, pas la page HTML.
    response = admin_client.get("/admin/api/utilisateurs")
    json_data = response.get_json()

    # --- Assert ---
    assert response.status_code == 200
    assert "users" in json_data
    assert "admin_count" in json_data
    assert json_data["admin_count"] == 1

    # On extrait les noms d'utilisateurs de la réponse JSON pour une vérification facile.
    usernames_in_response = {user['username'] for user in json_data['users']}

    assert len(usernames_in_response) == 3
    assert "testadmin" in usernames_in_response
    assert "dash_user" in usernames_in_response
    assert "specific_user" in usernames_in_response