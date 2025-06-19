# mon_application/models.py
"""
Ce module définit les modèles de données de l'application en utilisant SQLAlchemy ORM.

Chaque classe correspond à une table dans la base de données et définit sa structure
ainsi que les relations avec les autres tables. Ces modèles sont la source de vérité
pour la structure de la base de données et sont utilisés par Flask-Migrate pour générer
les scripts de migration.
"""

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db


class UserChampAccess(db.Model):
    """Table d'association pour les droits d'accès des utilisateurs aux champs."""

    __tablename__ = "user_champ_access"
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    champ_no = db.Column(db.Text, db.ForeignKey("champs.champno", ondelete="CASCADE"), primary_key=True)


class User(db.Model, UserMixin):
    """Modèle pour les utilisateurs de l'application."""

    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.Text, unique=True, nullable=False)
    password_hash = db.Column(db.Text, nullable=False)
    is_admin = db.Column(db.Boolean, nullable=False, default=False)
    is_dashboard_only = db.Column(db.Boolean, nullable=False, default=False)

    # Relation vers les champs autorisés
    champs_autorises = db.relationship("Champ", secondary="user_champ_access", back_populates="utilisateurs_autorises")

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    @property
    def allowed_champs(self) -> list[str]:
        """Retourne la liste des numéros de champ autorisés pour l'utilisateur."""
        return [champ.champno for champ in self.champs_autorises]

    def can_access_champ(self, champ_no: str) -> bool:
        """Vérifie si l'utilisateur a l'autorisation d'accéder à un champ."""
        if self.is_admin or self.is_dashboard_only:
            return True
        return champ_no in self.allowed_champs


class Champ(db.Model):
    """Modèle pour les champs (disciplines)."""

    __tablename__ = "champs"
    champno = db.Column(db.Text, primary_key=True)
    champnom = db.Column(db.Text, nullable=False)

    # Relations
    utilisateurs_autorises = db.relationship("User", secondary="user_champ_access", back_populates="champs_autorises")
    cours = db.relationship("Cours", back_populates="champ")
    enseignants = db.relationship("Enseignant", back_populates="champ")
    statuts_annee = db.relationship("ChampAnneeStatut", back_populates="champ", cascade="all, delete-orphan")


class TypeFinancement(db.Model):
    """Modèle pour les types de financement."""

    __tablename__ = "typesfinancement"
    code = db.Column(db.Text, primary_key=True)
    libelle = db.Column(db.Text, nullable=False)

    # Relation
    cours = db.relationship("Cours", back_populates="financement")


class AnneeScolaire(db.Model):
    """Modèle pour les années scolaires."""

    __tablename__ = "anneesscolaires"
    annee_id = db.Column(db.Integer, primary_key=True)
    libelle_annee = db.Column(db.Text, unique=True, nullable=False)
    est_courante = db.Column(db.Boolean, nullable=False, default=False)

    # Relations
    cours = db.relationship("Cours", back_populates="annee_scolaire", cascade="all, delete-orphan")
    enseignants = db.relationship("Enseignant", back_populates="annee_scolaire", cascade="all, delete-orphan")
    statuts_champs = db.relationship("ChampAnneeStatut", back_populates="annee_scolaire", cascade="all, delete-orphan")
    preparations_horaire = db.relationship("PreparationHoraire", back_populates="annee_scolaire", cascade="all, delete-orphan")


class Enseignant(db.Model):
    """Modèle pour les enseignants (réels ou fictifs)."""

    __tablename__ = "enseignants"
    enseignantid = db.Column(db.Integer, primary_key=True)
    annee_id = db.Column(db.Integer, db.ForeignKey("anneesscolaires.annee_id"), nullable=False)
    nomcomplet = db.Column(db.Text, nullable=False)
    nom = db.Column(db.Text)
    prenom = db.Column(db.Text)
    champno = db.Column(db.Text, db.ForeignKey("champs.champno"), nullable=False)
    esttempsplein = db.Column(db.Boolean, nullable=False, default=True)
    estfictif = db.Column(db.Boolean, nullable=False, default=False)

    # Relations
    annee_scolaire = db.relationship("AnneeScolaire", back_populates="enseignants")
    champ = db.relationship("Champ", back_populates="enseignants")
    attributions = db.relationship("AttributionCours", back_populates="enseignant", cascade="all, delete-orphan")
    preparations_horaire = db.relationship("PreparationHoraire", back_populates="enseignant", cascade="all, delete-orphan")

    __table_args__ = (db.UniqueConstraint("nom", "prenom", "annee_id", name="enseignants_nom_prenom_annee_id_key"),)


class Cours(db.Model):
    """Modèle pour les cours."""

    __tablename__ = "cours"
    codecours = db.Column(db.Text, primary_key=True)
    annee_id = db.Column(db.Integer, db.ForeignKey("anneesscolaires.annee_id"), primary_key=True)
    champno = db.Column(db.Text, db.ForeignKey("champs.champno"), nullable=False)
    coursdescriptif = db.Column(db.Text, nullable=False)
    nbperiodes = db.Column(db.Numeric(5, 2), nullable=False)
    nbgroupeinitial = db.Column(db.Integer, nullable=False)
    estcoursautre = db.Column(db.Boolean, nullable=False, default=False)
    # MODIFIÉ : on supprime ondelete="SET NULL" pour forcer une erreur si le financement est utilisé
    financement_code = db.Column(db.Text, db.ForeignKey("typesfinancement.code"))

    # Relations
    annee_scolaire = db.relationship("AnneeScolaire", back_populates="cours")
    champ = db.relationship("Champ", back_populates="cours")
    financement = db.relationship("TypeFinancement", back_populates="cours")
    attributions = db.relationship("AttributionCours", back_populates="cours", cascade="all, delete-orphan")
    preparations_horaire = db.relationship("PreparationHoraire", back_populates="cours", cascade="all, delete-orphan")


class AttributionCours(db.Model):
    """Modèle pour les attributions de cours aux enseignants."""

    __tablename__ = "attributionscours"
    attributionid = db.Column(db.Integer, primary_key=True)
    enseignantid = db.Column(db.Integer, db.ForeignKey("enseignants.enseignantid", ondelete="CASCADE"), nullable=False)
    codecours = db.Column(db.Text, nullable=False)
    annee_id_cours = db.Column(db.Integer, nullable=False)
    nbgroupespris = db.Column(db.Integer, nullable=False, default=1)

    # Relations
    enseignant = db.relationship("Enseignant", back_populates="attributions")
    cours = db.relationship("Cours", back_populates="attributions")

    __table_args__ = (db.ForeignKeyConstraint(["codecours", "annee_id_cours"], ["cours.codecours", "cours.annee_id"], ondelete="CASCADE"),)


class ChampAnneeStatut(db.Model):
    """Modèle pour les statuts d'un champ pour une année donnée."""

    __tablename__ = "champ_annee_statuts"
    champ_no = db.Column(db.Text, db.ForeignKey("champs.champno", ondelete="CASCADE"), primary_key=True)
    annee_id = db.Column(db.Integer, db.ForeignKey("anneesscolaires.annee_id", ondelete="CASCADE"), primary_key=True)
    est_verrouille = db.Column(db.Boolean, nullable=False, default=False)
    est_confirme = db.Column(db.Boolean, nullable=False, default=False)

    # Relations
    champ = db.relationship("Champ", back_populates="statuts_annee")
    annee_scolaire = db.relationship("AnneeScolaire", back_populates="statuts_champs")


class PreparationHoraire(db.Model):
    """Modèle pour sauvegarder les données de la préparation de l'horaire."""

    __tablename__ = "preparation_horaire"
    id = db.Column(db.Integer, primary_key=True)
    annee_id = db.Column(db.Integer, db.ForeignKey("anneesscolaires.annee_id", ondelete="CASCADE"), nullable=False)
    secondaire_level = db.Column(db.Integer, nullable=False)
    codecours = db.Column(db.Text, nullable=False)
    annee_id_cours = db.Column(db.Integer, nullable=False)
    enseignant_id = db.Column(db.Integer, db.ForeignKey("enseignants.enseignantid", ondelete="CASCADE"), nullable=False)
    colonne_assignee = db.Column(db.Text, nullable=False)

    # Relations
    annee_scolaire = db.relationship("AnneeScolaire", back_populates="preparations_horaire")
    enseignant = db.relationship("Enseignant", back_populates="preparations_horaire")
    cours = db.relationship("Cours", back_populates="preparations_horaire")

    __table_args__ = (
        db.ForeignKeyConstraint(["codecours", "annee_id_cours"], ["cours.codecours", "cours.annee_id"], ondelete="CASCADE"),
        db.UniqueConstraint("annee_id", "secondaire_level", "enseignant_id", "colonne_assignee", name="preparation_horaire_unique_assignment"),
    )
