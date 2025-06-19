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


# --- NOUVEAUX TESTS POUR LE CRUD UTILISATEUR ---

def test_api_create_user_success(admin_client, db):
    """Vérifie qu'un utilisateur peut être créé via l'API avec des droits spécifiques."""
    # --- Arrange ---
    champ_math = Champ(champno="061", champnom="Maths")
    champ_sci = Champ(champno="062", champnom="Sciences")
    db.session.add_all([champ_math, champ_sci])
    db.session.commit()

    user_data = {
        "username": "newuser",
        "password": "password123",
        "role": "specific_champs",
        "allowed_champs": ["061"]
    }

    # --- Act ---
    response = admin_client.post("/admin/api/utilisateurs/creer", json=user_data)
    json_response = response.get_json()

    # --- Assert ---
    assert response.status_code == 201
    assert json_response["success"] is True
    assert json_response["user"]["username"] == "newuser"
    assert json_response["user"]["is_admin"] is False
    assert json_response["user"]["allowed_champs"] == ["061"]

    # Vérification en base de données
    created_user = db.session.query(User).filter_by(username="newuser").one()
    assert created_user is not None
    assert created_user.check_password("password123")
    assert not created_user.is_admin
    assert not created_user.is_dashboard_only
    assert len(created_user.champs_autorises) == 1
    assert created_user.champs_autorises[0].champno == "061"


def test_api_create_user_fails_on_duplicate(admin_client):
    """Vérifie que la création échoue si le nom d'utilisateur est déjà pris."""
    # --- Arrange ---
    # L'utilisateur 'testadmin' existe déjà grâce à la fixture admin_client.
    user_data = {
        "username": "testadmin",
        "password": "anotherpassword",
        "role": "admin"
    }

    # --- Act ---
    response = admin_client.post("/admin/api/utilisateurs/creer", json=user_data)
    json_response = response.get_json()

    # --- Assert ---
    assert response.status_code == 409
    assert json_response["success"] is False
    # CORRECTION : On ajuste l'assertion pour correspondre au message réel.
    assert "déjà pris" in json_response["message"]


def test_api_update_user_role_success(admin_client, db):
    """Vérifie la mise à jour du rôle et des permissions d'un utilisateur."""
    # --- Arrange ---
    champ_hist = Champ(champno="070", champnom="Histoire")
    champ_geo = Champ(champno="071", champnom="Géographie")

    user_to_update = User(username="updateme", is_dashboard_only=True)
    user_to_update.set_password("pwd")

    db.session.add_all([champ_hist, champ_geo, user_to_update])
    db.session.commit()

    user_id = user_to_update.id
    update_data = {
        "role": "specific_champs",
        "allowed_champs": ["070", "071"]
    }

    # --- Act ---
    response = admin_client.post(f"/admin/api/utilisateurs/{user_id}/update_role", json=update_data)

    # --- Assert ---
    assert response.status_code == 200
    assert response.get_json()["success"] is True

    # Vérification en base de données
    db.session.expire(user_to_update) # Forcer le rechargement depuis la BDD
    updated_user = db.session.get(User, user_id)
    assert updated_user.is_admin is False
    assert updated_user.is_dashboard_only is False
    assert set(updated_user.allowed_champs) == {"070", "071"}


def test_api_delete_user_success(admin_client, db):
    """Vérifie la suppression réussie d'un utilisateur."""
    # --- Arrange ---
    user_to_delete = User(username="deleteme")
    user_to_delete.set_password("pwd")
    db.session.add(user_to_delete)
    db.session.commit()
    user_id = user_to_delete.id
    assert db.session.get(User, user_id) is not None

    # --- Act ---
    response = admin_client.post(f"/admin/api/utilisateurs/{user_id}/delete")

    # --- Assert ---
    assert response.status_code == 200
    assert response.get_json()["success"] is True
    assert db.session.get(User, user_id) is None


def test_api_delete_user_fails_on_self_delete(admin_client, db):
    """Vérifie qu'un admin ne peut pas se supprimer lui-même."""
    # --- Arrange ---
    # Récupérons l'ID de l'admin actuellement connecté
    admin_user = db.session.query(User).filter_by(username="testadmin").one()
    admin_id = admin_user.id

    # --- Act ---
    response = admin_client.post(f"/admin/api/utilisateurs/{admin_id}/delete")
    json_response = response.get_json()

    # --- Assert ---
    assert response.status_code == 403
    assert json_response["success"] is False
    assert "Vous ne pouvez pas vous supprimer vous-même" in json_response["message"]
    # Vérifier que l'utilisateur est toujours là
    assert db.session.get(User, admin_id) is not None