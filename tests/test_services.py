# tests/test_services.py
"""
Tests unitaires et d'intégration pour la couche de services.
Ces tests valident la logique métier sans passer par la couche HTTP (routes).
Ils interagissent directement avec les fonctions de service et la base de
données de test (SQLite en mémoire) fournie par les fixtures.
"""

import pytest

from mon_application.models import (
    AnneeScolaire,
    AttributionCours,
    Champ,
    ChampAnneeStatut,
    Cours,
    Enseignant,
    PreparationHoraire,
    TypeFinancement,
)
from mon_application.services import (
    BusinessRuleValidationError,
    DuplicateEntityError,
    EntityNotFoundError,
    ForeignKeyError,
    ServiceException,
    _get_all_teachers_with_details_service,
    add_attribution_service,
    create_course_service,
    create_fictitious_teacher_service,
    create_teacher_service,
    delete_attribution_service,
    delete_course_service,
    delete_teacher_service,
    get_all_champ_statuses_for_year_service,
    get_attributions_for_export_service,
    get_champ_details_service,
    get_course_details_service,
    get_dashboard_summary_service_orm,
    get_data_for_admin_page_service,
    get_org_scolaire_export_data_service,  # NOUVEL IMPORT
    get_preparation_horaire_data_service,
    get_teacher_details_service,
    reassign_course_to_champ_service,
    reassign_course_to_financement_service,
    save_imported_courses,
    save_imported_teachers,
    save_preparation_horaire_service,
    toggle_champ_confirm_service,
    toggle_champ_lock_service,
    update_course_service,
    update_teacher_service,
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


class TestCourseServices:
    """Regroupe les tests pour les services CRUD de l'entité Cours."""

    def test_create_course_success(self, app, db):
        """Vérifie la création réussie d'un cours via le service."""
        annee, champ, _, _ = _setup_initial_data(db)
        data = {
            "codecours": "TEST101",
            "champno": champ.champno,
            "coursdescriptif": "Cours test",
            "nbperiodes": 3.5,
            "nbgroupeinitial": 3,
            "estcoursautre": True,
        }

        created_cours_dict = create_course_service(data, annee.annee_id)
        assert created_cours_dict["codecours"] == "TEST101"
        assert created_cours_dict["coursdescriptif"] == "Cours test"

        cours_in_db = db.session.get(Cours, {"codecours": "TEST101", "annee_id": annee.annee_id})
        assert cours_in_db is not None
        assert cours_in_db.nbgroupeinitial == 3

    def test_create_course_fails_on_duplicate(self, app, db):
        """Vérifie que la création échoue avec la bonne exception en cas de doublon."""
        annee, champ, _, _ = _setup_initial_data(db)
        data = {
            "codecours": "TEST101",
            "champno": champ.champno,
            "coursdescriptif": "Cours test",
            "nbperiodes": 4,
            "nbgroupeinitial": 1,
            "estcoursautre": False,
        }
        create_course_service(data, annee.annee_id)

        with pytest.raises(DuplicateEntityError) as excinfo:
            create_course_service(data, annee.annee_id)
        assert "existe déjà" in str(excinfo.value)

    def test_get_course_details_success(self, app, db):
        """Vérifie que les détails d'un cours sont bien retournés."""
        annee, champ, _, _ = _setup_initial_data(db)
        cours = Cours(
            codecours="TEST101",
            annee_id=annee.annee_id,
            champno=champ.champno,
            coursdescriptif="Détails",
            nbperiodes=5,
            nbgroupeinitial=1,
            estcoursautre=False,
        )
        db.session.add(cours)
        db.session.commit()

        details = get_course_details_service("TEST101", annee.annee_id)
        assert details["coursdescriptif"] == "Détails"
        assert details["nbperiodes"] == 5.0

    def test_get_course_details_fails_on_not_found(self, app, db):
        """Vérifie qu'une exception est levée si le cours n'existe pas."""
        annee, _, _, _ = _setup_initial_data(db)
        with pytest.raises(EntityNotFoundError):
            get_course_details_service("NONEXISTENT", annee.annee_id)

    def test_update_course_success(self, app, db):
        """Vérifie la mise à jour réussie d'un cours."""
        annee, champ, champ_fran, _ = _setup_initial_data(db)
        cours = Cours(
            codecours="TEST101",
            annee_id=annee.annee_id,
            champno=champ.champno,
            coursdescriptif="Original",
            nbperiodes=1,
            nbgroupeinitial=1,
            estcoursautre=False,
        )
        db.session.add(cours)
        db.session.commit()

        update_data = {
            "champno": champ_fran.champno,
            "coursdescriptif": "Modifié",
            "nbperiodes": 9.99,
            "nbgroupeinitial": 99,
            "estcoursautre": True,
        }
        updated_dict = update_course_service("TEST101", annee.annee_id, update_data)
        assert updated_dict["coursdescriptif"] == "Modifié"
        assert updated_dict["champno"] == champ_fran.champno

        cours_in_db = db.session.get(Cours, {"codecours": "TEST101", "annee_id": annee.annee_id})
        assert cours_in_db.coursdescriptif == "Modifié"
        assert float(cours_in_db.nbperiodes) == 9.99

    def test_delete_course_success(self, app, db):
        """Vérifie la suppression réussie d'un cours non utilisé."""
        annee, champ, _, _ = _setup_initial_data(db)
        cours = Cours(
            codecours="TEST101",
            annee_id=annee.annee_id,
            champno=champ.champno,
            coursdescriptif="A supprimer",
            nbperiodes=1,
            nbgroupeinitial=1,
            estcoursautre=False,
        )
        db.session.add(cours)
        db.session.commit()
        assert db.session.query(Cours).count() == 1

        delete_course_service("TEST101", annee.annee_id)
        assert db.session.query(Cours).count() == 0

    def test_delete_course_fails_on_fk_constraint(self, app, db):
        """Vérifie que la suppression échoue si le cours est utilisé par une attribution."""
        annee, champ, _, _ = _setup_initial_data(db)
        cours = Cours(
            codecours="USED101",
            annee_id=annee.annee_id,
            champno=champ.champno,
            coursdescriptif="Utilisé",
            nbperiodes=1,
            nbgroupeinitial=1,
            estcoursautre=False,
        )
        prof = Enseignant(annee_id=annee.annee_id, nomcomplet="Prof Test", nom="Test", prenom="Prof", champno=champ.champno)
        db.session.add_all([cours, prof])
        db.session.commit()

        attribution = AttributionCours(enseignantid=prof.enseignantid, codecours=cours.codecours, annee_id_cours=cours.annee_id)
        db.session.add(attribution)
        db.session.commit()

        with pytest.raises(ForeignKeyError) as excinfo:
            delete_course_service("USED101", annee.annee_id)

        assert "Impossible de supprimer" in str(excinfo.value)
        assert db.session.query(Cours).count() == 1


class TestTeacherServices:
    """Regroupe les tests pour les services CRUD de l'entité Enseignant."""

    def test_create_teacher_success(self, app, db):
        """Vérifie la création réussie d'un enseignant via le service."""
        annee, champ, _, _ = _setup_initial_data(db)
        data = {"nom": "Einstein", "prenom": "Albert", "champno": champ.champno, "esttempsplein": True}

        created_teacher_dict = create_teacher_service(data, annee.annee_id)
        assert created_teacher_dict["nom"] == "Einstein"
        assert created_teacher_dict["nomcomplet"] == "Albert Einstein"

        teacher_in_db = db.session.query(Enseignant).filter_by(nom="Einstein").first()
        assert teacher_in_db is not None
        assert teacher_in_db.nomcomplet == "Albert Einstein"
        assert not teacher_in_db.estfictif

    def test_create_teacher_fails_on_duplicate(self, app, db):
        """Vérifie que la création échoue avec la bonne exception en cas de doublon."""
        annee, champ, _, _ = _setup_initial_data(db)
        data = {"nom": "Curie", "prenom": "Marie", "champno": champ.champno, "esttempsplein": True}
        create_teacher_service(data, annee.annee_id)

        with pytest.raises(DuplicateEntityError) as excinfo:
            create_teacher_service(data, annee.annee_id)
        assert "existe déjà" in str(excinfo.value)

    def test_get_teacher_details_success(self, app, db):
        """Vérifie que les détails d'un enseignant sont bien retournés."""
        annee, champ, _, _ = _setup_initial_data(db)
        teacher = Enseignant(annee_id=annee.annee_id, nom="Nightingale", prenom="Florence", nomcomplet="Florence Nightingale", champno=champ.champno)
        db.session.add(teacher)
        db.session.commit()

        details = get_teacher_details_service(teacher.enseignantid)
        assert details["nom"] == "Nightingale"
        assert details["enseignantid"] == teacher.enseignantid

    def test_get_teacher_details_fails_on_not_found(self, app, db):
        """Vérifie qu'une exception est levée si l'enseignant n'existe pas."""
        _setup_initial_data(db)
        with pytest.raises(EntityNotFoundError):
            get_teacher_details_service(999)

    def test_get_teacher_details_fails_for_fictitious_teacher(self, app, db):
        """Vérifie que le service ne retourne pas d'enseignants fictifs."""
        annee, champ, _, _ = _setup_initial_data(db)
        fictitious_teacher = Enseignant(annee_id=annee.annee_id, nomcomplet="Tâche", champno=champ.champno, estfictif=True)
        db.session.add(fictitious_teacher)
        db.session.commit()

        with pytest.raises(EntityNotFoundError):
            get_teacher_details_service(fictitious_teacher.enseignantid)

    def test_update_teacher_success(self, app, db):
        """Vérifie la mise à jour réussie d'un enseignant."""
        annee, champ_math, champ_fran, _ = _setup_initial_data(db)
        teacher = Enseignant(annee_id=annee.annee_id, nom="Lovelace", prenom="Ada", nomcomplet="Ada Lovelace", champno=champ_math.champno)
        db.session.add(teacher)
        db.session.commit()

        update_data = {"nom": "Byron", "prenom": "Augusta Ada", "champno": champ_fran.champno, "esttempsplein": False}
        updated_dict = update_teacher_service(teacher.enseignantid, update_data)
        assert updated_dict["nom"] == "Byron"
        assert updated_dict["nomcomplet"] == "Augusta Ada Byron"

        teacher_in_db = db.session.get(Enseignant, teacher.enseignantid)
        assert teacher_in_db.nomcomplet == "Augusta Ada Byron"
        assert not teacher_in_db.esttempsplein
        assert teacher_in_db.champno == champ_fran.champno

    def test_delete_teacher_success_no_attributions(self, app, db):
        """Vérifie la suppression d'un enseignant sans attributions."""
        annee, champ, _, _ = _setup_initial_data(db)
        teacher = Enseignant(annee_id=annee.annee_id, nom="Galilei", prenom="Galileo", nomcomplet="Galileo Galilei", champno=champ.champno)
        db.session.add(teacher)
        db.session.commit()
        teacher_id = teacher.enseignantid
        assert db.session.query(Enseignant).count() == 1

        affected_courses = delete_teacher_service(teacher_id)
        assert affected_courses == []
        assert db.session.query(Enseignant).count() == 0

    def test_delete_teacher_with_attributions(self, app, db):
        """Vérifie la suppression d'un enseignant et la cascade sur ses attributions."""
        annee, champ, _, _ = _setup_initial_data(db)
        teacher = Enseignant(annee_id=annee.annee_id, nom="Feynman", prenom="Richard", nomcomplet="Richard Feynman", champno=champ.champno)
        cours = Cours(codecours="PHYS101", annee_id=annee.annee_id, champno=champ.champno, coursdescriptif="QED", nbperiodes=4, nbgroupeinitial=1)
        db.session.add_all([teacher, cours])
        db.session.commit()

        attribution = AttributionCours(enseignantid=teacher.enseignantid, codecours=cours.codecours, annee_id_cours=cours.annee_id)
        db.session.add(attribution)
        db.session.commit()

        teacher_id = teacher.enseignantid
        assert db.session.query(Enseignant).count() == 1
        assert db.session.query(AttributionCours).count() == 1

        affected_courses = delete_teacher_service(teacher_id)

        assert len(affected_courses) == 1
        assert affected_courses[0]["CodeCours"] == "PHYS101"
        assert db.session.query(Enseignant).count() == 0
        assert db.session.query(AttributionCours).count() == 0

    def test_create_fictitious_teacher_service_orm(self, app, db):
        """Vérifie la création et la numérotation correcte des tâches via l'ORM."""
        # --- Arrange ---
        annee, champ_math, champ_fran, _ = _setup_initial_data(db)
        annee_id = annee.annee_id

        # --- Act & Assert ---
        # 1. Créer la première tâche pour MATH, doit être numérotée "1"
        fictif1_math = create_fictitious_teacher_service(champ_math.champno, annee_id)
        assert fictif1_math["nomcomplet"] == "MATH-Tâche restante-1"
        assert fictif1_math["estfictif"] is True
        assert fictif1_math["champno"] == champ_math.champno

        # Vérifier en BDD
        fictif_in_db = db.session.get(Enseignant, fictif1_math["enseignantid"])
        assert fictif_in_db is not None
        assert fictif_in_db.nomcomplet == "MATH-Tâche restante-1"

        # 2. Créer la seconde tâche pour MATH, doit être numérotée "2"
        fictif2_math = create_fictitious_teacher_service(champ_math.champno, annee_id)
        assert fictif2_math["nomcomplet"] == "MATH-Tâche restante-2"

        # 3. Créer la première tâche pour FRAN, doit être numérotée "1" (indépendant)
        fictif1_fran = create_fictitious_teacher_service(champ_fran.champno, annee_id)
        assert fictif1_fran["nomcomplet"] == "FRAN-Tâche restante-1"

        # 4. Vérifier le compte total en BDD
        assert db.session.query(Enseignant).filter_by(estfictif=True).count() == 3
        assert db.session.query(Enseignant).filter_by(estfictif=False).count() == 0


class TestAttributionServices:
    """Regroupe les tests pour les services CRUD de l'entité AttributionCours."""

    def test_add_attribution_success(self, app, db):
        """Vérifie l'ajout réussi d'une attribution."""
        annee, champ, _, _ = _setup_initial_data(db)
        prof = Enseignant(annee_id=annee.annee_id, nom="A", prenom="B", nomcomplet="B A", champno=champ.champno)
        cours = Cours(codecours="C1", annee_id=annee.annee_id, champno=champ.champno, coursdescriptif="D", nbperiodes=1, nbgroupeinitial=1)
        db.session.add_all([prof, cours])
        db.session.commit()

        new_id = add_attribution_service(prof.enseignantid, cours.codecours, annee.annee_id)
        assert isinstance(new_id, int)
        assert db.session.query(AttributionCours).count() == 1

    def test_add_attribution_fails_if_no_groups_left(self, app, db):
        """Vérifie que l'ajout échoue s'il n'y a plus de groupes disponibles."""
        annee, champ, _, _ = _setup_initial_data(db)
        prof = Enseignant(annee_id=annee.annee_id, nom="A", prenom="B", nomcomplet="B A", champno=champ.champno)
        cours = Cours(codecours="C1", annee_id=annee.annee_id, champno=champ.champno, coursdescriptif="D", nbperiodes=1, nbgroupeinitial=1)
        db.session.add_all([prof, cours])
        db.session.commit()
        add_attribution_service(prof.enseignantid, cours.codecours, annee.annee_id)

        with pytest.raises(BusinessRuleValidationError, match="Plus de groupes disponibles"):
            add_attribution_service(prof.enseignantid, cours.codecours, annee.annee_id)

    def test_add_attribution_fails_if_champ_is_locked(self, app, db):
        """Vérifie que l'ajout échoue si le champ de l'enseignant est verrouillé."""
        annee, champ, _, _ = _setup_initial_data(db)
        prof = Enseignant(annee_id=annee.annee_id, nom="A", prenom="B", nomcomplet="B A", champno=champ.champno)
        cours = Cours(codecours="C1", annee_id=annee.annee_id, champno=champ.champno, coursdescriptif="D", nbperiodes=1, nbgroupeinitial=1)
        statut = ChampAnneeStatut(champ_no=champ.champno, annee_id=annee.annee_id, est_verrouille=True)
        db.session.add_all([prof, cours, statut])
        db.session.commit()

        with pytest.raises(BusinessRuleValidationError, match="champ est verrouillé"):
            add_attribution_service(prof.enseignantid, cours.codecours, annee.annee_id)

    def test_add_attribution_succeeds_for_fictitious_teacher_when_locked(self, app, db):
        """Vérifie que l'ajout est permis pour un prof fictif même si le champ est verrouillé."""
        annee, champ, _, _ = _setup_initial_data(db)
        prof_fictif = Enseignant(annee_id=annee.annee_id, nomcomplet="Tâche", champno=champ.champno, estfictif=True)
        cours = Cours(codecours="C1", annee_id=annee.annee_id, champno=champ.champno, coursdescriptif="D", nbperiodes=1, nbgroupeinitial=1)
        statut = ChampAnneeStatut(champ_no=champ.champno, annee_id=annee.annee_id, est_verrouille=True)
        db.session.add_all([prof_fictif, cours, statut])
        db.session.commit()

        add_attribution_service(prof_fictif.enseignantid, cours.codecours, annee.annee_id)
        assert db.session.query(AttributionCours).count() == 1

    def test_delete_attribution_success(self, app, db):
        """Vérifie la suppression réussie d'une attribution."""
        annee, champ, _, _ = _setup_initial_data(db)
        prof = Enseignant(annee_id=annee.annee_id, nom="A", prenom="B", nomcomplet="B A", champno=champ.champno)
        cours = Cours(codecours="C1", annee_id=annee.annee_id, champno=champ.champno, coursdescriptif="D", nbperiodes=1, nbgroupeinitial=1)
        db.session.add_all([prof, cours])
        db.session.commit()
        attr = AttributionCours(enseignantid=prof.enseignantid, codecours=cours.codecours, annee_id_cours=annee.annee_id)
        db.session.add(attr)
        db.session.commit()
        attr_id = attr.attributionid

        result = delete_attribution_service(attr_id)
        assert result["CodeCours"] == "C1"
        assert db.session.query(AttributionCours).count() == 0

    def test_delete_attribution_fails_if_champ_is_locked(self, app, db):
        """Vérifie que la suppression échoue si le champ est verrouillé."""
        annee, champ, _, _ = _setup_initial_data(db)
        prof = Enseignant(annee_id=annee.annee_id, nom="A", prenom="B", nomcomplet="B A", champno=champ.champno)
        cours = Cours(codecours="C1", annee_id=annee.annee_id, champno=champ.champno, coursdescriptif="D", nbperiodes=1, nbgroupeinitial=1)
        statut = ChampAnneeStatut(champ_no=champ.champno, annee_id=annee.annee_id, est_verrouille=True)
        db.session.add_all([prof, cours, statut])
        db.session.commit()
        attr = AttributionCours(enseignantid=prof.enseignantid, codecours=cours.codecours, annee_id_cours=annee.annee_id)
        db.session.add(attr)
        db.session.commit()

        with pytest.raises(BusinessRuleValidationError, match="champ est verrouillé"):
            delete_attribution_service(attr.attributionid)
        assert db.session.query(AttributionCours).count() == 1


class TestChampStatusServices:
    """Regroupe les tests pour les services de bascule de statut de champ."""

    def test_toggle_lock_service_flow(self, app, db):
        """Vérifie la séquence de bascule complète pour le verrouillage."""
        annee, champ, _, _ = _setup_initial_data(db)

        # 1. Premier toggle : Crée l'entrée et la met à True
        nouveau_statut = toggle_champ_lock_service(champ.champno, annee.annee_id)
        assert nouveau_statut is True
        status_in_db = db.session.query(ChampAnneeStatut).one()
        assert status_in_db.est_verrouille is True
        assert status_in_db.est_confirme is False

        # 2. Deuxième toggle : Met à jour à False
        nouveau_statut = toggle_champ_lock_service(champ.champno, annee.annee_id)
        assert nouveau_statut is False
        db.session.refresh(status_in_db)
        assert status_in_db.est_verrouille is False

        # 3. Troisième toggle : Remet à True
        nouveau_statut = toggle_champ_lock_service(champ.champno, annee.annee_id)
        assert nouveau_statut is True
        db.session.refresh(status_in_db)
        assert status_in_db.est_verrouille is True

    def test_toggle_confirm_service_flow(self, app, db):
        """Vérifie la séquence de bascule pour la confirmation."""
        annee, champ, _, _ = _setup_initial_data(db)

        # Premier toggle : Crée l'entrée et la met à True
        nouveau_statut = toggle_champ_confirm_service(champ.champno, annee.annee_id)
        assert nouveau_statut is True
        status_in_db = db.session.query(ChampAnneeStatut).one()
        assert status_in_db.est_confirme is True
        assert status_in_db.est_verrouille is False

    def test_toggles_are_independent(self, app, db):
        """Vérifie que basculer un statut n'affecte pas l'autre."""
        annee, champ, _, _ = _setup_initial_data(db)

        # Verrouiller le champ
        toggle_champ_lock_service(champ.champno, annee.annee_id)
        status_in_db = db.session.query(ChampAnneeStatut).one()
        assert status_in_db.est_verrouille is True
        assert status_in_db.est_confirme is False

        # Confirmer le champ
        toggle_champ_confirm_service(champ.champno, annee.annee_id)
        db.session.refresh(status_in_db)
        assert status_in_db.est_verrouille is True  # Ne doit pas avoir changé
        assert status_in_db.est_confirme is True

    def test_get_all_champ_statuses_for_year_service(self, app, db):
        """Vérifie la récupération des statuts pour une année spécifique via ORM."""
        # --- Arrange ---
        annee, champ_math, champ_fran, _ = _setup_initial_data(db)
        annee2025 = AnneeScolaire(annee_id=2025, libelle_annee="2025-2026")
        champ_scie = Champ(champno="SCIE", champnom="Sciences")
        db.session.add_all([annee2025, champ_scie])

        # Statuts pour l'année 2024 (celle qu'on va tester)
        statut_math_2024 = ChampAnneeStatut(champ_no=champ_math.champno, annee_id=annee.annee_id, est_verrouille=True, est_confirme=True)
        statut_fran_2024 = ChampAnneeStatut(champ_no=champ_fran.champno, annee_id=annee.annee_id, est_verrouille=False, est_confirme=True)

        # Statut pour une autre année (doit être ignoré)
        statut_math_2025 = ChampAnneeStatut(champ_no=champ_math.champno, annee_id=annee2025.annee_id, est_verrouille=True, est_confirme=False)

        db.session.add_all([statut_math_2024, statut_fran_2024, statut_math_2025])
        db.session.commit()

        # --- Act ---
        statuses = get_all_champ_statuses_for_year_service(annee.annee_id)

        # --- Assert ---
        assert isinstance(statuses, dict)
        # Seuls les statuts pour 2024 doivent être retournés
        assert len(statuses) == 2
        # Vérifier le contenu pour MATH
        assert "MATH" in statuses
        assert statuses["MATH"] == {"est_verrouille": True, "est_confirme": True}
        # Vérifier le contenu pour FRAN
        assert "FRAN" in statuses
        assert statuses["FRAN"] == {"est_verrouille": False, "est_confirme": True}
        # Vérifier que SCIE (sans statut) et le statut de 2025 ne sont pas présents
        assert "SCIE" not in statuses

    def test_get_champ_details_service(self, app, db):
        """Vérifie la récupération des détails d'un champ et ses statuts via l'ORM."""
        annee, champ_math, champ_fran, _ = _setup_initial_data(db)
        # Cas 1: Champ avec statut défini
        statut = ChampAnneeStatut(champ_no=champ_math.champno, annee_id=annee.annee_id, est_verrouille=True)
        db.session.add(statut)
        db.session.commit()

        details_math = get_champ_details_service(champ_math.champno, annee.annee_id)
        assert details_math["ChampNo"] == "MATH"
        assert details_math["ChampNom"] == "Mathématiques"
        assert details_math["est_verrouille"] is True
        assert details_math["est_confirme"] is False

        # Cas 2: Champ sans statut défini (devrait retourner les valeurs par défaut)
        details_fran = get_champ_details_service(champ_fran.champno, annee.annee_id)
        assert details_fran["ChampNo"] == "FRAN"
        assert details_fran["ChampNom"] == "Français"
        assert details_fran["est_verrouille"] is False
        assert details_fran["est_confirme"] is False

        # Cas 3: Champ inexistant
        with pytest.raises(EntityNotFoundError):
            get_champ_details_service("INEXISTANT", annee.annee_id)


class TestDashboardServices:
    """Regroupe les tests pour les services liés au tableau de bord."""

    def test_get_dashboard_summary_service_orm_logic(self, app, db):
        """Vérifie la logique de calcul complexe du sommaire du tableau de bord."""
        # --- Arrange ---
        annee, champ_math, champ_fran, _ = _setup_initial_data(db)
        annee_id = annee.annee_id
        champ_scie = Champ(champno="SCIE", champnom="Sciences")
        db.session.add(champ_scie)

        # Enseignants
        tp_math_1 = Enseignant(annee_id=annee_id, nom="Gauss", prenom="Carl", nomcomplet="Carl Gauss", champno="MATH", esttempsplein=True)
        tp_math_2 = Enseignant(annee_id=annee_id, nom="Euler", prenom="Leonhard", nomcomplet="Leonhard Euler", champno="MATH", esttempsplein=True)
        pp_math = Enseignant(annee_id=annee_id, nom="Noether", prenom="Emmy", nomcomplet="Emmy Noether", champno="MATH", esttempsplein=False)
        tp_fran_1 = Enseignant(annee_id=annee_id, nom="Hugo", prenom="Victor", nomcomplet="Victor Hugo", champno="FRAN", esttempsplein=True)
        tp_fran_2 = Enseignant(annee_id=annee_id, nom="Dumas", prenom="Alexandre", nomcomplet="Alexandre Dumas", champno="FRAN", esttempsplein=True)
        fictif_fran = Enseignant(annee_id=annee_id, nomcomplet="Tâche FRAN", champno="FRAN", estfictif=True)
        db.session.add_all([tp_math_1, tp_math_2, pp_math, tp_fran_1, tp_fran_2, fictif_fran])

        # Cours
        cours_m1 = Cours(codecours="M1", annee_id=annee_id, champno="MATH", coursdescriptif="Algèbre", nbperiodes=2.5, nbgroupeinitial=1)
        cours_m2 = Cours(codecours="M2", annee_id=annee_id, champno="MATH", coursdescriptif="Analyse", nbperiodes=3.0, nbgroupeinitial=1)
        cours_f1 = Cours(codecours="F1", annee_id=annee_id, champno="FRAN", coursdescriptif="Littérature", nbperiodes=4.0, nbgroupeinitial=1)
        db.session.add_all([cours_m1, cours_m2, cours_f1])
        db.session.commit()

        # Attributions
        db.session.add_all(
            [
                AttributionCours(enseignantid=tp_math_1.enseignantid, codecours="M1", annee_id_cours=annee_id),  # 2.5 p
                AttributionCours(enseignantid=tp_math_2.enseignantid, codecours="M2", annee_id_cours=annee_id),  # 3.0 p
                AttributionCours(enseignantid=pp_math.enseignantid, codecours="M1", annee_id_cours=annee_id),  # Non compté
                AttributionCours(enseignantid=tp_fran_1.enseignantid, codecours="F1", annee_id_cours=annee_id),  # 4.0 p
                AttributionCours(enseignantid=fictif_fran.enseignantid, codecours="F1", annee_id_cours=annee_id),  # Non compté
            ]
        )

        # Statuts de champ
        db.session.add(ChampAnneeStatut(champ_no="MATH", annee_id=annee_id, est_confirme=True))
        db.session.add(ChampAnneeStatut(champ_no="FRAN", annee_id=annee_id, est_verrouille=True))
        db.session.commit()

        # --- Act ---
        summary = get_dashboard_summary_service_orm(annee_id)

        # --- Assert ---
        assert "moyennes_par_champ" in summary
        champs_summary = summary["moyennes_par_champ"]
        assert len(champs_summary) == 3  # MATH, FRAN, SCIE

        # Vérification pour MATH (confirmé)
        math_summary = champs_summary["MATH"]
        assert math_summary["champ_nom"] == "Mathématiques"
        assert math_summary["est_verrouille"] is False
        assert math_summary["est_confirme"] is True
        assert math_summary["nb_enseignants_tp"] == 2  # Gauss, Euler
        assert math_summary["periodes_choisies_tp"] == pytest.approx(2.5 + 3.0)
        assert math_summary["moyenne"] == pytest.approx((2.5 + 3.0) / 2)
        assert math_summary["periodes_magiques"] == pytest.approx(5.5 - (2 * 24))

        # Vérification pour FRAN (verrouillé)
        fran_summary = champs_summary["FRAN"]
        assert fran_summary["champ_nom"] == "Français"
        assert fran_summary["est_verrouille"] is True
        assert fran_summary["est_confirme"] is False
        assert fran_summary["nb_enseignants_tp"] == 2  # Hugo, Dumas
        assert fran_summary["periodes_choisies_tp"] == pytest.approx(4.0)  # Dumas a 0 période
        assert fran_summary["moyenne"] == pytest.approx(4.0 / 2)
        assert fran_summary["periodes_magiques"] == pytest.approx(4.0 - (2 * 24))

        # Vérification pour SCIE (aucun enseignant, aucun statut)
        scie_summary = champs_summary["SCIE"]
        assert scie_summary["champ_nom"] == "Sciences"
        assert scie_summary["est_verrouille"] is False
        assert scie_summary["est_confirme"] is False
        assert scie_summary["nb_enseignants_tp"] == 0
        assert scie_summary["periodes_choisies_tp"] == 0.0
        assert scie_summary["moyenne"] == 0.0
        assert scie_summary["periodes_magiques"] == 0.0

        # Vérification des totaux et moyennes globales
        grand_totals = summary["grand_totals"]
        assert grand_totals["total_enseignants_tp"] == 4  # 2 MATH + 2 FRAN
        assert grand_totals["total_periodes_choisies_tp"] == pytest.approx(5.5 + 4.0)
        assert grand_totals["total_periodes_magiques"] == pytest.approx((5.5 - 48) + (4.0 - 48))

        assert summary["moyenne_generale"] == pytest.approx(9.5 / 4)
        # Seul MATH est confirmé
        assert summary["moyenne_preliminaire_confirmee"] == pytest.approx(5.5 / 2)


class TestTaskPageServices:
    """
    Regroupe les tests pour les services qui fournissent des données à la
    page principale des tâches.
    """

    def test_get_all_teachers_with_details_service(self, app, db):
        """
        Vérifie que le service ORM récupère correctement tous les enseignants,
        leurs attributions et calcule les totaux de périodes avec précision.
        """
        # --- Arrange ---
        annee, champ_math, champ_fran, _ = _setup_initial_data(db)
        annee_id = annee.annee_id

        # Enseignants
        prof_a = Enseignant(annee_id=annee_id, nom="A", prenom="Prof", nomcomplet="Prof A", champno="MATH")
        prof_b = Enseignant(annee_id=annee_id, nom="B", prenom="Prof", nomcomplet="Prof B", champno="FRAN", esttempsplein=False)
        prof_fictif = Enseignant(annee_id=annee_id, nomcomplet="Tâche MATH", champno="MATH", estfictif=True)
        prof_sans_cours = Enseignant(annee_id=annee_id, nom="C", prenom="Prof", nomcomplet="Prof C", champno="MATH")
        db.session.add_all([prof_a, prof_b, prof_fictif, prof_sans_cours])

        # Cours
        cours_math1 = Cours(codecours="M1", annee_id=annee_id, champno="MATH", coursdescriptif="Algèbre", nbperiodes=2.5, nbgroupeinitial=2)
        cours_math2_autre = Cours(codecours="M2", annee_id=annee_id, champno="MATH", coursdescriptif="Soutien", nbperiodes=1.5, nbgroupeinitial=1, estcoursautre=True)
        cours_fran1 = Cours(codecours="F1", annee_id=annee_id, champno="FRAN", coursdescriptif="Grammaire", nbperiodes=4.0, nbgroupeinitial=1)
        db.session.add_all([cours_math1, cours_math2_autre, cours_fran1])
        db.session.commit()

        # Attributions
        attr1 = AttributionCours(enseignantid=prof_a.enseignantid, codecours="M1", annee_id_cours=annee_id, nbgroupespris=1)
        attr2 = AttributionCours(enseignantid=prof_a.enseignantid, codecours="M2", annee_id_cours=annee_id, nbgroupespris=1)
        attr3 = AttributionCours(enseignantid=prof_b.enseignantid, codecours="F1", annee_id_cours=annee_id, nbgroupespris=1)
        attr4 = AttributionCours(enseignantid=prof_fictif.enseignantid, codecours="M1", annee_id_cours=annee_id, nbgroupespris=1)
        db.session.add_all([attr1, attr2, attr3, attr4])
        db.session.commit()

        # --- Act ---
        result = _get_all_teachers_with_details_service(annee_id)

        # --- Assert ---
        assert len(result) == 4  # Les 4 enseignants créés
        assert all("attributions" in r and "periodes" in r for r in result)

        # Dictionnaire pour un accès facile
        result_by_name = {r["nomcomplet"]: r for r in result}

        # Vérification détaillée pour Prof A
        prof_a_data = result_by_name["Prof A"]
        assert prof_a_data["nom"] == "A"
        assert prof_a_data["esttempsplein"] is True
        assert len(prof_a_data["attributions"]) == 2
        periodes = prof_a_data["periodes"]
        assert periodes["periodes_cours"] == pytest.approx(2.5)
        assert periodes["periodes_autres"] == pytest.approx(1.5)
        assert periodes["total_periodes"] == pytest.approx(4.0)

        # Vérification détaillée pour Prof B
        prof_b_data = result_by_name["Prof B"]
        assert prof_b_data["esttempsplein"] is False
        assert len(prof_b_data["attributions"]) == 1
        assert prof_b_data["attributions"][0]["CodeCours"] == "F1"
        periodes_b = prof_b_data["periodes"]
        assert periodes_b["periodes_cours"] == pytest.approx(4.0)
        assert periodes_b["periodes_autres"] == 0.0
        assert periodes_b["total_periodes"] == pytest.approx(4.0)

        # Vérification pour l'enseignant sans cours
        prof_c_data = result_by_name["Prof C"]
        assert len(prof_c_data["attributions"]) == 0
        periodes_c = prof_c_data["periodes"]
        assert periodes_c["periodes_cours"] == 0.0
        assert periodes_c["periodes_autres"] == 0.0
        assert periodes_c["total_periodes"] == 0.0

        # Vérification pour l'enseignant fictif
        prof_fictif_data = result_by_name["Tâche MATH"]
        assert prof_fictif_data["estfictif"] is True
        assert len(prof_fictif_data["attributions"]) == 1
        periodes_f = prof_fictif_data["periodes"]
        assert periodes_f["periodes_cours"] == pytest.approx(2.5)
        assert periodes_f["periodes_autres"] == 0.0
        assert periodes_f["total_periodes"] == pytest.approx(2.5)


class TestAdminPageServices:
    """Regroupe les tests pour les services de la page d'administration."""

    def test_get_data_for_admin_page_service_orm(self, app, db):
        """Vérifie que les données pour la page admin sont correctement groupées par l'ORM."""
        # --- Arrange ---
        annee, champ_math, champ_fran, _ = _setup_initial_data(db)
        annee_id = annee.annee_id
        # Données de test
        cours_m1 = Cours(annee_id=annee_id, codecours="M1", champno="MATH", coursdescriptif="M1 desc", nbperiodes=1, nbgroupeinitial=1)
        cours_m2 = Cours(annee_id=annee_id, codecours="M2", champno="MATH", coursdescriptif="M2 desc", nbperiodes=1, nbgroupeinitial=1)
        cours_f1 = Cours(annee_id=annee_id, codecours="F1", champno="FRAN", coursdescriptif="F1 desc", nbperiodes=1, nbgroupeinitial=1)
        ens_math = Enseignant(annee_id=annee_id, nom="E-Math", prenom="P", nomcomplet="P E-Math", champno="MATH")
        ens_fran = Enseignant(annee_id=annee_id, nom="E-Fran", prenom="P", nomcomplet="P E-Fran", champno="FRAN")
        # Enseignant fictif qui ne doit pas apparaître
        ens_fictif = Enseignant(annee_id=annee_id, nomcomplet="Fictif", champno="MATH", estfictif=True)
        db.session.add_all([cours_m1, cours_m2, cours_f1, ens_math, ens_fran, ens_fictif])
        db.session.commit()

        # --- Act ---
        data = get_data_for_admin_page_service(annee_id)

        # --- Assert ---
        assert "cours_par_champ" in data
        assert "enseignants_par_champ" in data
        assert "tous_les_champs" in data
        assert "tous_les_financements" in data

        # Vérification des cours
        cours_par_champ = data["cours_par_champ"]
        assert "MATH" in cours_par_champ
        assert "FRAN" in cours_par_champ
        assert len(cours_par_champ["MATH"]["cours"]) == 2
        assert cours_par_champ["MATH"]["cours"][0]["codecours"] == "M1"
        assert cours_par_champ["FRAN"]["champ_nom"] == "Français"
        assert len(cours_par_champ["FRAN"]["cours"]) == 1

        # Vérification des enseignants
        enseignants_par_champ = data["enseignants_par_champ"]
        assert "MATH" in enseignants_par_champ
        assert len(enseignants_par_champ["MATH"]["enseignants"]) == 1
        assert enseignants_par_champ["MATH"]["enseignants"][0]["nom"] == "E-Math"
        assert "FRAN" in enseignants_par_champ
        assert len(enseignants_par_champ["FRAN"]["enseignants"]) == 1

    def test_reassign_course_to_champ_service_success(self, app, db):
        """Vérifie la réassignation réussie d'un cours à un autre champ."""
        annee, champ_math, champ_fran, _ = _setup_initial_data(db)
        cours = Cours(annee_id=annee.annee_id, codecours="C1", champno="MATH", coursdescriptif="D", nbperiodes=1, nbgroupeinitial=1)
        db.session.add(cours)
        db.session.commit()

        result = reassign_course_to_champ_service("C1", annee.annee_id, "FRAN")

        assert result["nouveau_champ_no"] == "FRAN"
        assert result["nouveau_champ_nom"] == "Français"
        db.session.refresh(cours)
        assert cours.champno == "FRAN"

    def test_reassign_course_to_champ_service_fails(self, app, db):
        """Vérifie les cas d'échec de la réassignation de champ."""
        annee, _, _, _ = _setup_initial_data(db)
        # Échec si le cours n'existe pas
        with pytest.raises(EntityNotFoundError):
            reassign_course_to_champ_service("C-NON", annee.annee_id, "MATH")

        # Échec si le champ de destination n'existe pas
        cours = Cours(annee_id=annee.annee_id, codecours="C1", champno="MATH", coursdescriptif="D", nbperiodes=1, nbgroupeinitial=1)
        db.session.add(cours)
        db.session.commit()
        with pytest.raises(BusinessRuleValidationError):
            reassign_course_to_champ_service("C1", annee.annee_id, "CHAMP-NON")

    def test_reassign_course_to_financement_service_success(self, app, db):
        """Vérifie la réassignation réussie d'un cours à un financement."""
        annee, champ_math, _, financement_reg = _setup_initial_data(db)
        fin_spe = TypeFinancement(code="SPE", libelle="Spécial")
        cours = Cours(annee_id=annee.annee_id, codecours="C1", champno="MATH", coursdescriptif="D", nbperiodes=1, nbgroupeinitial=1)
        db.session.add_all([fin_spe, cours])
        db.session.commit()
        assert cours.financement_code is None

        # Assignation
        reassign_course_to_financement_service("C1", annee.annee_id, "REG")
        db.session.refresh(cours)
        assert cours.financement_code == "REG"

        # Changement
        reassign_course_to_financement_service("C1", annee.annee_id, "SPE")
        db.session.refresh(cours)
        assert cours.financement_code == "SPE"

        # Désassignation
        reassign_course_to_financement_service("C1", annee.annee_id, None)
        db.session.refresh(cours)
        assert cours.financement_code is None

    def test_reassign_course_to_financement_service_fails(self, app, db):
        """Vérifie les cas d'échec de la réassignation de financement."""
        annee, champ_math, _, _ = _setup_initial_data(db)
        cours = Cours(annee_id=annee.annee_id, codecours="C1", champno="MATH", coursdescriptif="D", nbperiodes=1, nbgroupeinitial=1)
        db.session.add(cours)
        db.session.commit()

        # Échec si le cours n'existe pas
        with pytest.raises(EntityNotFoundError):
            reassign_course_to_financement_service("C-NON", annee.annee_id, "REG")

        # Échec si le financement n'existe pas
        with pytest.raises(BusinessRuleValidationError):
            reassign_course_to_financement_service("C1", annee.annee_id, "FIN-NON")


class TestPreparationHoraireServices:
    """Regroupe les tests pour les services de Préparation de l'horaire refactorisés."""

    def _setup_preparation_data(self, db, annee, champ):
        """Helper pour créer les données de base pour les tests d'horaire."""
        # Un cours avec 3 groupes disponibles
        cours = Cours(annee_id=annee.annee_id, codecours="MATH101", champno=champ.champno, coursdescriptif="Algèbre 1", nbgroupeinitial=3, nbperiodes=1)
        # Un enseignant non-fictif
        prof = Enseignant(annee_id=annee.annee_id, nom="Turing", prenom="Alan", nomcomplet="Alan Turing", champno=champ.champno)
        db.session.add_all([cours, prof])
        db.session.commit()

        # Attribuer 2 des 3 groupes à cet enseignant
        attr = AttributionCours(enseignantid=prof.enseignantid, codecours=cours.codecours, annee_id_cours=annee.annee_id, nbgroupespris=2)
        db.session.add(attr)
        db.session.commit()
        return cours, prof

    def test_get_preparation_horaire_data_service_orm(self, app, db):
        """Vérifie que la récupération des données pour l'horaire via l'ORM est correcte."""
        # --- Arrange ---
        annee, champ_math, _, _ = _setup_initial_data(db)
        cours, prof = self._setup_preparation_data(db, annee, champ_math)

        # Pré-sauvegarder une assignation pour vérifier la grille
        saved_assignment = PreparationHoraire(
            annee_id=annee.annee_id,
            secondaire_level=1,
            codecours=cours.codecours,
            annee_id_cours=annee.annee_id,
            enseignant_id=prof.enseignantid,
            colonne_assignee="col1",
        )
        db.session.add(saved_assignment)
        db.session.commit()

        # --- Act ---
        data = get_preparation_horaire_data_service(annee.annee_id)

        # --- Assert ---
        # 1. Vérifier la structure générale
        assert "all_champs" in data
        assert "cours_par_champ" in data
        assert "enseignants_par_cours" in data
        assert "prepared_grid" in data

        # 2. Vérifier que les cours sont corrects
        assert "MATH" in data["cours_par_champ"]
        assert len(data["cours_par_champ"]["MATH"]) == 1
        assert data["cours_par_champ"]["MATH"][0]["codecours"] == "MATH101"

        # 3. Vérifier que les groupes sont "dépliés"
        enseignants = data["enseignants_par_cours"]["MATH101"]
        assert len(enseignants) == 2  # nbgroupespris=2
        assert enseignants[0]["enseignantid"] == prof.enseignantid
        assert enseignants[1]["enseignantid"] == prof.enseignantid

        # 4. Vérifier la grille pré-remplie
        grid = data["prepared_grid"]
        assert len(grid[1]) == 1  # Un seul cours au niveau 1
        grid_item = grid[1][0]
        assert grid_item["cours"]["codecours"] == "MATH101"
        assert "col1" in grid_item["assigned_teachers_by_col"]
        assert grid_item["assigned_teachers_by_col"]["col1"] == [prof.enseignantid]
        # Un enseignant non assigné (le 2ème groupe)
        assert len(grid_item["unassigned_teachers"]) == 1
        assert grid_item["unassigned_teachers"][0]["enseignantid"] == prof.enseignantid

    def test_save_preparation_horaire_service_orm_transaction(self, app, db):
        """Vérifie la nature transactionnelle de la sauvegarde (supprimer puis insérer)."""
        # --- Arrange ---
        annee, champ_math, _, _ = _setup_initial_data(db)
        cours, prof = self._setup_preparation_data(db, annee, champ_math)
        assert db.session.query(PreparationHoraire).count() == 0

        # --- Act 1 & Assert 1: Sauvegarde initiale ---
        assignments_1 = [
            {
                "secondaire_level": 1,
                "codecours": cours.codecours,
                "annee_id_cours": annee.annee_id,
                "enseignant_id": prof.enseignantid,
                "colonne_assignee": "col1",
            },
            {
                "secondaire_level": 1,
                "codecours": cours.codecours,
                "annee_id_cours": annee.annee_id,
                "enseignant_id": prof.enseignantid,
                "colonne_assignee": "col2",
            },
        ]
        save_preparation_horaire_service(annee.annee_id, assignments_1)
        assert db.session.query(PreparationHoraire).count() == 2

        # --- Act 2 & Assert 2: Remplacer par de nouvelles données ---
        assignments_2 = [
            {
                "secondaire_level": 2,
                "codecours": cours.codecours,
                "annee_id_cours": annee.annee_id,
                "enseignant_id": prof.enseignantid,
                "colonne_assignee": "colA",
            }
        ]
        save_preparation_horaire_service(annee.annee_id, assignments_2)
        assert db.session.query(PreparationHoraire).count() == 1
        saved = db.session.query(PreparationHoraire).one()
        assert saved.secondaire_level == 2
        assert saved.colonne_assignee == "colA"

        # --- Act 3 & Assert 3: Vider les données ---
        save_preparation_horaire_service(annee.annee_id, [])
        assert db.session.query(PreparationHoraire).count() == 0

    def test_save_preparation_horaire_service_orm_fails_on_invalid_data(self, app, db):
        """Vérifie que le service lève une exception si les données sont mal formées."""
        annee, _, _, _ = _setup_initial_data(db)
        # Données avec une clé manquante ("enseignant_id")
        invalid_assignments = [{"secondaire_level": 1, "codecours": "C1", "annee_id_cours": annee.annee_id, "colonne_assignee": "col1"}]
        with pytest.raises(BusinessRuleValidationError, match="invalides ou incomplètes"):
            save_preparation_horaire_service(annee.annee_id, invalid_assignments)


# NOUVELLE CLASSE DE TESTS POUR LES SERVICES D'EXPORT
class TestExportServices:
    """Regroupe les tests pour les services d'export refactorisés avec l'ORM."""

    def test_get_attributions_for_export_service_orm(self, app, db):
        """
        Vérifie que le service d'export des attributions retourne les bonnes données,
        agrège correctement les groupes et exclut les enseignants fictifs.
        """
        # --- Arrange ---
        annee, champ_math, champ_fran, _ = _setup_initial_data(db)
        annee_id = annee.annee_id

        # Enseignants (réels et fictif)
        prof_a_math = Enseignant(annee_id=annee_id, nom="Archimède", prenom="Syra", nomcomplet="Syra Archimède", champno="MATH")
        prof_b_math = Enseignant(annee_id=annee_id, nom="Zeno", prenom="Citium", nomcomplet="Citium Zeno", champno="MATH")
        prof_c_fran = Enseignant(annee_id=annee_id, nom="Voltaire", prenom="François", nomcomplet="François Voltaire", champno="FRAN")
        prof_fictif = Enseignant(annee_id=annee_id, nomcomplet="Tâche MATH", champno="MATH", estfictif=True)
        db.session.add_all([prof_a_math, prof_b_math, prof_c_fran, prof_fictif])

        # Cours
        cours_m1 = Cours(codecours="M1", annee_id=annee_id, champno="MATH", coursdescriptif="Géométrie", nbperiodes=4.0, nbgroupeinitial=5)
        cours_m2 = Cours(codecours="M2", annee_id=annee_id, champno="MATH", coursdescriptif="Calcul", nbperiodes=5.0, nbgroupeinitial=3)
        cours_f1 = Cours(codecours="F1", annee_id=annee_id, champno="FRAN", coursdescriptif="Candide", nbperiodes=3.0, nbgroupeinitial=2)
        db.session.add_all([cours_m1, cours_m2, cours_f1])
        db.session.commit()

        # Attributions
        # Prof A prend 1 groupe de M1
        attr1 = AttributionCours(enseignantid=prof_a_math.enseignantid, codecours="M1", annee_id_cours=annee_id, nbgroupespris=1)
        # Prof A prend 2 groupes de M2 (via 2 attributions distinctes pour tester le SUM)
        attr2 = AttributionCours(enseignantid=prof_a_math.enseignantid, codecours="M2", annee_id_cours=annee_id, nbgroupespris=1)
        attr3 = AttributionCours(enseignantid=prof_a_math.enseignantid, codecours="M2", annee_id_cours=annee_id, nbgroupespris=1)
        # Prof B prend 1 groupe de M1
        attr4 = AttributionCours(enseignantid=prof_b_math.enseignantid, codecours="M1", annee_id_cours=annee_id, nbgroupespris=1)
        # Prof C prend 1 groupe de F1
        attr5 = AttributionCours(enseignantid=prof_c_fran.enseignantid, codecours="F1", annee_id_cours=annee_id, nbgroupespris=1)
        # Le prof fictif prend 1 groupe de M1 (doit être ignoré)
        attr_fictif = AttributionCours(enseignantid=prof_fictif.enseignantid, codecours="M1", annee_id_cours=annee_id, nbgroupespris=1)
        db.session.add_all([attr1, attr2, attr3, attr4, attr5, attr_fictif])
        db.session.commit()

        # --- Act ---
        result = get_attributions_for_export_service(annee_id)

        # --- Assert ---
        # 1. Structure générale et clés de champ
        assert isinstance(result, dict)
        assert "MATH" in result
        assert "FRAN" in result
        assert len(result.keys()) == 2

        # 2. Vérification du champ MATH
        math_data = result["MATH"]
        assert math_data["nom"] == "Mathématiques"
        assert len(math_data["attributions"]) == 3  # A(M1), A(M2), B(M1)

        # L'ordre doit être Archimède(M1), Archimède(M2), Zeno(M1)
        attributions_math = math_data["attributions"]
        assert attributions_math[0]["nom"] == "Archimède" and attributions_math[0]["codecours"] == "M1"
        assert attributions_math[1]["nom"] == "Archimède" and attributions_math[1]["codecours"] == "M2"
        assert attributions_math[2]["nom"] == "Zeno" and attributions_math[2]["codecours"] == "M1"

        # 3. Vérification de l'agrégation (le point crucial)
        attr_archimede_m2 = next(a for a in attributions_math if a["nom"] == "Archimède" and a["codecours"] == "M2")
        assert attr_archimede_m2["total_groupes_pris"] == 2
        assert attr_archimede_m2["prenom"] == "Syra"

        # 4. Vérification d'une attribution simple
        attr_archimede_m1 = next(a for a in attributions_math if a["nom"] == "Archimède" and a["codecours"] == "M1")
        assert attr_archimede_m1["total_groupes_pris"] == 1

        # 5. Vérification du champ FRAN
        fran_data = result["FRAN"]
        assert fran_data["nom"] == "Français"
        assert len(fran_data["attributions"]) == 1
        assert fran_data["attributions"][0]["nom"] == "Voltaire"
        assert fran_data["attributions"][0]["total_groupes_pris"] == 1

    def test_get_attributions_for_export_service_orm_empty(self, app, db):
        """Vérifie que le service retourne un dictionnaire vide si aucune attribution n'existe."""
        annee, _, _, _ = _setup_initial_data(db)
        # Aucune attribution n'est créée

        result = get_attributions_for_export_service(annee.annee_id)
        assert result == {}

    def test_get_org_scolaire_export_data_service_orm(self, app, db):
        """
        Teste la logique complexe de l'export Organisation Scolaire, incluant le pivotage,
        l'agrégation, la gestion des non-attribués et le tri.
        """
        # --- Arrange ---
        # Données de base
        annee, champ_math, champ_fran, _ = _setup_initial_data(db)
        annee_id = annee.annee_id
        fin_sport = TypeFinancement(code="SPORT", libelle="Sport-Études")
        db.session.add(fin_sport)

        # Enseignants pour tester le tri et les champs
        prof_b_math = Enseignant(annee_id=annee_id, nom="Babbage", prenom="Charles", nomcomplet="Charles Babbage", champno="MATH")
        prof_a_math = Enseignant(annee_id=annee_id, nom="Archimede", prenom="Syra", nomcomplet="Syra Archimede", champno="MATH")
        prof_c_fran = Enseignant(annee_id=annee_id, nom="Camus", prenom="Albert", nomcomplet="Albert Camus", champno="FRAN")
        tache_math_10 = Enseignant(annee_id=annee_id, nomcomplet="MATH-Tâche restante-10", champno="MATH", estfictif=True)
        tache_math_2 = Enseignant(annee_id=annee_id, nomcomplet="MATH-Tâche restante-2", champno="MATH", estfictif=True)
        db.session.add_all([prof_a_math, prof_b_math, prof_c_fran, tache_math_2, tache_math_10])

        # Cours
        # Cours régulier entièrement attribué à Prof A
        cours_m1_reg = Cours(codecours="M1R", annee_id=annee_id, champno="MATH", coursdescriptif="Arithmétique", nbperiodes=2.0, nbgroupeinitial=1)
        # Cours spécial entièrement attribué à Tâche 2
        cours_m2_sport = Cours(codecours="M2S", annee_id=annee_id, champno="MATH", coursdescriptif="Stats Sport", nbperiodes=1.5, nbgroupeinitial=1, financement_code="SPORT")
        # Cours partiellement attribué (2/3 groupes), reste 1 groupe non attribué
        cours_f1_part = Cours(codecours="F1P", annee_id=annee_id, champno="FRAN", coursdescriptif="Grammaire", nbperiodes=3.0, nbgroupeinitial=3)
        # Cours entièrement non attribué
        cours_f2_unassigned = Cours(codecours="F2U", annee_id=annee_id, champno="FRAN", coursdescriptif="Poésie", nbperiodes=2.5, nbgroupeinitial=2)
        db.session.add_all([cours_m1_reg, cours_m2_sport, cours_f1_part, cours_f2_unassigned])
        db.session.commit()

        # Attributions
        db.session.add_all(
            [
                AttributionCours(enseignantid=prof_a_math.enseignantid, codecours="M1R", annee_id_cours=annee_id, nbgroupespris=1),
                AttributionCours(enseignantid=tache_math_2.enseignantid, codecours="M2S", annee_id_cours=annee_id, nbgroupespris=1),
                AttributionCours(enseignantid=prof_c_fran.enseignantid, codecours="F1P", annee_id_cours=annee_id, nbgroupespris=2),
            ]
        )
        db.session.commit()

        # --- Act ---
        result = get_org_scolaire_export_data_service(annee_id)

        # --- Assert ---
        # 1. Structure globale
        assert "MATH" in result
        assert "FRAN" in result
        assert len(result) == 2
        assert result["MATH"]["nom"] == "Mathématiques"
        assert result["FRAN"]["nom"] == "Français"

        # 2. Vérification des données MATH et du tri
        math_data = result["MATH"]["donnees"]
        assert len(math_data) == 3  # Archimede, Babbage, Tâche 2 (Tâche 10 n'a pas de cours)
        # Tri : Archimede (A) avant Babbage (B), puis Tâche 2
        assert math_data[0]["nomcomplet"] == "Syra Archimede"
        assert math_data[1]["nomcomplet"] == "Charles Babbage"
        assert math_data[2]["nomcomplet"] == "Tâche restante-2"

        # 3. Vérification du pivot et des valeurs pour MATH
        prof_a_row = math_data[0]
        assert prof_a_row["PÉRIODES RÉGULIER"] == pytest.approx(2.0)
        assert prof_a_row["PÉRIODES SPORT-ÉTUDES"] == pytest.approx(0.0)

        tache_2_row = math_data[2]
        assert tache_2_row["PÉRIODES RÉGULIER"] == pytest.approx(0.0)
        assert tache_2_row["PÉRIODES SPORT-ÉTUDES"] == pytest.approx(1.5)

        # 4. Vérification des données FRAN et des non-attribués
        fran_data = result["FRAN"]["donnees"]
        assert len(fran_data) == 2  # Camus et la ligne "Non attribué"
        # Tri: Enseignant réel avant "Non attribué"
        assert fran_data[0]["nomcomplet"] == "Albert Camus"
        assert fran_data[1]["nomcomplet"] == "Non attribué"

        # 5. Vérification du pivot et des valeurs pour FRAN
        prof_c_row = fran_data[0]
        assert prof_c_row["PÉRIODES RÉGULIER"] == pytest.approx(3.0 * 2)  # 2 groupes
        assert prof_c_row["PÉRIODES SPORT-ÉTUDES"] == pytest.approx(0.0)

        unassigned_row = fran_data[1]
        assert unassigned_row["estfictif"] is True
        # Calcul des périodes non-attribuées :
        # 1 groupe de F1P (1 * 3.0) + 2 groupes de F2U (2 * 2.5) = 3.0 + 5.0 = 8.0
        assert unassigned_row["PÉRIODES RÉGULIER"] == pytest.approx(8.0)
