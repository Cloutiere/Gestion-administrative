# tests/test_admin.py
"""
Tests pour le blueprint 'admin' et ses routes, en accord avec l'architecture
réelle de l'application (pages HTML + endpoints API).
"""

import pytest

from mon_application.models import AnneeScolaire, Champ, Cours, TypeFinancement, User


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
    response = admin_client.get("/admin/utilisateurs")
    assert response.status_code == 200
    assert b"Cr\xc3\xa9er un nouvel utilisateur" in response.data


def test_api_get_all_users_renvoie_les_utilisateurs(admin_client, db):
    """
    Vérifie que l'endpoint API qui alimente la table des utilisateurs
    renvoie bien un JSON avec les bonnes données.
    """
    champ_math = Champ(champno="01", champnom="Mathématiques")
    dashboard_user = User(username="dash_user", is_dashboard_only=True)
    dashboard_user.set_password("pwd")
    specific_user = User(username="specific_user")
    specific_user.set_password("pwd")
    specific_user.champs_autorises.append(champ_math)
    db.session.add_all([champ_math, dashboard_user, specific_user])
    db.session.commit()
    response = admin_client.get("/admin/api/utilisateurs")
    json_data = response.get_json()
    assert response.status_code == 200
    assert json_data["admin_count"] == 1
    usernames_in_response = {user["username"] for user in json_data["users"]}
    assert "testadmin" in usernames_in_response
    assert "dash_user" in usernames_in_response
    assert "specific_user" in usernames_in_response


def test_api_create_user_success(admin_client, db):
    """Vérifie qu'un utilisateur peut être créé via l'API avec des droits spécifiques."""
    champ_math = Champ(champno="061", champnom="Maths")
    db.session.add(champ_math)
    db.session.commit()

    user_data = {"username": "newuser", "password": "password123", "role": "specific_champs", "allowed_champs": ["061"]}

    response = admin_client.post("/admin/api/utilisateurs/creer", json=user_data)
    assert response.status_code == 201

    created_user = db.session.query(User).filter_by(username="newuser").one()
    assert created_user.allowed_champs[0] == "061"


def test_api_create_user_fails_on_duplicate(admin_client):
    """Vérifie que la création échoue si le nom d'utilisateur est déjà pris."""
    user_data = {"username": "testadmin", "password": "anotherpassword", "role": "admin"}
    response = admin_client.post("/admin/api/utilisateurs/creer", json=user_data)
    assert response.status_code == 409
    assert "déjà pris" in response.get_json()["message"]


def test_api_update_user_role_success(admin_client, db):
    """Vérifie la mise à jour du rôle et des permissions d'un utilisateur."""
    champ_hist = Champ(champno="070", champnom="Histoire")
    user_to_update = User(username="updateme", is_dashboard_only=True)
    user_to_update.set_password("pwd")
    db.session.add_all([champ_hist, user_to_update])
    db.session.commit()
    user_id = user_to_update.id
    update_data = {"role": "specific_champs", "allowed_champs": ["070"]}
    response = admin_client.post(f"/admin/api/utilisateurs/{user_id}/update_role", json=update_data)
    assert response.status_code == 200
    updated_user = db.session.get(User, user_id)
    assert updated_user.allowed_champs == ["070"]


def test_api_delete_user_success(admin_client, db):
    """Vérifie la suppression réussie d'un utilisateur."""
    user_to_delete = User(username="deleteme")
    user_to_delete.set_password("pwd")
    db.session.add(user_to_delete)
    db.session.commit()
    user_id = user_to_delete.id
    response = admin_client.post(f"/admin/api/utilisateurs/{user_id}/delete")
    assert response.status_code == 200
    assert db.session.get(User, user_id) is None


def test_api_delete_user_fails_on_self_delete(admin_client, db):
    """Vérifie qu'un admin ne peut pas se supprimer lui-même."""
    admin_user = db.session.query(User).filter_by(username="testadmin").one()
    admin_id = admin_user.id
    response = admin_client.post(f"/admin/api/utilisateurs/{admin_id}/delete")
    assert response.status_code == 403
    assert "Vous ne pouvez pas vous supprimer vous-même" in response.get_json()["message"]


def test_api_get_all_financements_success(admin_client, db):
    """Vérifie que l'API renvoie une liste triée de financements."""
    f1 = TypeFinancement(code="SPO", libelle="Sport-Études")
    f2 = TypeFinancement(code="ADA", libelle="Adaptation Scolaire")
    db.session.add_all([f1, f2])
    db.session.commit()
    response = admin_client.get("/admin/api/financements")
    json_data = response.get_json()
    assert response.status_code == 200
    assert json_data[0]["code"] == "ADA"


def test_api_create_financement_success(admin_client, db):
    """Vérifie la création réussie d'un type de financement."""
    data = {"code": "REG", "libelle": "Régulier"}
    response = admin_client.post("/admin/api/financements/creer", json=data)
    assert response.status_code == 201
    assert db.session.get(TypeFinancement, "REG") is not None


def test_api_create_financement_fails_on_duplicate_code(admin_client, db):
    """Vérifie que la création échoue si le code existe déjà."""
    db.session.add(TypeFinancement(code="REG", libelle="Déjà là"))
    db.session.commit()
    data = {"code": "REG", "libelle": "Nouveau Régulier"}
    response = admin_client.post("/admin/api/financements/creer", json=data)
    assert response.status_code == 409


def test_api_update_financement_success(admin_client, db):
    """Vérifie la mise à jour réussie d'un type de financement."""
    financement = TypeFinancement(code="MOD", libelle="Ancien Libellé")
    db.session.add(financement)
    db.session.commit()
    data = {"libelle": "Nouveau Libellé"}
    response = admin_client.post("/admin/api/financements/MOD/modifier", json=data)
    assert response.status_code == 200
    updated = db.session.get(TypeFinancement, "MOD")
    assert updated.libelle == "Nouveau Libellé"


def test_api_delete_financement_success(admin_client, db):
    """Vérifie la suppression réussie d'un financement non utilisé."""
    db.session.add(TypeFinancement(code="DEL", libelle="À supprimer"))
    db.session.commit()
    response = admin_client.post("/admin/api/financements/DEL/supprimer")
    assert response.status_code == 200
    assert db.session.get(TypeFinancement, "DEL") is None


def test_api_delete_financement_fails_when_in_use(admin_client, db):
    """Vérifie que la suppression échoue si le financement est utilisé par un cours."""
    annee = AnneeScolaire(libelle_annee="2023-2024")
    champ = Champ(champno="061", champnom="Maths")
    financement_utilise = TypeFinancement(code="USED", libelle="Financement en cours d'utilisation")

    # On rend la création des objets plus explicite
    db.session.add_all([annee, champ, financement_utilise])
    db.session.commit()

    cours = Cours(
        codecours="MTH-101",
        annee_id=annee.annee_id,
        champno=champ.champno,
        coursdescriptif="Test",
        nbperiodes=4,
        nbgroupeinitial=1,
        financement_code="USED",
    )
    db.session.add(cours)
    db.session.commit()

    test_cours = db.session.get(Cours, {"codecours": "MTH-101", "annee_id": annee.annee_id})
    assert test_cours is not None
    assert test_cours.financement_code == "USED"

    response = admin_client.post("/admin/api/financements/USED/supprimer")
    json_response = response.get_json()

    assert response.status_code == 409, f"Statut inattendu {response.status_code}. Réponse: {json_response}"
    assert json_response["success"] is False
    # CORRECTION : On vérifie que le message contient une sous-chaîne attendue
    assert "utilisé par des cours" in json_response["message"]
    assert db.session.get(TypeFinancement, "USED") is not None
