# tests/test_api.py
"""
Tests pour le blueprint 'api' et ses routes.
Ces tests valident le comportement des endpoints utilisés par le front-end
pour les opérations CRUD sur les attributions et les enseignants.
"""

import pytest

from mon_application import services
from mon_application.models import (
    AnneeScolaire,
    AttributionCours,
    Champ,
    ChampAnneeStatut,
    Cours,
    Enseignant,
    User,
)


@pytest.fixture
def sample_data(db):
    """
    Fixture pour peupler la base de données avec des entités de base.
    NOTE: Cette fixture ne crée volontairement PAS d'attributions pour permettre
    à chaque test de définir son propre état initial.
    """
    annee = AnneeScolaire(annee_id=1, libelle_annee="2023-2024", est_courante=True)
    champ_math = Champ(champno="MATH", champnom="Mathématiques")
    champ_hist = Champ(champno="HIST", champnom="Histoire")
    db.session.add_all([annee, champ_math, champ_hist])
    db.session.commit()

    ens_math = Enseignant(enseignantid=1, annee_id=annee.annee_id, nom="Turing", prenom="Alan", nomcomplet="Alan Turing", champno="MATH")
    ens_hist = Enseignant(enseignantid=2, annee_id=annee.annee_id, nom="Lovelace", prenom="Ada", nomcomplet="Ada Lovelace", champno="HIST")
    db.session.add_all([ens_math, ens_hist])
    db.session.commit()

    cours_math = Cours(codecours="MTH101", annee_id=annee.annee_id, champno="MATH", coursdescriptif="Calcul Différentiel", nbperiodes=4, nbgroupeinitial=2)
    cours_hist = Cours(codecours="HST101", annee_id=annee.annee_id, champno="HIST", coursdescriptif="Révolution Française", nbperiodes=3, nbgroupeinitial=1)
    db.session.add_all([cours_math, cours_hist])
    db.session.commit()

    return {
        "annee": annee,
        "champ_math": champ_math,
        "champ_hist": champ_hist,
        "ens_math": ens_math,
        "ens_hist": ens_hist,
        "cours_math": cours_math,
        "cours_hist": cours_hist,
    }


@pytest.fixture
def logged_in_client(client, db, sample_data):
    """Fixture qui crée et connecte un utilisateur avec accès au champ 'MATH'."""
    user = User(username="math_teacher")
    user.set_password("password")
    user.champs_autorises.append(sample_data["champ_math"])
    db.session.add(user)
    db.session.commit()

    client.post("/auth/login", data={"username": "math_teacher", "password": "password"})
    yield client


@pytest.fixture
def admin_client(client, db):
    """Fixture qui crée un utilisateur admin et le connecte."""
    admin_user = User(username="admin", is_admin=True)
    admin_user.set_password("password")
    db.session.add(admin_user)
    db.session.commit()
    client.post("/auth/login", data={"username": "admin", "password": "password"})
    yield client


# --- Tests pour /api/attributions/ajouter ---


def test_api_ajouter_attribution_success(logged_in_client, sample_data):
    """Vérifie l'ajout réussi d'une attribution et le payload de la réponse."""
    # GIVEN
    enseignant_id = sample_data["ens_math"].enseignantid
    code_cours = sample_data["cours_math"].codecours
    data = {"enseignant_id": enseignant_id, "code_cours": code_cours}

    # WHEN
    response = logged_in_client.post("/api/attributions/ajouter", json=data)
    json_data = response.get_json()

    # THEN
    assert response.status_code == 201, f"Response data: {json_data}"
    assert json_data["success"] is True
    assert json_data["periodes_enseignant"]["total_periodes"] == 4.0
    assert json_data["groupes_restants_cours"] == 1


def test_api_ajouter_attribution_no_more_groups(admin_client, sample_data):
    """Vérifie que l'ajout échoue si tous les groupes d'un cours sont pris."""
    # GIVEN: Un admin est connecté et le seul groupe du cours d'histoire est pris.
    services.add_attribution_service(sample_data["ens_hist"].enseignantid, sample_data["cours_hist"].codecours, sample_data["annee"].annee_id)

    # WHEN: On essaie de prendre un deuxième groupe pour le même cours
    data = {"enseignant_id": sample_data["ens_hist"].enseignantid, "code_cours": sample_data["cours_hist"].codecours}
    response = admin_client.post("/api/attributions/ajouter", json=data)
    json_data = response.get_json()

    # THEN
    assert response.status_code == 409
    assert json_data["success"] is False
    assert "Plus de groupes disponibles" in json_data["message"]


def test_api_ajouter_attribution_unauthorized_champ(logged_in_client, sample_data):
    """Vérifie que l'ajout échoue si l'utilisateur n'a pas accès au champ."""
    # GIVEN: L'utilisateur 'math_teacher' essaie d'attribuer un cours d'histoire
    data = {"enseignant_id": sample_data["ens_hist"].enseignantid, "code_cours": sample_data["cours_hist"].codecours}

    # WHEN
    response = logged_in_client.post("/api/attributions/ajouter", json=data)
    json_data = response.get_json()

    # THEN
    assert response.status_code == 403
    assert "Accès non autorisé" in json_data["message"]


# --- Tests pour /api/attributions/supprimer ---


def test_api_supprimer_attribution_success(admin_client, sample_data, db):
    """Vérifie la suppression réussie d'une attribution par un admin."""
    # GIVEN: Une attribution existe pour le cours d'histoire.
    attr = AttributionCours(enseignantid=sample_data["ens_hist"].enseignantid, codecours=sample_data["cours_hist"].codecours, annee_id_cours=1)
    db.session.add(attr)
    db.session.commit()
    attribution_id = attr.attributionid

    # WHEN: L'admin supprime cette attribution
    response = admin_client.post("/api/attributions/supprimer", json={"attribution_id": attribution_id})
    json_data = response.get_json()

    # THEN
    assert response.status_code == 200, f"Response data: {json_data}"
    assert json_data["success"] is True
    assert json_data["periodes_enseignant"]["total_periodes"] == 0.0
    assert json_data["groupes_restants_cours"] == 1
    assert db.session.get(AttributionCours, attribution_id) is None


def test_api_supprimer_attribution_unauthorized(logged_in_client, sample_data, db):
    """Vérifie que la suppression échoue si l'utilisateur n'a pas accès au champ."""
    # GIVEN: Une attribution existe pour le cours d'histoire.
    attr = AttributionCours(enseignantid=sample_data["ens_hist"].enseignantid, codecours=sample_data["cours_hist"].codecours, annee_id_cours=1)
    db.session.add(attr)
    db.session.commit()

    # WHEN: L'utilisateur 'math_teacher' (accès MATH) tente de supprimer l'attribution (champ HIST).
    response = logged_in_client.post("/api/attributions/supprimer", json={"attribution_id": attr.attributionid})

    # THEN
    assert response.status_code == 403
    assert "Accès non autorisé" in response.get_json()["message"]
    assert db.session.get(AttributionCours, attr.attributionid) is not None


def test_api_supprimer_attribution_locked_field(logged_in_client, sample_data, db):
    """Vérifie que la suppression échoue si le champ est verrouillé."""
    # GIVEN: Une attribution existe et le champ MATH est verrouillé.
    attr = AttributionCours(enseignantid=sample_data["ens_math"].enseignantid, codecours=sample_data["cours_math"].codecours, annee_id_cours=1)
    lock_status = ChampAnneeStatut(champ_no="MATH", annee_id=1, est_verrouille=True)
    db.session.add_all([attr, lock_status])
    db.session.commit()

    # WHEN: L'utilisateur 'math_teacher' (qui a accès) tente la suppression.
    response = logged_in_client.post("/api/attributions/supprimer", json={"attribution_id": attr.attributionid})

    # THEN
    assert response.status_code == 403
    assert "champ est verrouillé" in response.get_json()["message"]


def test_api_supprimer_attribution_not_found(admin_client):
    """Vérifie la réponse quand l'ID d'attribution n'existe pas."""
    response = admin_client.post("/api/attributions/supprimer", json={"attribution_id": 999})
    assert response.status_code == 404


# --- Tests pour /api/enseignants/<id>/supprimer ---


def test_api_supprimer_enseignant_success(logged_in_client, sample_data, db):
    """Vérifie la suppression d'un enseignant fictif."""
    # GIVEN: Un enseignant fictif est créé dans le champ MATH
    tache_fictive = services.create_fictitious_teacher_service("MATH", sample_data["annee"].annee_id)
    tache_id = tache_fictive["enseignantid"]
    services.add_attribution_service(tache_id, sample_data["cours_math"].codecours, sample_data["annee"].annee_id)

    # WHEN
    response = logged_in_client.post(f"/api/enseignants/{tache_id}/supprimer")
    json_data = response.get_json()

    # THEN
    assert response.status_code == 200
    assert json_data["enseignant_id"] == tache_id
    cours_libere = json_data["cours_liberes_details"][0]
    assert cours_libere["nouveaux_groupes_restants"] == 2
    assert db.session.get(Enseignant, tache_id) is None
