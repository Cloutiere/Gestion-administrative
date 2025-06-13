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

    for row_iter in sheet.iter_rows( # Renommé pour éviter conflit avec variable 'row'
        min_row=start_row, max_row=end_row, min_col=start_col, max_col=end_col
    ):
        for cell in row_iter:
            cell.border = box_border


def generer_export_taches(
    attributions_par_champ: dict[str, dict[str, Any]]
) -> io.BytesIO:
    """
    Génère un fichier Excel des tâches attribuées, avec une feuille par champ.

    Le fichier est formaté avec des en-têtes stylisés, des sous-totaux par
    enseignant, et un grand total par champ.

    Args:
        attributions_par_champ: Dictionnaire des attributions groupées par champ.
                                La clé est le champ_no et la valeur contient le
                                nom du champ et la liste des attributions.

    Returns:
        Un objet io.BytesIO contenant le fichier Excel (.xlsx) en mémoire.
    """
    workbook = openpyxl.Workbook()
    workbook.remove(cast(Worksheet, workbook.active))

    # --- Définition des styles communs ---
    header_font = Font(bold=True, color="FFFFFF", name="Calibri", size=11)
    header_fill = PatternFill("solid", fgColor="4F81BD")
    header_align = Alignment(horizontal="center", vertical="center")

    cell_font = Font(name="Calibri", size=11)
    center_align = Alignment(horizontal="center", vertical="center", wrap_text=True)
    left_align = Alignment(horizontal="left", vertical="center", wrap_text=True)
    right_align = Alignment(horizontal="right", vertical="center")
    number_format_periods = "General" # Format numérique pour les périodes

    subtotal_font = Font(bold=True, name="Calibri", size=11)
    subtotal_fill = PatternFill("solid", fgColor="F2F2F2")

    grand_total_font = Font(bold=True, color="FFFFFF", name="Calibri", size=11)
    grand_total_fill = PatternFill("solid", fgColor="365F91")

    # --- Itération sur chaque champ pour créer une feuille dédiée ---
    for champ_no, champ_data in attributions_par_champ.items():
        champ_nom = champ_data["nom"]
        attributions = champ_data["attributions"]
        nom_complet_champ = f"{champ_no}-{champ_nom}"
        safe_sheet_title = "".join(
            c for c in nom_complet_champ if c.isalnum() or c in " -_"
        ).strip()[:31]
        sheet = workbook.create_sheet(title=safe_sheet_title)

        # --- Écriture des en-têtes (commençant en B2) ---
        current_row_num = 2
        headers = [
            "Enseignant",
            "Code cours",
            "Description",
            "Cours autre",
            "Nb. grp.",
            "Pér./ groupe",
            "Pér. Total",
        ]
        # Laisser la colonne A vide pour l'esthétique si besoin, ici on commence en B
        for col_idx, header_text in enumerate(headers, start=2): # start=2 pour col B
            cell = sheet.cell(row=current_row_num, column=col_idx, value=header_text)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = header_align
        current_row_num += 1

        # --- Variables pour les totaux et le formatage ---
        grand_total_periodes_champ = 0.0
        subtotal_periodes_enseignant = 0.0
        previous_teacher_name = None
        previous_teacher_fullname = None
        group_start_row = current_row_num

        for attr in attributions:
            nom_enseignant_cle = f"{attr['nom']}, {attr['prenom']}"
            nom_enseignant_affichage = f"{attr['prenom']} {attr['nom']}"

            if (
                previous_teacher_name is not None
                and nom_enseignant_cle != previous_teacher_name
            ):
                sheet.cell(
                    row=current_row_num,
                    column=2, # Colonne B
                    value=f"Total pour {previous_teacher_fullname} :",
                )
                sheet.cell(
                    row=current_row_num, column=8, value=subtotal_periodes_enseignant # Colonne H
                )
                sheet.merge_cells(
                    start_row=current_row_num,
                    start_column=2, # Colonne B
                    end_row=current_row_num,
                    end_column=7, # Colonne G
                )

                for col_idx in range(2, 9): # Colonnes B à H
                    cell = sheet.cell(row=current_row_num, column=col_idx)
                    cell.font = subtotal_font
                    cell.fill = subtotal_fill
                    if col_idx == 2: # Colonne B
                        cell.alignment = right_align
                    elif col_idx == 8: # Colonne H
                        cell.alignment = center_align
                        cell.number_format = number_format_periods

                _apply_border_to_range(sheet, group_start_row, current_row_num, 2, 8) # B à H
                current_row_num += 2
                group_start_row = current_row_num
                subtotal_periodes_enseignant = 0.0

            est_autre = "Oui" if attr["estcoursautre"] else "Non"
            nb_groupes = attr["total_groupes_pris"]
            per_groupe = float(attr["nbperiodes"])
            per_total_ligne = int(nb_groupes) * per_groupe

            row_data = [
                f"{attr['nom']}, {attr['prenom']}", # Sera en colonne B
                attr["codecours"],
                attr["coursdescriptif"],
                est_autre,
                nb_groupes,
                per_groupe,
                per_total_ligne,
            ]
            for col_idx, cell_value in enumerate(row_data, start=2): # start=2 pour col B
                cell = sheet.cell(row=current_row_num, column=col_idx, value=cell_value)
                cell.font = cell_font
                if col_idx in {2, 3, 4}: # B, C, D
                    cell.alignment = left_align
                else: # E, F, G, H
                    cell.alignment = center_align
                if col_idx in {6, 7, 8}: # F, G, H
                    cell.number_format = number_format_periods
            current_row_num += 1

            subtotal_periodes_enseignant += per_total_ligne
            grand_total_periodes_champ += per_total_ligne
            previous_teacher_name = nom_enseignant_cle
            previous_teacher_fullname = nom_enseignant_affichage

        if previous_teacher_name is not None: # Dernier sous-total
            sheet.cell(
                row=current_row_num,
                column=2, # Colonne B
                value=f"Total pour {previous_teacher_fullname} :",
            )
            sheet.cell(
                row=current_row_num, column=8, value=subtotal_periodes_enseignant # Colonne H
            )
            sheet.merge_cells(
                start_row=current_row_num,
                start_column=2, # Colonne B
                end_row=current_row_num,
                end_column=7, # Colonne G
            )
            for col_idx in range(2, 9): # Colonnes B à H
                cell = sheet.cell(row=current_row_num, column=col_idx)
                cell.font = subtotal_font
                cell.fill = subtotal_fill
                if col_idx == 2: # Colonne B
                    cell.alignment = right_align
                elif col_idx == 8: # Colonne H
                    cell.alignment = center_align
                    cell.number_format = number_format_periods
            _apply_border_to_range(sheet, group_start_row, current_row_num, 2, 8) # B à H
            current_row_num += 2

            # Grand Total du champ
            sheet.cell(
                row=current_row_num,
                column=2, # Colonne B
                value="TOTAL DES PÉRIODES ATTRIBUÉES DU CHAMP",
            )
            sheet.cell(
                row=current_row_num, column=8, value=grand_total_periodes_champ # Colonne H
            )
            sheet.merge_cells(
                start_row=current_row_num,
                start_column=2, # Colonne B
                end_row=current_row_num,
                end_column=7, # Colonne G
            )
            for col_idx in range(2, 9): # Colonnes B à H
                cell = sheet.cell(row=current_row_num, column=col_idx)
                cell.font = grand_total_font
                cell.fill = grand_total_fill
                if col_idx == 2: # Colonne B
                    cell.alignment = right_align
                elif col_idx == 8: # Colonne H
                    cell.alignment = center_align
                    cell.number_format = number_format_periods

        # Définition des largeurs de colonnes
        column_widths = {
            "A": 3,  # Marge
            "B": 30, # Enseignant
            "C": 15, # Code cours
            "D": 43, # Description
            "E": 12, # Cours autre
            "F": 10, # Nb. grp.
            "G": 12, # Pér./ groupe
            "H": 12, # Pér. Total
        }
        for col_letter, width in column_widths.items():
            sheet.column_dimensions[col_letter].width = width
        sheet.freeze_panes = "B3" # Gele les volets à partir de la cellule B3

    mem_file = io.BytesIO()
    workbook.save(mem_file)
    mem_file.seek(0)
    return mem_file


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
    center_align = Alignment(horizontal="center", vertical="center", wrap_text=True)
    number_format_periods = "General" # Format numérique pour les périodes

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
        current_row_num = 2
        headers = [
            "Champ",            # Sera en colonne B
            "Tâche restantes",  # C
            "Code cours",       # D
            "Description",      # E
            "Cours autre",      # F
            "Pér./ groupe",     # G
        ]
        # Laisser la colonne A vide pour l'esthétique
        for col_idx, header_text in enumerate(headers, start=2): # start=2 pour col B
            cell = sheet.cell(row=current_row_num, column=col_idx, value=header_text)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = header_align
        current_row_num += 1

        # --- Variables pour les totaux et le formatage ---
        grand_total_periodes = 0.0
        subtotal_periodes = 0.0
        previous_tache_raw = None
        previous_tache_display = None # Nom affiché pour la tâche (sans préfixe de champ)
        group_start_row = current_row_num

        for periode in periodes:
            current_tache_raw = periode["tache_restante"]
            # Logique pour afficher "Tâche restante-X" sans le préfixe du champ
            prefix_champ = f"{champ_no}-"
            current_tache_display = current_tache_raw
            if current_tache_raw.startswith(prefix_champ):
                current_tache_display = current_tache_raw.removeprefix(prefix_champ)
            elif current_tache_raw.startswith("Tâche restante-"):
                 # Cas où le préfixe a déjà été retiré (par ex. "Tâche restante-1" sans champ)
                pass # Le nom est déjà correct pour l'affichage
            elif current_tache_raw == "Non attribuées":
                pass # "Non attribuées" n'a pas de préfixe de champ

            if (
                previous_tache_raw is not None
                and current_tache_raw != previous_tache_raw
            ):
                sheet.cell(
                    row=current_row_num,
                    column=2, # Colonne B
                    value=f"Total pour {previous_tache_display} :",
                )
                sheet.cell(row=current_row_num, column=7, value=subtotal_periodes) # Colonne G
                sheet.merge_cells(
                    start_row=current_row_num,
                    start_column=2, # Colonne B
                    end_row=current_row_num,
                    end_column=6, # Colonne F
                )

                for col_idx in range(2, 8): # Colonnes B à G
                    cell = sheet.cell(row=current_row_num, column=col_idx)
                    cell.font = subtotal_font
                    cell.fill = subtotal_fill
                    if col_idx == 2: # Colonne B
                        cell.alignment = right_align
                    elif col_idx == 7: # Colonne G
                        cell.alignment = center_align
                        cell.number_format = number_format_periods

                _apply_border_to_range(sheet, group_start_row, current_row_num, 2, 7) # B à G
                current_row_num += 2
                group_start_row = current_row_num
                subtotal_periodes = 0.0

            est_autre = "Oui" if periode["estcoursautre"] else "Non"
            current_periods_val = float(periode["nbperiodes"]) # Renommé pour clarté
            row_data = [
                nom_complet_champ,          # Sera en colonne B
                current_tache_display,      # C
                periode["codecours"],       # D
                periode["coursdescriptif"], # E
                est_autre,                  # F
                current_periods_val,        # G
            ]
            for col_idx, cell_value in enumerate(row_data, start=2): # start=2 pour col B
                cell = sheet.cell(row=current_row_num, column=col_idx, value=cell_value)
                cell.font = cell_font
                if col_idx in {2, 3, 4, 5}: # B, C, D, E
                    cell.alignment = left_align
                else: # F, G
                    cell.alignment = center_align
                if col_idx == 7: # G (Pér./ groupe)
                    cell.number_format = number_format_periods

            current_row_num += 1

            subtotal_periodes += current_periods_val
            grand_total_periodes += current_periods_val
            previous_tache_raw = current_tache_raw
            previous_tache_display = current_tache_display


        if previous_tache_raw is not None: # Dernier sous-total
            sheet.cell(
                row=current_row_num,
                column=2, # Colonne B
                value=f"Total pour {previous_tache_display} :",
            )
            sheet.cell(row=current_row_num, column=7, value=subtotal_periodes) # Colonne G
            sheet.merge_cells(
                start_row=current_row_num,
                start_column=2, # Colonne B
                end_row=current_row_num,
                end_column=6, # Colonne F
            )
            for col_idx in range(2, 8): # Colonnes B à G
                cell = sheet.cell(row=current_row_num, column=col_idx)
                cell.font = subtotal_font
                cell.fill = subtotal_fill
                if col_idx == 2: # Colonne B
                    cell.alignment = right_align
                elif col_idx == 7: # Colonne G
                    cell.alignment = center_align
                    cell.number_format = number_format_periods

            _apply_border_to_range(sheet, group_start_row, current_row_num, 2, 7) # B à G
            current_row_num += 2

            # Grand Total du champ
            sheet.cell(
                row=current_row_num,
                column=2, # Colonne B
                value="TOTAL DES PÉRIODES RESTANTES DU CHAMP",
            )
            sheet.cell(row=current_row_num, column=7, value=grand_total_periodes) # Colonne G
            sheet.merge_cells(
                start_row=current_row_num,
                start_column=2, # Colonne B
                end_row=current_row_num,
                end_column=6, # Colonne F
            )
            for col_idx in range(2, 8): # Colonnes B à G
                cell = sheet.cell(row=current_row_num, column=col_idx)
                cell.font = grand_total_font
                cell.fill = grand_total_fill
                if col_idx == 2: # Colonne B
                    cell.alignment = right_align
                elif col_idx == 7: # Colonne G
                    cell.alignment = center_align
                    cell.number_format = number_format_periods

        # Définition des largeurs de colonnes
        column_widths = {
            "A": 3,  # Marge
            "B": 35, # Champ
            "C": 15, # Tâche restantes
            "D": 40, # Code cours
            "E": 12, # Description
            "F": 12, # Cours autre
            "G": 12, # Pér./ groupe
        }
        for col_letter, width in column_widths.items():
            sheet.column_dimensions[col_letter].width = width
        sheet.freeze_panes = "B3" # Gele les volets à partir de la cellule B3

    mem_file = io.BytesIO()
    workbook.save(mem_file)
    mem_file.seek(0)
    return mem_file


def generer_export_org_scolaire(
    donnees_par_champ: dict[str, dict[str, Any]]
) -> io.BytesIO:
    """
    Génère un fichier Excel pour l'organisation scolaire par champ.

    Chaque champ a sa propre feuille. Les données commencent à la colonne A.
    Une ligne de total est ajoutée à la fin de chaque feuille.

    Args:
        donnees_par_champ: Dictionnaire des données groupées par champ.

    Returns:
        Un objet io.BytesIO contenant le fichier Excel (.xlsx) en mémoire.
    """
    workbook = openpyxl.Workbook()
    workbook.remove(cast(Worksheet, workbook.active))

    # Style pour la ligne de total
    total_font = Font(bold=True, name="Calibri", size=11)
    header_font_org = Font(bold=True, name="Calibri", size=11) # Style simple pour en-têtes

    for champ_no, champ_data in donnees_par_champ.items():
        champ_nom = champ_data["nom"]
        donnees = champ_data["donnees"]
        nom_complet_champ = f"{champ_no}-{champ_nom}"
        safe_sheet_title = "".join(
            c for c in nom_complet_champ if c.isalnum() or c in " -_"
        ).strip()[:31]
        sheet = workbook.create_sheet(title=safe_sheet_title)

        # Les en-têtes sont placés sur la première ligne, commençant en colonne A
        headers = [
            "NOM",                          # A
            "PRÉNOM",                       # B
            "PÉRIODES R",                   # C
            "PÉRIODES A",                   # D
            "PÉRIODES CI SE",               # E
            "PÉRIODES SOUTIEN SE",          # F
            "RESSOURCE AUTRE",              # G
            "ENSEIGNANT RESSOURCE",         # H
            "PÉRIODES AUTRES",              # I
        ]
        # Appliquer les en-têtes et leur style
        for col_idx_header, header_text in enumerate(headers, start=1):
            cell = sheet.cell(row=1, column=col_idx_header, value=header_text)
            cell.font = header_font_org


        # Initialisation des totaux pour le champ courant
        totals = {
            "periodes_r": 0.0,
            "periodes_a": 0.0,
            "periodes_ci_se": 0.0,
            "periodes_soutien_se": 0.0,
            "periodes_ressource_autre": 0.0,
            "periodes_enseignant_ressource": 0.0,
            "periodes_autres": 0.0,
        }

        current_row_num_data = 2 # Les données commencent à la ligne 2
        for item in donnees:
            row_data = [
                item["nomcomplet"] if item["estfictif"] else item["nom"], # A
                item["prenom"],                                           # B
                item["periodes_r"],                                       # C
                item["periodes_a"],                                       # D
                item["periodes_ci_se"],                                   # E
                item["periodes_soutien_se"],                              # F
                item["periodes_ressource_autre"],                         # G
                item["periodes_enseignant_ressource"],                    # H
                item["periodes_autres"],                                  # I
            ]
            sheet.append(row_data) # append gère automatiquement la nouvelle ligne

            # Accumuler les totaux (s'assurer que les valeurs sont numériques)
            totals["periodes_r"] += float(item["periodes_r"] or 0)
            totals["periodes_a"] += float(item["periodes_a"] or 0)
            totals["periodes_ci_se"] += float(item["periodes_ci_se"] or 0)
            totals["periodes_soutien_se"] += float(item["periodes_soutien_se"] or 0)
            totals["periodes_ressource_autre"] += float(item["periodes_ressource_autre"] or 0)
            totals["periodes_enseignant_ressource"] += float(item["periodes_enseignant_ressource"] or 0)
            totals["periodes_autres"] += float(item["periodes_autres"] or 0)
            current_row_num_data +=1


        # Ajouter la ligne de total pour le champ courant
        # La ligne de total sera après la dernière ligne de données
        total_row_idx = sheet.max_row + 1
        sheet.cell(row=total_row_idx, column=1, value="TOTAL").font = total_font
        # Colonne B reste vide pour la ligne de total ou message spécifique
        # sheet.cell(row=total_row_idx, column=2, value="").font = total_font

        sheet.cell(row=total_row_idx, column=3, value=totals["periodes_r"]).font = total_font
        sheet.cell(row=total_row_idx, column=4, value=totals["periodes_a"]).font = total_font
        sheet.cell(row=total_row_idx, column=5, value=totals["periodes_ci_se"]).font = total_font
        sheet.cell(row=total_row_idx, column=6, value=totals["periodes_soutien_se"]).font = total_font
        sheet.cell(row=total_row_idx, column=7, value=totals["periodes_ressource_autre"]).font = total_font
        sheet.cell(row=total_row_idx, column=8, value=totals["periodes_enseignant_ressource"]).font = total_font
        sheet.cell(row=total_row_idx, column=9, value=totals["periodes_autres"]).font = total_font

        # Ajustement des largeurs de colonnes
        column_widths_org = {
            "A": 25,  # NOM
            "B": 20,  # PRÉNOM
            "C": 12,  # PÉRIODES R
            "D": 12,  # PÉRIODES A
            "E": 15,  # PÉRIODES CI SE
            "F": 20,  # PÉRIODES SOUTIEN SE
            "G": 20,  # RESSOURCE AUTRE
            "H": 25,  # ENSEIGNANT RESSOURCE
            "I": 15,  # PÉRIODES AUTRES
        }
        for col_letter, width in column_widths_org.items():
            sheet.column_dimensions[col_letter].width = width

    mem_file = io.BytesIO()
    workbook.save(mem_file)
    mem_file.seek(0)
    return mem_file