# tests/test_services.py
"""
Tests unitaires et d'intégration pour la couche de services.
Ces tests valident la logique métier sans passer par la couche HTTP (routes).
Ils interagissent directement avec les fonctions de service et la base de
données de test (SQLite en mémoire) fournie par les fixtures.
"""

import pytest

from mon_application.models import AnneeScolaire, Champ, Cours, Enseignant, TypeFinancement
from mon_application.services import (
    save_imported_courses,
    save_imported_teachers,
    ServiceException,
)


def _setup_initial_data(db):
    """Crée les données de base nécessaires pour les tests (Champs, Année)."""
    annee = AnneeScolaire(annee_id=2024, libelle_annee="2024-2025")
    champ_math = Champ(champno="MATH", champnom="Mathématiques")
    champ_fran = Champ(champno="FRAN", champnom="Français")
    financement_reg = TypeFinancement(code="REG", libelle="Régulier")

    db.session.add_all([annee, champ_math, champ_fran, financement_reg])
    db.session.commit()
    return annee, champ_math, champ_fran, financement_reg


def test_save_imported_courses_success(app, db):
    """
    Vérifie que l'importation de cours réussit, supprime les anciennes
    données et insère correctement les nouvelles.
    """
    # --- Arrange ---
    annee, champ_math, _, _ = _setup_initial_data(db)
    annee_id = annee.annee_id

    # Créer un "ancien" cours qui doit être supprimé
    old_cours = Cours(
        codecours="OLD101",
        annee_id=annee_id,
        champno=champ_math.champno,
        coursdescriptif="Ancien cours",
        nbperiodes=4,
        nbgroupeinitial=1,
    )
    db.session.add(old_cours)
    db.session.commit()
    assert db.session.query(Cours).count() == 1

    # Données à importer
    new_courses_data = [
        {
            "codecours": "MATH101",
            "champno": "MATH",
            "coursdescriptif": "Intro aux maths",
            "nbperiodes": 4,
            "nbgroupeinitial": 2,
            "estcoursautre": False,
            "financement_code": "REG",
        },
        {
            "codecours": "MATH202",
            "champno": "MATH",
            "coursdescriptif": "Maths avancées",
            "nbperiodes": 6,
            "nbgroupeinitial": 1,
            "estcoursautre": False,
            "financement_code": None,
        },
    ]

    # --- Act ---
    stats = save_imported_courses(new_courses_data, annee_id)

    # --- Assert ---
    assert stats.imported_count == 2
    assert stats.deleted_main_entities_count == 1
    assert stats.deleted_attributions_count == 0  # Pas d'attributions à supprimer

    # Vérifier l'état de la base de données
    assert db.session.query(Cours).count() == 2
    assert db.session.query(Cours).filter_by(codecours="OLD101").first() is None
    new_cours_1 = db.session.query(Cours).filter_by(codecours="MATH101").first()
    assert new_cours_1 is not None
    assert new_cours_1.coursdescriptif == "Intro aux maths"
    assert new_cours_1.annee_id == annee_id


def test_save_imported_teachers_success(app, db):
    """
    Vérifie que l'importation d'enseignants réussit, supprime les anciens
    et insère correctement les nouveaux.
    """
    # --- Arrange ---
    annee, champ_math, champ_fran, _ = _setup_initial_data(db)
    annee_id = annee.annee_id

    # Créer un "ancien" enseignant qui doit être supprimé
    old_teacher = Enseignant(
        annee_id=annee_id,
        nomcomplet="Ancien Prof",
        nom="Prof",
        prenom="Ancien",
        champno=champ_math.champno,
    )
    db.session.add(old_teacher)
    db.session.commit()
    assert db.session.query(Enseignant).count() == 1

    # Données à importer
    new_teachers_data = [
        {"nom": "Dupont", "prenom": "Jean", "champno": "MATH", "esttempsplein": True},
        {"nom": "Durand", "prenom": "Marie", "champno": "FRAN", "esttempsplein": False},
    ]

    # --- Act ---
    stats = save_imported_teachers(new_teachers_data, annee_id)

    # --- Assert ---
    assert stats.imported_count == 2
    assert stats.deleted_main_entities_count == 1
    assert stats.deleted_attributions_count == 0

    # Vérifier l'état de la base de données
    assert db.session.query(Enseignant).count() == 2
    assert db.session.query(Enseignant).filter_by(nom="Prof").first() is None
    new_teacher_1 = db.session.query(Enseignant).filter_by(nom="Dupont").first()
    assert new_teacher_1 is not None
    assert new_teacher_1.nomcomplet == "Jean Dupont"
    assert new_teacher_1.annee_id == annee_id


def test_save_imported_courses_rollback_on_invalid_fk(app, db):
    """
    Vérifie que la transaction est annulée si un cours contient
    une clé étrangère (champno) invalide.
    """
    # --- Arrange ---
    annee, _, _, _ = _setup_initial_data(db)
    annee_id = annee.annee_id

    # Données invalides (CHIMIE n'existe pas)
    invalid_courses_data = [
        {
            "codecours": "CHIM101",
            "champno": "CHIMIE",
            "coursdescriptif": "Intro à la chimie",
            "nbperiodes": 4,
            "nbgroupeinitial": 2,
            "estcoursautre": False,
            "financement_code": "REG",
        }
    ]

    # --- Act & Assert ---
    with pytest.raises(ServiceException) as excinfo:
        save_imported_courses(invalid_courses_data, annee_id)

    assert "Erreur d'intégrité" in str(excinfo.value)

    # Vérifier que la DB est vide, prouvant le rollback
    assert db.session.query(Cours).count() == 0