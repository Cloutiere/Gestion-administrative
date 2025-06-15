# mon_application/services.py
"""
Ce module contient la logique métier de l'application (couche de services).

Il a pour but de découpler la logique complexe des routes Flask (contrôleurs).
Les fonctions ici gèrent des tâches comme le traitement de fichiers, les
opérations de base de données transactionnelles complexes, etc.
"""

from typing import Any, cast

import openpyxl
import psycopg2
from openpyxl.utils.exceptions import InvalidFileException
from openpyxl.worksheet.worksheet import Worksheet
from psycopg2.extensions import connection as PgConnection

from . import database as db


class ImportationStats:
    """Classe de données pour stocker les statistiques d'une importation."""

    def __init__(self) -> None:
        self.imported_count = 0
        self.deleted_attributions_count = 0
        self.deleted_main_entities_count = 0


def process_courses_excel(file_stream: Any) -> list[dict[str, Any]]:
    """
    Traite un fichier Excel de cours.

    Args:
        file_stream: Le flux du fichier Excel (.xlsx).

    Returns:
        Une liste de dictionnaires, où chaque dictionnaire représente un cours.

    Raises:
        ValueError: Si le fichier est invalide, vide, ou si une ligne contient des données invalides.
        InvalidFileException: Si le fichier est corrompu.
    """
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


def save_imported_courses(
    courses_data: list[dict[str, Any]], annee_id: int
) -> ImportationStats:
    """
    Sauvegarde les cours importés dans une transaction atomique.

    Args:
        courses_data: La liste des cours à insérer.
        annee_id: L'ID de l'année scolaire concernée.

    Returns:
        Un objet ImportationStats avec les comptes des opérations.
    """
    stats = ImportationStats()
    conn = cast(PgConnection | None, db.get_db())
    if not conn:
        raise psycopg2.Error("Impossible d'obtenir une connexion à la base de données.")

    try:
        with conn.cursor():
            stats.deleted_attributions_count = db.delete_all_attributions_for_year(annee_id)
            stats.deleted_main_entities_count = db.delete_all_cours_for_year(annee_id)

            for cours in courses_data:
                db.create_cours(cours, annee_id)
            stats.imported_count = len(courses_data)

            conn.commit()
    except psycopg2.Error:
        conn.rollback()
        raise

    return stats


def process_teachers_excel(file_stream: Any) -> list[dict[str, Any]]:
    """
    Traite un fichier Excel d'enseignants.

    Args:
        file_stream: Le flux du fichier Excel (.xlsx).

    Returns:
        Une liste de dictionnaires, où chaque dictionnaire représente un enseignant.
    """
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


def save_imported_teachers(
    teachers_data: list[dict[str, Any]], annee_id: int
) -> ImportationStats:
    """
    Sauvegarde les enseignants importés dans une transaction atomique.

    Args:
        teachers_data: La liste des enseignants à insérer.
        annee_id: L'ID de l'année scolaire concernée.

    Returns:
        Un objet ImportationStats avec les comptes des opérations.
    """
    stats = ImportationStats()
    conn = cast(PgConnection | None, db.get_db())
    if not conn:
        raise psycopg2.Error("Impossible d'obtenir une connexion à la base de données.")

    try:
        with conn.cursor():
            stats.deleted_attributions_count = db.delete_all_attributions_for_year(annee_id)
            stats.deleted_main_entities_count = db.delete_all_enseignants_for_year(annee_id)

            for ens in teachers_data:
                db.create_enseignant(ens, annee_id)
            stats.imported_count = len(teachers_data)

            conn.commit()
    except psycopg2.Error:
        conn.rollback()
        raise

    return stats