# mon_application/services.py
"""
Ce module contient la logique métier de l'application (couche de services).

Il a pour but de découpler la logique complexe des routes Flask (contrôleurs).
Les fonctions ici gèrent des tâches comme le traitement de fichiers, les
opérations de base de données transactionnelles complexes, l'application des
règles de gestion et l'orchestration des appels à la couche d'accès aux
données (DAO).
"""

from collections import defaultdict
from typing import Any, cast

import openpyxl
import psycopg2
from openpyxl.utils.exceptions import InvalidFileException
from openpyxl.worksheet.worksheet import Worksheet
from psycopg2.extensions import connection as PgConnection

# NOUVEAU : Imports pour SQLAlchemy ORM
from .extensions import db
from .models import User

# ANCIEN : On le garde pour les fonctions non encore refactorisées
from . import database as old_db


# --- Exceptions Personnalisées pour la Couche de Service ---
class ServiceException(Exception):
    """Exception de base pour les erreurs de la couche de service."""
    def __init__(self, message="Une erreur est survenue."):
        self.message = message
        super().__init__(self.message)

class EntityNotFoundError(ServiceException):
    """Levée lorsqu'une entité n'est pas trouvée."""
    def __init__(self, message="L'entité n'a pas été trouvée."):
        super().__init__(message)

class DuplicateEntityError(ServiceException):
    """Levée lors d'une tentative de création d'une entité qui existe déjà."""
    def __init__(self, message="Cette entité existe déjà."):
        super().__init__(message)

class BusinessRuleValidationError(ServiceException):
    """Levée lorsqu'une règle métier est violée."""
    def __init__(self, message="Opération non autorisée par les règles de gestion."):
        super().__init__(message)

class ForeignKeyError(ServiceException):
    """Levée lorsqu'une suppression est bloquée par une contrainte de clé étrangère."""
    def __init__(self, message="Impossible de supprimer, cette entité est en cours d'utilisation."):
        super().__init__(message)

# ... le reste des classes d'exception reste inchangé ...


# --- Services - Utilisateurs et Rôles ---

# MODIFIÉ : Le service ne gère plus la transaction (commit/rollback).
# Il prépare l'objet et l'ajoute à la session. C'est le rôle de l'appelant
# (la route) de commiter la transaction.
def register_first_admin_service(username: str, password: str, confirm_password: str) -> User:
    """
    Gère la logique d'inscription du premier admin.
    Lève des exceptions et retourne l'objet User prêt à être commit.
    """
    if db.session.query(User.id).count() > 0:
        raise BusinessRuleValidationError("L'inscription n'est autorisée que pour le premier utilisateur.")

    if not all([username, password, confirm_password]):
        raise BusinessRuleValidationError("Tous les champs sont requis.")
    if password != confirm_password:
        raise BusinessRuleValidationError("Les mots de passe ne correspondent pas.")
    if len(password) < 6:
        raise BusinessRuleValidationError("Le mot de passe doit contenir au moins 6 caractères.")

    if db.session.query(User).filter_by(username=username).first():
            raise DuplicateEntityError("Ce nom d'utilisateur est déjà pris.")

    new_admin = User(username=username, is_admin=True)
    new_admin.set_password(password)

    db.session.add(new_admin)
    # Le db.session.commit() est retiré.

    return new_admin


# --- Le reste du fichier services.py reste inchangé pour l'instant ---
# ... (toutes les autres fonctions de service) ...
def process_courses_excel(file_stream: Any) -> list[dict[str, Any]]:
    # ... (code inchangé, utilise encore l'ancien système pour l'instant)
    nouveaux_cours: list[dict[str, Any]] = []
    try:
        workbook = openpyxl.load_workbook(file_stream)
        sheet = cast(Worksheet, workbook.active)
        if sheet.max_row <= 1:
            raise ValueError("Fichier Excel vide ou ne contenant que l'en-tête.")

        for row_idx, row in enumerate(sheet.iter_rows(min_row=2), start=2):
            values = [cell.value for cell in row]
            if not any(v is not None and str(v).strip() != "" for v in values[:7]):
                continue

            (
                champ_no_raw, code_cours_raw, desc_raw, nb_grp_raw, nb_per_raw,
            ) = (values[0], values[1], values[3], values[4], values[5])
            est_autre_raw = values[6] if len(values) > 6 else None
            financement_code_raw = values[7] if len(values) > 7 else None

            if not all([champ_no_raw, code_cours_raw, desc_raw, nb_grp_raw, nb_per_raw]):
                raise ValueError(f"Ligne {row_idx}: Données essentielles manquantes.")

            try:
                est_autre = str(est_autre_raw).strip().upper() in ("VRAI", "TRUE", "OUI", "YES", "1")
                financement_code = str(financement_code_raw).strip() if financement_code_raw else None

                nouveaux_cours.append(
                    {
                        "codecours": str(code_cours_raw).strip(),
                        "champno": str(champ_no_raw).strip(),
                        "coursdescriptif": str(desc_raw).strip(),
                        "nbperiodes": float(str(nb_per_raw).replace(",", ".")),
                        "nbgroupeinitial": int(float(str(nb_grp_raw).replace(",", "."))),
                        "estcoursautre": est_autre,
                        "financement_code": financement_code,
                    }
                )
            except (ValueError, TypeError) as e:
                raise ValueError(f"Ligne {row_idx}: Erreur de type de données. Détails: {e}") from e

    except InvalidFileException as e:
        raise InvalidFileException("Fichier Excel corrompu ou invalide.") from e

    if not nouveaux_cours:
        raise ValueError("Aucun cours valide n'a été trouvé dans le fichier.")

    return nouveaux_cours

class ImportationStats:
    """Classe de données pour stocker les statistiques d'une importation."""
    # ... (code inchangé)
    def __init__(self) -> None:
        self.imported_count = 0
        self.deleted_attributions_count = 0
        self.deleted_main_entities_count = 0

def save_imported_courses(courses_data: list[dict[str, Any]], annee_id: int) -> ImportationStats:
    # ... (code inchangé, utilise encore l'ancien système pour l'instant)
    stats = ImportationStats()
    conn = cast(PgConnection | None, old_db.get_db())
    if not conn:
        raise ServiceException("Impossible d'obtenir une connexion à la base de données.")

    try:
        with conn.cursor():
            stats.deleted_attributions_count = old_db.delete_all_attributions_for_year(annee_id)
            stats.deleted_main_entities_count = old_db.delete_all_cours_for_year(annee_id)

            for cours in courses_data:
                old_db.create_cours(cours, annee_id)
            stats.imported_count = len(courses_data)

            conn.commit()
    except psycopg2.Error as e:
        conn.rollback()
        raise ServiceException(f"Erreur de base de données lors de l'importation des cours: {e}")

def process_teachers_excel(file_stream: Any) -> list[dict[str, Any]]:
    """Traite un fichier Excel d'enseignants."""
    nouveaux_enseignants: list[dict[str, Any]] = []
    try:
        workbook = openpyxl.load_workbook(file_stream)
        sheet = cast(Worksheet, workbook.active)
        if sheet.max_row <= 1:
            raise ValueError("Fichier Excel vide ou ne contenant que l'en-tête.")

        for row_idx, row in enumerate(sheet.iter_rows(min_row=2), start=2):
            values = [cell.value for cell in row]
            if not any(v is not None and str(v).strip() != "" for v in values[:4]):
                continue

            champ_no_raw, nom_raw, prenom_raw, temps_plein_raw = (
                values[0], values[1], values[2], values[3],
            )

            if not all([champ_no_raw, nom_raw, prenom_raw, temps_plein_raw is not None]):
                raise ValueError(f"Ligne {row_idx}: Données essentielles manquantes.")

            try:
                nom_clean, prenom_clean = str(nom_raw).strip(), str(prenom_raw).strip()
                if not nom_clean or not prenom_clean:
                    continue
                nouveaux_enseignants.append(
                    {
                        "nom": nom_clean,
                        "prenom": prenom_clean,
                        "champno": str(champ_no_raw).strip(),
                        "esttempsplein": str(temps_plein_raw).strip().upper()
                        in ("VRAI", "TRUE", "OUI", "YES", "1"),
                    }
                )
            except (ValueError, TypeError) as e:
                raise ValueError(f"Ligne {row_idx}: Erreur de type de données. Détails: {e}") from e

    except InvalidFileException as e:
        raise InvalidFileException("Fichier Excel des enseignants corrompu ou invalide.") from e

    if not nouveaux_enseignants:
        raise ValueError("Aucun enseignant valide n'a été trouvé dans le fichier.")

    return nouveaux_enseignants


def save_imported_teachers(teachers_data: list[dict[str, Any]], annee_id: int) -> ImportationStats:
    """Sauvegarde les enseignants importés dans une transaction atomique."""
    stats = ImportationStats()
    conn = cast(PgConnection | None, old_db.get_db())
    if not conn:
        raise ServiceException("Impossible d'obtenir une connexion à la base de données.")

    try:
        with conn.cursor():
            stats.deleted_attributions_count = old_db.delete_all_attributions_for_year(annee_id)
            stats.deleted_main_entities_count = old_db.delete_all_enseignants_for_year(annee_id)

            for ens in teachers_data:
                ens["nomcomplet"] = f"{ens['prenom']} {ens['nom']}"
                old_db.create_enseignant(ens, annee_id)
            stats.imported_count = len(teachers_data)

            conn.commit()
    except psycopg2.Error as e:
        conn.rollback()
        raise ServiceException(f"Erreur de base de données lors de l'importation des enseignants: {e}")

    return stats


# --- Nouveaux Services - Années Scolaires ---
def get_all_annees_service() -> list[dict[str, Any]]:
    """Récupère toutes les années scolaires."""
    return old_db.get_all_annees()


def create_annee_scolaire_service(libelle: str) -> dict[str, Any]:
    """Crée une nouvelle année scolaire et la définit comme courante si aucune autre ne l'est."""
    conn = cast(PgConnection | None, old_db.get_db())
    if not conn:
        raise ServiceException("Pas de connexion à la base de données.")
    try:
        with conn.cursor():
            annee_courante_existante = old_db.get_annee_courante() is not None
            new_annee = old_db.create_annee_scolaire(libelle)
            if not new_annee:
                raise DuplicateEntityError(f"L'année '{libelle}' existe déjà.")

            if not annee_courante_existante:
                old_db.set_annee_courante(new_annee["annee_id"])
                new_annee["est_courante"] = True
            conn.commit()
            return new_annee
    except psycopg2.Error as e:
        if conn:
            conn.rollback()
        raise ServiceException(f"Erreur de base de données lors de la création de l'année: {e}")


def set_annee_courante_service(annee_id: int) -> None:
    """Définit une année scolaire comme étant la courante."""
    if not old_db.get_annee_by_id(annee_id):
        raise EntityNotFoundError("Année non trouvée.")
    if not old_db.set_annee_courante(annee_id):
        raise ServiceException("La mise à jour de l'année courante a échoué.")


# --- Nouveaux Services - Champs & Statuts ---
def get_all_champs_service() -> list[dict[str, Any]]:
    """Récupère tous les champs."""
    return old_db.get_all_champs()


def toggle_champ_lock_service(champ_no: str, annee_id: int) -> bool:
    """Bascule le statut de verrouillage d'un champ pour l'année active."""
    nouveau_statut = old_db.toggle_champ_annee_lock_status(champ_no, annee_id)
    if nouveau_statut is None:
        raise ServiceException(f"Impossible de modifier le verrou du champ {champ_no}.")
    return nouveau_statut


def toggle_champ_confirm_service(champ_no: str, annee_id: int) -> bool:
    """Bascule le statut de confirmation d'un champ pour l'année active."""
    nouveau_statut = old_db.toggle_champ_annee_confirm_status(champ_no, annee_id)
    if nouveau_statut is None:
        raise ServiceException(f"Impossible de modifier la confirmation du champ {champ_no}.")
    return nouveau_statut


# --- Services CRUD - Cours ---
def get_course_details_service(code_cours: str, annee_id: int) -> dict[str, Any]:
    """Récupère les détails d'un cours spécifique."""
    cours = old_db.get_cours_details(code_cours, annee_id)
    if not cours:
        raise EntityNotFoundError("Cours non trouvé pour cette année.")
    return cours


def create_course_service(data: dict[str, Any], annee_id: int) -> dict[str, Any]:
    """Crée un cours après validation."""
    try:
        new_cours = old_db.create_cours(data, annee_id)
        if not new_cours:
            raise ServiceException("La création du cours a échoué pour une raison inconnue.")
        return new_cours
    except psycopg2.errors.UniqueViolation:
        raise DuplicateEntityError("Un cours avec ce code existe déjà pour cette année.")
    except psycopg2.Error as e:
        raise ServiceException(f"Erreur de base de données: {e}")


def update_course_service(code_cours: str, annee_id: int, data: dict[str, Any]) -> dict[str, Any]:
    """Met à jour un cours après validation."""
    try:
        updated_course = old_db.update_cours(code_cours, annee_id, data)
        if not updated_course:
            raise EntityNotFoundError("Cours non trouvé pour cette année.")
        return updated_course
    except psycopg2.Error as e:
        raise ServiceException(f"Erreur de base de données: {e}")


def delete_course_service(code_cours: str, annee_id: int) -> None:
    """Supprime un cours et gère les erreurs de dépendance."""
    try:
        if not old_db.delete_cours(code_cours, annee_id):
            raise EntityNotFoundError("Cours non trouvé pour cette année.")
    except psycopg2.errors.ForeignKeyViolation:
        raise ForeignKeyError("Impossible de supprimer : ce cours est attribué à un ou plusieurs enseignants.")
    except psycopg2.Error as e:
        raise ServiceException(f"Erreur de base de données: {e}")


def reassign_course_to_champ_service(code_cours: str, annee_id: int, nouveau_champ_no: str) -> dict[str, Any]:
    """Réassigne un cours à un nouveau champ."""
    try:
        result = old_db.reassign_cours_to_champ(code_cours, annee_id, nouveau_champ_no)
        if not result:
            raise ServiceException("Impossible de réassigner le cours (champ invalide ou cours non trouvé).")
        return result
    except psycopg2.Error as e:
        raise ServiceException(f"Erreur de base de données: {e}")


def reassign_course_to_financement_service(code_cours: str, annee_id: int, code_financement: str | None) -> None:
    """Réassigne un cours à un nouveau type de financement."""
    try:
        if not old_db.reassign_cours_to_financement(code_cours, annee_id, code_financement):
            raise ServiceException("Impossible de réassigner le financement (cours non trouvé).")
    except psycopg2.Error as e:
        raise ServiceException(f"Erreur de base de données: {e}")


# --- Services CRUD - Enseignants ---
def get_teacher_details_service(enseignant_id: int) -> dict[str, Any]:
    """Récupère les détails d'un enseignant non fictif."""
    enseignant = old_db.get_enseignant_details(enseignant_id)
    if not enseignant or enseignant["estfictif"]:
        raise EntityNotFoundError("Enseignant non trouvé ou non modifiable.")
    return enseignant


def create_teacher_service(data: dict[str, Any], annee_id: int) -> dict[str, Any]:
    """Crée un enseignant après validation."""
    try:
        data["nomcomplet"] = f"{data['prenom']} {data['nom']}"
        new_teacher = old_db.create_enseignant(data, annee_id)
        if not new_teacher:
            raise ServiceException("La création de l'enseignant a échoué.")
        return new_teacher
    except psycopg2.errors.UniqueViolation:
        raise DuplicateEntityError("Un enseignant avec ce nom/prénom existe déjà pour cette année.")
    except psycopg2.Error as e:
        raise ServiceException(f"Erreur de base de données: {e}")


def update_teacher_service(enseignant_id: int, data: dict[str, Any]) -> dict[str, Any]:
    """Met à jour un enseignant après validation."""
    try:
        data["nomcomplet"] = f"{data['prenom']} {data['nom']}"
        updated_teacher = old_db.update_enseignant(enseignant_id, data)
        if not updated_teacher:
            raise EntityNotFoundError("Enseignant non trouvé ou non modifiable (fictif).")
        return updated_teacher
    except psycopg2.errors.UniqueViolation:
        raise DuplicateEntityError("Un autre enseignant avec ce nom/prénom existe déjà.")
    except psycopg2.Error as e:
        raise ServiceException(f"Erreur de base de données: {e}")


def delete_teacher_service(enseignant_id: int) -> list[dict[str, Any]]:
    """Supprime un enseignant (réel ou fictif) et retourne les cours affectés."""
    if not old_db.get_enseignant_details(enseignant_id):
        raise EntityNotFoundError("Enseignant non trouvé.")

    cours_affectes = old_db.get_affected_cours_for_enseignant(enseignant_id)
    try:
        if not old_db.delete_enseignant(enseignant_id):
            raise ServiceException("La suppression de l'enseignant a échoué en base de données.")
        return cours_affectes
    except psycopg2.Error as e:
        raise ServiceException(f"Erreur de base de données lors de la suppression: {e}")


def create_fictitious_teacher_service(champ_no: str, annee_id: int) -> dict[str, Any]:
    """Crée une nouvelle tâche restante (enseignant fictif) pour un champ/année."""
    try:
        fictifs_existants = old_db.get_fictif_enseignants_by_champ(champ_no, annee_id)
        numeros = [
            int(f["nomcomplet"].split("-")[-1])
            for f in fictifs_existants
            if f["nomcomplet"].startswith(f"{champ_no}-Tâche restante-") and f["nomcomplet"].split("-")[-1].isdigit()
        ]
        next_num = max(numeros) + 1 if numeros else 1
        nom_tache = f"{champ_no}-Tâche restante-{next_num}"
        nouveau_fictif = old_db.create_fictif_enseignant(nom_tache, champ_no, annee_id)
        if not nouveau_fictif:
            raise ServiceException("La création de la tâche restante a échoué.")
        return nouveau_fictif
    except psycopg2.Error as e:
        raise ServiceException(f"Erreur de base de données: {e}")


# --- Services CRUD - Financements ---
def get_all_financements_service() -> list[dict[str, Any]]:
    """Récupère tous les types de financement."""
    return old_db.get_all_financements()


def create_financement_service(code: str, libelle: str) -> dict[str, Any]:
    """Crée un type de financement."""
    try:
        new_financement = old_db.create_financement(code, libelle)
        if not new_financement:
            raise ServiceException("La création du financement a échoué.")
        return new_financement
    except psycopg2.errors.UniqueViolation:
        raise DuplicateEntityError("Ce code de financement existe déjà.")
    except psycopg2.Error as e:
        raise ServiceException(f"Erreur de base de données: {e}")


def update_financement_service(code: str, libelle: str) -> dict[str, Any]:
    """Met à jour un type de financement."""
    try:
        updated = old_db.update_financement(code, libelle)
        if not updated:
            raise EntityNotFoundError("Financement non trouvé.")
        return updated
    except psycopg2.Error as e:
        raise ServiceException(f"Erreur de base de données: {e}")


def delete_financement_service(code: str) -> None:
    """Supprime un type de financement."""
    try:
        if not old_db.delete_financement(code):
            raise EntityNotFoundError("Type de financement non trouvé.")
    except psycopg2.errors.ForeignKeyViolation:
        raise ForeignKeyError("Impossible de supprimer : ce financement est utilisé par des cours.")
    except psycopg2.Error as e:
        raise ServiceException(f"Erreur de base de données: {e}")
def get_all_users_with_details_service() -> dict[str, Any]:
    """Récupère tous les utilisateurs avec le décompte des admins."""
    return {"users": old_db.get_all_users_with_access_info(), "admin_count": old_db.get_admin_count()}


def create_user_service(username: str, password: str, role: str, allowed_champs: list[str]) -> dict[str, Any]:
    """Crée un utilisateur complet avec son rôle et ses accès."""
    if len(password) < 6:
        raise BusinessRuleValidationError("Le mot de passe doit faire au moins 6 caractères.")

    # NOTE: Cette fonction doit être entièrement refactorisée pour l'ORM. Pour l'instant on la laisse pour ne pas casser l'API admin.
    password_hash = generate_password_hash(password)
    conn = cast(PgConnection | None, old_db.get_db())
    if not conn:
        raise ServiceException("Pas de connexion à la base de données.")

    user = None
    try:
        user = old_db.create_user(username, password_hash)
        if not user:
            raise DuplicateEntityError("Ce nom d'utilisateur est déjà pris.")

        is_admin = role == "admin"
        is_dashboard_only = role == "dashboard_only"
        champs_for_role = allowed_champs if role == "specific_champs" else []
        old_db.update_user_role_and_access(user["id"], is_admin, is_dashboard_only, champs_for_role)
        conn.commit()

        user_complet = old_db.get_user_by_id(user["id"])
        if not user_complet:
            raise ServiceException("Erreur lors de la récupération de l'utilisateur après création.")
        return user_complet
    except Exception as e:
        if conn: conn.rollback()
        if user: old_db.delete_user_data(user["id"]); conn.commit()
        if isinstance(e, (psycopg2.errors.UniqueViolation, DuplicateEntityError)):
            raise DuplicateEntityError("Ce nom d'utilisateur est déjà pris.")
        if isinstance(e, ServiceException): raise e
        raise ServiceException(f"Erreur base de données lors de la création de l'utilisateur: {e}")


def update_user_role_service(user_id: int, role: str, allowed_champs: list[str]) -> None:
    """Met à jour le rôle et les accès d'un utilisateur."""
    if not old_db.get_user_by_id(user_id):
        raise EntityNotFoundError("Utilisateur non trouvé.")

    is_admin = role == "admin"
    is_dashboard_only = role == "dashboard_only"
    champs_for_role = allowed_champs if role == "specific_champs" else []

    conn = cast(PgConnection | None, old_db.get_db())
    if not conn:
        raise ServiceException("Pas de connexion à la base de données.")
    try:
        with conn.cursor():
            old_db.update_user_role_and_access(user_id, is_admin, is_dashboard_only, champs_for_role)
        conn.commit()
    except psycopg2.Error as e:
        if conn:
            conn.rollback()
        raise ServiceException(f"La mise à jour du rôle a échoué: {e}")


def delete_user_service(user_id_to_delete: int, current_user_id: int) -> None:
    """Supprime un utilisateur en respectant les règles métier."""
    if user_id_to_delete == current_user_id:
        raise BusinessRuleValidationError("Vous ne pouvez pas vous supprimer vous-même.")
    target_user = old_db.get_user_by_id(user_id_to_delete)
    if not target_user:
        raise EntityNotFoundError("Utilisateur non trouvé.")
    if target_user["is_admin"] and old_db.get_admin_count() <= 1:
        raise BusinessRuleValidationError("Impossible de supprimer le dernier administrateur.")
    if not old_db.delete_user_data(user_id_to_delete):
        raise ServiceException("La suppression de l'utilisateur a échoué.")


# --- Services - Attributions ---
def add_attribution_service(enseignant_id: int, code_cours: str, annee_id: int) -> int:
    """Ajoute une attribution en validant les règles métier."""
    verrou_info = old_db.get_verrou_info_enseignant(enseignant_id)
    if not verrou_info:
        raise EntityNotFoundError("Enseignant non trouvé.")
    if verrou_info.get("est_verrouille") and not verrou_info.get("estfictif"):
        raise BusinessRuleValidationError("Les modifications sont désactivées car le champ est verrouillé.")
    if old_db.get_groupes_restants_pour_cours(code_cours, annee_id) < 1:
        raise BusinessRuleValidationError("Plus de groupes disponibles pour ce cours.")

    try:
        new_id = old_db.add_attribution(enseignant_id, code_cours, annee_id)
        if new_id is None:
            raise ServiceException("Erreur de base de données lors de l'attribution.")
        return new_id
    except psycopg2.Error as e:
        raise ServiceException(f"Erreur de base de données: {e}")


def delete_attribution_service(attribution_id: int) -> dict[str, Any]:
    """Supprime une attribution en validant les règles métier."""
    attr_info = old_db.get_attribution_info(attribution_id)
    if not attr_info:
        raise EntityNotFoundError("Attribution non trouvée.")
    if attr_info.get("est_verrouille") and not attr_info.get("estfictif"):
        raise BusinessRuleValidationError("Les modifications sont désactivées car le champ est verrouillé.")

    try:
        if not old_db.delete_attribution(attribution_id):
            raise ServiceException("Échec de la suppression de l'attribution.")
        return attr_info
    except psycopg2.Error as e:
        raise ServiceException(f"Erreur de base de données: {e}")


# --- Nouveaux Services - Page Data Aggregation ---
def get_data_for_admin_page_service(annee_id: int) -> dict[str, Any]:
    """Récupère toutes les données nécessaires pour la page d'administration des données."""
    return {
        "cours_par_champ": old_db.get_all_cours_grouped_by_champ(annee_id),
        "enseignants_par_champ": old_db.get_all_enseignants_grouped_by_champ(annee_id),
        "tous_les_champs": old_db.get_all_champs(),
        "tous_les_financements": old_db.get_all_financements(),
    }


def get_data_for_user_admin_page_service() -> dict[str, Any]:
    """Récupère toutes les données nécessaires pour la page d'administration des utilisateurs."""
    return {
        "users": old_db.get_all_users_with_access_info(),
        "all_champs": old_db.get_all_champs(),
    }


# --- Nouveaux Services - Dashboard & Exports ---
def get_dashboard_summary_service(annee_id: int) -> dict[str, Any]:
    """Récupère les données agrégées pour la page du sommaire."""
    return old_db.get_dashboard_summary_data(annee_id)


def get_detailed_tasks_data_service(annee_id: int) -> list[dict[str, Any]]:
    """Récupère et formate les données pour la page de détail des tâches."""
    tous_les_enseignants_details = old_db.get_all_enseignants_avec_details(annee_id)
    tous_les_champs = old_db.get_all_champs()
    statuts_champs = old_db.get_all_champ_statuses_for_year(annee_id)

    enseignants_par_champ_temp: dict[str, dict[str, Any]] = {
        str(champ["champno"]): {
            "champno": str(champ["champno"]),
            "champnom": champ["champnom"],
            "enseignants": [],
            "est_verrouille": statuts_champs.get(str(champ["champno"]), {}).get("est_verrouille", False),
            "est_confirme": statuts_champs.get(str(champ["champno"]), {}).get("est_confirme", False),
        }
        for champ in tous_les_champs
    }
    for ens in tous_les_enseignants_details:
        champ_no = ens["champno"]
        if champ_no in enseignants_par_champ_temp:
            enseignants_par_champ_temp[champ_no]["enseignants"].append(ens)
    return list(enseignants_par_champ_temp.values())


def get_attributions_for_export_service(annee_id: int) -> dict[str, dict[str, Any]]:
    """Récupère et groupe les attributions pour l'export Excel."""
    attributions_raw = old_db.get_all_attributions_for_export(annee_id)
    if not attributions_raw:
        return {}
    attributions_par_champ: dict[str, dict[str, Any]] = {}
    for attr in attributions_raw:
        champ_no = attr["champno"]
        if champ_no not in attributions_par_champ:
            attributions_par_champ[champ_no] = {"nom": attr["champnom"], "attributions": []}
        attributions_par_champ[champ_no]["attributions"].append(attr)
    return attributions_par_champ


def get_remaining_periods_for_export_service(annee_id: int) -> dict[str, dict[str, Any]]:
    """Récupère et groupe les périodes restantes pour l'export Excel."""
    periodes_restantes_raw = old_db.get_periodes_restantes_for_export(annee_id)
    if not periodes_restantes_raw:
        return {}
    periodes_par_champ: dict[str, dict[str, Any]] = {}
    for periode in periodes_restantes_raw:
        champ_no = periode["champno"]
        if champ_no not in periodes_par_champ:
            periodes_par_champ[champ_no] = {"nom": periode["champnom"], "periodes": []}
        periodes_par_champ[champ_no]["periodes"].append(periode)
    return periodes_par_champ


def get_org_scolaire_export_data_service(annee_id: int) -> dict[str, dict[str, Any]]:
    """Prépare les données pivotées pour l'export 'Organisation Scolaire'."""
    tous_les_financements = old_db.get_all_financements()
    libelle_to_header_map = {f["libelle"].upper(): f"PÉRIODES {f['libelle'].upper()}" for f in tous_les_financements}
    libelle_to_header_map["SOUTIEN EN SPORT-ÉTUDES"] = "PÉRIODES SOUTIEN SPORT-ÉTUDES"
    code_to_libelle_map = {f["code"]: f["libelle"].upper() for f in tous_les_financements}

    donnees_raw = old_db.get_data_for_org_scolaire_export(annee_id)
    if not donnees_raw:
        return {}

    pivot_data: dict[str, dict[str, Any]] = {}
    ALL_HEADERS = [
        "PÉRIODES RÉGULIER", "PÉRIODES ADAPTATION SCOLAIRE", "PÉRIODES SPORT-ÉTUDES",
        "PÉRIODES ENSEIGNANT RESSOURCE", "PÉRIODES AIDESEC", "PÉRIODES DIPLÔMA",
        "PÉRIODES MESURE SEUIL (UTILISÉE COORDINATION PP)", "PÉRIODES MESURE SEUIL (RESSOURCES AUTRES)",
        "PÉRIODES MESURE SEUIL (POUR FABLAB)", "PÉRIODES MESURE SEUIL (BONIFIER ALTERNE)",
        "PÉRIODES ALTERNE", "PÉRIODES FORMANUM", "PÉRIODES MENTORAT", "PÉRIODES COORDINATION SPORT-ÉTUDES",
        "PÉRIODES SOUTIEN SPORT-ÉTUDES",
    ]

    for item in donnees_raw:
        champ_no = item["champno"]
        enseignant_key = f"fictif-{item['nomcomplet']}" if item["estfictif"] else f"reel-{item['nom']}-{item['prenom']}"

        if enseignant_key not in pivot_data.setdefault(champ_no, {}):
            pivot_data[champ_no][enseignant_key] = {
                "nom": item["nom"], "prenom": item["prenom"], "nomcomplet": item["nomcomplet"],
                "estfictif": item["estfictif"], "champnom": item["champnom"],
                **{header: 0.0 for header in ALL_HEADERS},
            }

        total_p = float(item["total_periodes"] or 0.0)
        financement_code = item["financement_code"]
        target_col = "PÉRIODES RÉGULIER"

        if financement_code and financement_code in code_to_libelle_map:
            libelle_upper = code_to_libelle_map[financement_code]
            if libelle_upper in libelle_to_header_map:
                target_col = libelle_to_header_map[libelle_upper]

        if target_col in pivot_data[champ_no][enseignant_key]:
            pivot_data[champ_no][enseignant_key][target_col] += total_p

    donnees_par_champ: dict[str, dict[str, Any]] = {}
    for champ_no, enseignants in pivot_data.items():
        if enseignants:
            donnees_par_champ[champ_no] = {
                "nom": next(iter(enseignants.values()))["champnom"],
                "donnees": list(enseignants.values()),
            }
    return donnees_par_champ


# --- SERVICES POUR PRÉPARATION HORAIRE ---

def get_preparation_horaire_data_service(annee_id: int) -> dict[str, Any]:
    """
    Récupère et structure les données nécessaires pour la page de préparation de l'horaire.
    """
    try:
        # 1. Récupérer toutes les briques de données brutes
        all_champs = old_db.get_all_champs()
        all_cours_raw = old_db.get_all_cours_for_preparation(annee_id)
        all_assignments_raw = old_db.get_assignments_for_preparation(annee_id)
        saved_assignments_raw = old_db.get_saved_preparation_horaire(annee_id)

        # 2. Pré-traiter les données pour un accès facile
        cours_par_champ: defaultdict[str, list] = defaultdict(list)
        cours_details: dict[str, dict] = {}
        for cours in all_cours_raw:
            cours_par_champ[cours["champno"]].append(cours)
            cours_details[cours["codecours"]] = cours

        enseignants_par_cours: defaultdict[str, list] = defaultdict(list)
        for assignment in all_assignments_raw:
            enseignants_par_cours[assignment["codecours"]].append(assignment)

        # 3. Organiser les assignations sauvegardées
        saved_placements = defaultdict(lambda: defaultdict(list))
        for saved in saved_assignments_raw:
            key = (saved['secondaire_level'], saved['codecours'])
            saved_placements[key][saved['colonne_assignee']].append(saved['enseignant_id'])

        # 4. Construire la structure de la grille pour le template
        prepared_grid: dict[int, list] = {level: [] for level in range(1, 6)}
        cours_traites = set()

        for (level, codecours), columns in saved_placements.items():
            cours_info = cours_details.get(codecours)
            if not cours_info:
                continue

            all_teachers_for_course = enseignants_par_cours.get(codecours, [])
            placed_teacher_ids = {tid for teacher_ids in columns.values() for tid in teacher_ids}
            unassigned_teachers = [t for t in all_teachers_for_course if t['enseignantid'] not in placed_teacher_ids]

            # MODIFIÉ : Création et ajout du dictionnaire de recherche
            teachers_lookup = {t['enseignantid']: t for t in all_teachers_for_course}

            prepared_grid[level].append({
                "cours": cours_info,
                "all_teachers_for_course": all_teachers_for_course,
                "unassigned_teachers": unassigned_teachers,
                "assigned_teachers_by_col": columns,
                "teachers_lookup": teachers_lookup,  # NOUVEAU: Ajout du lookup
            })
            cours_traites.add(codecours)

        # 5. Retourner le dictionnaire final structuré
        return {
            "all_champs": all_champs,
            "cours_par_champ": dict(cours_par_champ),
            "enseignants_par_cours": dict(enseignants_par_cours),
            "prepared_grid": prepared_grid,
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise ServiceException(f"Erreur lors de la préparation des données pour l'horaire : {e}")


def save_preparation_horaire_service(annee_id: int, assignments_data: list[dict[str, Any]]) -> None:
    """
    Valide et sauvegarde les données de préparation de l'horaire.
    """
    # Validation basique de la structure des données reçues
    required_keys = ["secondaire_level", "codecours", "annee_id_cours", "enseignant_id", "colonne_assignee"]
    for item in assignments_data:
        if not all(key in item for key in required_keys):
            raise BusinessRuleValidationError("Données de sauvegarde invalides ou incomplètes.")

    try:
        if not old_db.save_preparation_horaire_data(annee_id, assignments_data):
            raise ServiceException("La sauvegarde en base de données a échoué.")
    except Exception as e:
        raise ServiceException(f"Erreur lors de la sauvegarde de la préparation de l'horaire : {e}")