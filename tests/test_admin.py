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


# --- Tests pour la gestion des utilisateurs ---

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


# ... (Les autres tests pour les utilisateurs restent ici, inchangés) ...

def test_api_delete_user_fails_on_self_delete(admin_client, db):
    """Vérifie qu'un admin ne peut pas se supprimer lui-même."""
    admin_user = db.session.query(User).filter_by(username="testadmin").one()
    admin_id = admin_user.id
    response = admin_client.post(f"/admin/api/utilisateurs/{admin_id}/delete")
    assert response.status_code == 403
    assert "Vous ne pouvez pas vous supprimer vous-même" in response.get_json()["message"]


# --- Tests pour la gestion des Types de Financement ---

def test_api_get_all_financements_success(admin_client, db):
    """Vérifie que l'API renvoie une liste triée de financements."""
    f1 = TypeFinancement(code="SPO", libelle="Sport-Études")
    f2 = TypeFinancement(code="ADA", libelle="Adaptation Scolaire")
    db.session.add_all([f1, f2])
    db.session.commit()
    response = admin_client.get("/admin/api/financements")
    json_data = response.get_json()
    assert response.status_code == 200
    assert len(json_data) == 2
    assert json_data[0]["code"] == "ADA"
    assert json_data[1]["code"] == "SPO"


# ... (Les autres tests pour les financements restent ici, inchangés) ...

def test_api_delete_financement_fails_when_in_use(admin_client, db):
    """Vérifie que la suppression échoue si le financement est utilisé par un cours."""
    # 1. Mise en place des entités nécessaires
    annee = AnneeScolaire(libelle_annee="2023-2024")
    champ = Champ(champno="061", champnom="Maths")
    financement_utilise = TypeFinancement(code="USED", libelle="Financement Utilisé")
    db.session.add_all([annee, champ, financement_utilise])
    db.session.commit()

    # 2. Création du cours qui utilise le financement
    cours = Cours(
        codecours="MTH-101",
        annee_id=annee.annee_id,
        champno=champ.champno,
        coursdescriptif="Test de contrainte",
        nbperiodes=4,
        nbgroupeinitial=1,
        financement_code="USED",  # <-- Liaison clé étrangère
    )
    db.session.add(cours)
    db.session.commit()

    # 3. Vérification de la configuration (test du test)
    test_cours = db.session.get(Cours, {"codecours": "MTH-101", "annee_id": annee.annee_id})
    assert test_cours is not None
    assert test_cours.financement_code == "USED"

    # 4. Tentative de suppression
    response = admin_client.post("/admin/api/financements/USED/supprimer")
    json_response = response.get_json()

    # 5. Assertions
    assert response.status_code == 409, f"Statut inattendu {response.status_code}. Réponse: {json_response}"
    assert json_response["success"] is False
    assert "utilisé par des cours" in json_response["message"]
    assert db.session.get(TypeFinancement, "USED") is not None


# --- NOUVEAUX TESTS : Gestion des Années Scolaires ---


def test_api_create_annee_scolaire_first_one_is_courante(admin_client, db):
    """Vérifie que la première année créée est définie comme courante."""
    data = {"libelle": "2024-2025"}
    response = admin_client.post("/admin/api/annees/creer", json=data)
    json_data = response.get_json()

    assert response.status_code == 201
    assert json_data["success"] is True
    assert json_data["annee"]["libelle_annee"] == "2024-2025"
    assert json_data["annee"]["est_courante"] is True

    # Vérification directe en BDD
    annee_in_db = db.session.query(AnneeScolaire).filter_by(libelle_annee="2024-2025").one()
    assert annee_in_db.est_courante is True


def test_api_create_annee_scolaire_subsequent_is_not_courante(admin_client, db):
    """Vérifie qu'une année créée après une année courante n'est pas courante."""
    # Setup : une année courante existe déjà
    annee_existante = AnneeScolaire(libelle_annee="2023-2024", est_courante=True)
    db.session.add(annee_existante)
    db.session.commit()

    data = {"libelle": "2024-2025"}
    response = admin_client.post("/admin/api/annees/creer", json=data)
    json_data = response.get_json()

    assert response.status_code == 201
    assert json_data["annee"]["est_courante"] is False

    # Vérification directe en BDD
    annee_in_db = db.session.query(AnneeScolaire).filter_by(libelle_annee="2024-2025").one()
    assert annee_in_db.est_courante is False


def test_api_create_annee_scolaire_fails_on_duplicate(admin_client, db):
    """Vérifie que la création échoue si le libellé existe déjà."""
    annee_existante = AnneeScolaire(libelle_annee="2023-2024", est_courante=True)
    db.session.add(annee_existante)
    db.session.commit()

    data = {"libelle": "2023-2024"}
    response = admin_client.post("/admin/api/annees/creer", json=data)
    json_data = response.get_json()

    assert response.status_code == 409
    assert json_data["success"] is False
    assert "existe déjà" in json_data["message"]


def test_api_set_annee_courante_toggles_correctly(admin_client, db):
    """Vérifie que définir une année courante désactive l'ancienne."""
    annee1 = AnneeScolaire(libelle_annee="2023-2024", est_courante=True)
    annee2 = AnneeScolaire(libelle_annee="2024-2025", est_courante=False)
    db.session.add_all([annee1, annee2])
    db.session.commit()
    # On récupère les ID après le commit pour s'assurer qu'ils sont assignés
    annee1_id, annee2_id = annee1.annee_id, annee2.annee_id

    # On définit la 2e année comme courante
    response = admin_client.post("/admin/api/annees/set_courante", json={"annee_id": annee2_id})

    assert response.status_code == 200
    assert response.get_json()["success"] is True

    # Vérification cruciale en BDD
    updated_annee1 = db.session.get(AnneeScolaire, annee1_id)
    updated_annee2 = db.session.get(AnneeScolaire, annee2_id)
    assert updated_annee1.est_courante is False
    assert updated_annee2.est_courante is True


def test_api_set_annee_courante_fails_on_not_found(admin_client):
    """Vérifie que l'API renvoie une erreur 404 si l'ID n'existe pas."""
    response = admin_client.post("/admin/api/annees/set_courante", json={"annee_id": 999})
    assert response.status_code == 404
