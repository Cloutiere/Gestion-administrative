# mon_application/exports.py
"""
Ce module contient les fonctions de génération de fichiers Excel pour l'exportation.

Il est conçu pour être indépendant de Flask et se concentre uniquement sur la
création de documents Excel formatés à partir de données brutes fournies
en argument.
"""

import io
from typing import Any, cast

import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.worksheet.worksheet import Worksheet


def generer_export_taches(attributions: list[dict[str, Any]]) -> io.BytesIO:
    """
    Génère un fichier Excel des tâches attribuées à partir d'une liste de données.

    Le fichier est formaté avec des en-têtes stylisés et des couleurs de ligne
    alternées pour une meilleure lisibilité.

    Args:
        attributions: Une liste de dictionnaires, où chaque dictionnaire
                      représente une attribution agrégée avec les détails
                      de l'enseignant, du cours et du champ.

    Returns:
        Un objet io.BytesIO contenant le fichier Excel (.xlsx) en mémoire.
    """
    workbook = openpyxl.Workbook()
    sheet = cast(Worksheet, workbook.active)
    sheet.title = "Tâches Attribuées"

    # --- Définition des styles ---
    header_font = Font(bold=True, color="FFFFFF", name="Calibri", size=11)
    header_fill = PatternFill(
        start_color="4F81BD", end_color="4F81BD", fill_type="solid"
    )
    header_alignment = Alignment(horizontal="center", vertical="center")

    cell_font = Font(name="Calibri", size=11)
    center_align = Alignment(horizontal="center", vertical="center", wrap_text=True)
    left_align = Alignment(horizontal="left", vertical="center", wrap_text=True)
    number_format_periods = "0.00"

    # --- Définition des styles d'alternance de couleur ---
    fill_color_a = PatternFill(
        start_color="DDEBF7", end_color="DDEBF7", fill_type="solid"
    )
    fill_color_b = PatternFill(fill_type=None)

    # --- Écriture des en-têtes avec style ---
    headers = [
        "Champ",
        "Enseignant",
        "Code cours",
        "Description",
        "Cours autre",
        "Nb. grp.",
        "Pér./ groupe",
        "Pér. Total",
        "Information",
        "Plan B",
    ]
    sheet.append(headers)

    for cell in sheet[1]:
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_alignment

    # --- Écriture des données avec style et couleur alternée ---
    previous_teacher_name = None
    use_fill_color_a = True

    for attr in attributions:
        nom_enseignant = f"{attr['nom']}, {attr['prenom']}"

        if nom_enseignant != previous_teacher_name:
            use_fill_color_a = not use_fill_color_a

        chosen_fill = fill_color_a if use_fill_color_a else fill_color_b

        est_autre = "Oui" if attr["estcoursautre"] else "Non"
        nb_groupes = attr["total_groupes_pris"]
        per_groupe = attr["nbperiodes"]
        per_total = int(nb_groupes) * float(per_groupe)

        row_data = [
            attr["champnom"],
            nom_enseignant,
            attr["codecours"],
            attr["coursdescriptif"],
            est_autre,
            nb_groupes,
            per_groupe,
            per_total,
            "",
            "",
        ]
        sheet.append(row_data)

        current_row = sheet.max_row
        for col_idx, _cell_value in enumerate(row_data, 1):
            cell = sheet.cell(row=current_row, column=col_idx)
            cell.font = cell_font
            if col_idx in {5, 6, 7, 8}:
                cell.alignment = center_align
            else:
                cell.alignment = left_align
            if col_idx in {7, 8}:
                cell.number_format = number_format_periods
            cell.fill = chosen_fill

        previous_teacher_name = nom_enseignant

    # --- Ajustement final de la feuille ---
    column_widths = {
        "A": 25,
        "B": 25,
        "C": 15,
        "D": 40,
        "E": 12,
        "F": 10,
        "G": 12,
        "H": 12,
        "I": 15,
        "J": 15,
    }
    for col_letter, width in column_widths.items():
        sheet.column_dimensions[col_letter].width = width

    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = sheet.dimensions

    # --- Sauvegarde du classeur dans un flux mémoire ---
    mem_file = io.BytesIO()
    workbook.save(mem_file)
    mem_file.seek(0)

    return mem_file


def _apply_border_to_range(
    sheet: Worksheet, start_row: int, end_row: int, start_col: int, end_col: int
) -> None:
    """Applique une bordure fine autour d'une plage de cellules."""
    thin_border_side = Side(style="thin")
    box_border = Border(
        left=thin_border_side,
        right=thin_border_side,
        top=thin_border_side,
        bottom=thin_border_side,
    )

    for row in sheet.iter_rows(
        min_row=start_row, max_row=end_row, min_col=start_col, max_col=end_col
    ):
        for cell in row:
            cell.border = box_border


def generer_export_periodes_restantes(
    periodes_par_champ: dict[str, dict[str, Any]]
) -> io.BytesIO:
    """
    Génère un fichier Excel des périodes restantes avec totaux et mise en forme.

    Crée une feuille par champ. Le tableau commence en B2. Les groupes de
    tâches sont encadrés, avec des sous-totaux et un grand total.

    Args:
        periodes_par_champ: Dictionnaire des périodes restantes par champ.

    Returns:
        Un objet io.BytesIO contenant le fichier Excel (.xlsx) en mémoire.
    """
    workbook = openpyxl.Workbook()
    workbook.remove(cast(Worksheet, workbook.active))

    # --- Définition des styles ---
    header_font = Font(bold=True, color="FFFFFF", name="Calibri", size=11)
    header_fill = PatternFill("solid", fgColor="4F81BD")
    header_align = Alignment(horizontal="center", vertical="center")
    cell_font = Font(name="Calibri", size=11)
    left_align = Alignment(horizontal="left", vertical="center", wrap_text=True)
    right_align = Alignment(horizontal="right", vertical="center")
    number_format_periods = "0.00"

    subtotal_font = Font(bold=True, name="Calibri", size=11)
    subtotal_fill = PatternFill("solid", fgColor="F2F2F2")

    grand_total_font = Font(bold=True, color="FFFFFF", name="Calibri", size=11)
    grand_total_fill = PatternFill("solid", fgColor="365F91")

    # --- Itération et création des feuilles ---
    for champ_no, champ_data in periodes_par_champ.items():
        champ_nom = champ_data["nom"]
        periodes = champ_data["periodes"]
        nom_complet_champ = f"{champ_no}-{champ_nom}"
        safe_sheet_title = "".join(
            c for c in nom_complet_champ if c.isalnum() or c in " -_"
        ).strip()[:31]
        sheet = workbook.create_sheet(title=safe_sheet_title)

        # --- Écriture des en-têtes (commençant en B2) ---
        current_row_num = 2  # Le tableau commence à la ligne 2
        headers = [
            "Champ", "Tâche restantes", "Code cours", "Description",
            "Cours autre", "Pér./ groupe",
        ]
        for col_idx, header_text in enumerate(headers, start=2):
            cell = sheet.cell(row=current_row_num, column=col_idx, value=header_text)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = header_align
        current_row_num += 1

        # --- Variables pour les totaux et le formatage ---
        grand_total_periodes = 0.0
        subtotal_periodes = 0.0
        previous_tache_raw = None
        previous_tache_display = None
        group_start_row = current_row_num

        for periode in periodes:
            current_tache_raw = periode["tache_restante"]
            prefix_to_remove = f"{champ_no}-"
            current_tache_display = current_tache_raw
            if current_tache_raw.startswith(prefix_to_remove):
                current_tache_display = current_tache_raw.removeprefix(prefix_to_remove)

            if previous_tache_raw is not None and current_tache_raw != previous_tache_raw:
                sheet.cell(row=current_row_num, column=2, value=f"Total pour {previous_tache_display}")
                sheet.cell(row=current_row_num, column=7, value=subtotal_periodes)
                sheet.merge_cells(start_row=current_row_num, start_column=2, end_row=current_row_num, end_column=6)

                for col_idx in range(2, 8):
                    cell = sheet.cell(row=current_row_num, column=col_idx)
                    cell.font = subtotal_font
                    cell.fill = subtotal_fill
                    if col_idx == 2: cell.alignment = right_align
                    if col_idx == 7: cell.number_format = number_format_periods

                _apply_border_to_range(sheet, group_start_row, current_row_num, 2, 7)
                current_row_num += 2  # +1 pour le sous-total, +1 pour la ligne vide
                group_start_row = current_row_num
                subtotal_periodes = 0.0

            est_autre = "Oui" if periode["estcoursautre"] else "Non"
            current_periods = float(periode["nbperiodes"])
            row_data = [
                nom_complet_champ, current_tache_display, periode["codecours"],
                periode["coursdescriptif"], est_autre, current_periods,
            ]
            for col_idx, cell_value in enumerate(row_data, start=2):
                cell = sheet.cell(row=current_row_num, column=col_idx, value=cell_value)
                cell.font = cell_font
                cell.alignment = left_align
                if col_idx == 7:
                    cell.number_format = number_format_periods
            current_row_num += 1

            subtotal_periodes += current_periods
            grand_total_periodes += current_periods
            previous_tache_raw = current_tache_raw
            previous_tache_display = current_tache_display

        if previous_tache_raw is not None:
            sheet.cell(row=current_row_num, column=2, value=f"Total pour {previous_tache_display}")
            sheet.cell(row=current_row_num, column=7, value=subtotal_periodes)
            sheet.merge_cells(start_row=current_row_num, start_column=2, end_row=current_row_num, end_column=6)
            for col_idx in range(2, 8):
                cell = sheet.cell(row=current_row_num, column=col_idx)
                cell.font = subtotal_font
                cell.fill = subtotal_fill
                if col_idx == 2: cell.alignment = right_align
                if col_idx == 7: cell.number_format = number_format_periods

            _apply_border_to_range(sheet, group_start_row, current_row_num, 2, 7)
            current_row_num += 2

            sheet.cell(row=current_row_num, column=2, value="TOTAL DES PÉRIODES RESTANTES DU CHAMP")
            sheet.cell(row=current_row_num, column=7, value=grand_total_periodes)
            sheet.merge_cells(start_row=current_row_num, start_column=2, end_row=current_row_num, end_column=6)
            for col_idx in range(2, 8):
                cell = sheet.cell(row=current_row_num, column=col_idx)
                cell.font = grand_total_font
                cell.fill = grand_total_fill
                if col_idx == 2: cell.alignment = right_align
                if col_idx == 7: cell.number_format = number_format_periods

        column_widths = {'A': 3, 'B': 35, 'C': 25, 'D': 15, 'E': 40, 'F': 12, 'G': 12}
        for col_letter, width in column_widths.items():
            sheet.column_dimensions[col_letter].width = width
        sheet.freeze_panes = "B3"

    mem_file = io.BytesIO()
    workbook.save(mem_file)
    mem_file.seek(0)
    return mem_file