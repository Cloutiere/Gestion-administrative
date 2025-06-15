# mon_application/dashboard.py
"""
Ce module contient le Blueprint pour les routes du tableau de bord.

Il regroupe les pages HTML et les points d'API RESTful destinés à la
visualisation des données et à leur exportation, accessibles aux administrateurs
et aux utilisateurs ayant le rôle "dashboard_only".
Les permissions sont gérées par les décorateurs `dashboard_access_required`
et `dashboard_api_access_required`.
"""

from typing import Any, cast

from flask import (
    Blueprint,
    current_app,
    flash,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_login import current_user
from werkzeug.wrappers import Response

from . import database as db
from . import exports
from .utils import dashboard_access_required, dashboard_api_access_required

# Crée un Blueprint 'dashboard'.
bp = Blueprint("dashboard", __name__, url_prefix="/admin")


# --- Fonctions utilitaires pour le sommaire (dépendantes de l'année) ---
def calculer_donnees_sommaire(
    annee_id: int,
) -> tuple[
    list[dict[str, Any]], dict[str, dict[str, Any]], float, float, dict[str, float]
]:
    """
    Calcule les données agrégées pour la page sommaire globale pour une année donnée.

    Args:
        annee_id: L'ID de l'année scolaire pour laquelle calculer les données.

    Returns:
        Un tuple contenant :
        - La liste des enseignants groupés par champ (pour la page de détail).
        - Un dictionnaire des moyennes et totaux par champ, incluant les statuts.
        - La moyenne générale des périodes pour les enseignants à temps plein.
        - La moyenne "Préliminaire confirmée" (enseignants TP des champs confirmés).
        - Un dictionnaire contenant les totaux globaux pour le pied de tableau.
    """
    tous_les_champs = db.get_all_champs()
    statuts_champs = db.get_all_champ_statuses_for_year(annee_id)
    tous_enseignants_details = db.get_all_enseignants_avec_details(annee_id)

    moyennes_par_champ_calculees: dict[str, Any] = {}
    for champ in tous_les_champs:
        champ_no = str(champ["champno"])
        statut = statuts_champs.get(
            champ_no, {"est_verrouille": False, "est_confirme": False}
        )
        moyennes_par_champ_calculees[champ_no] = {
            "champ_nom": champ["champnom"],
            "est_verrouille": statut["est_verrouille"],
            "est_confirme": statut["est_confirme"],
            "nb_enseignants_tp": 0,
            "periodes_choisies_tp": 0.0,
            "moyenne": 0.0,
            "periodes_magiques": 0.0,
        }

    enseignants_par_champ_temp: dict[str, dict[str, Any]] = {
        str(champ["champno"]): {
            "champno": str(champ["champno"]),
            "champnom": champ["champnom"],
            "enseignants": [],
            "est_verrouille": moyennes_par_champ_calculees[str(champ["champno"])][
                "est_verrouille"
            ],
            "est_confirme": moyennes_par_champ_calculees[str(champ["champno"])][
                "est_confirme"
            ],
        }
        for champ in tous_les_champs
    }

    for ens in tous_enseignants_details:
        champ_no = ens["champno"]
        if champ_no in enseignants_par_champ_temp:
            enseignants_par_champ_temp[champ_no]["enseignants"].append(ens)

        if (
            ens["compte_pour_moyenne_champ"]
            and champ_no in moyennes_par_champ_calculees
        ):
            moyennes_par_champ_calculees[champ_no]["nb_enseignants_tp"] += 1
            moyennes_par_champ_calculees[champ_no]["periodes_choisies_tp"] += ens[
                "total_periodes"
            ]

    total_periodes_global_tp = 0.0
    nb_enseignants_tp_global = 0
    total_periodes_confirme_tp = 0.0
    nb_enseignants_confirme_tp = 0
    total_enseignants_tp_etablissement = 0
    total_periodes_choisies_tp_etablissement = 0.0
    total_periodes_magiques_etablissement = 0.0

    for data in moyennes_par_champ_calculees.values():
        nb_ens_tp = data["nb_enseignants_tp"]
        periodes_choisies_tp = data["periodes_choisies_tp"]

        data["moyenne"] = (periodes_choisies_tp / nb_ens_tp) if nb_ens_tp > 0 else 0.0
        data["periodes_magiques"] = periodes_choisies_tp - (nb_ens_tp * 24)

        total_enseignants_tp_etablissement += nb_ens_tp
        total_periodes_choisies_tp_etablissement += periodes_choisies_tp
        total_periodes_magiques_etablissement += data["periodes_magiques"]

        if nb_ens_tp > 0:
            total_periodes_global_tp += periodes_choisies_tp
            nb_enseignants_tp_global += nb_ens_tp
            if data["est_confirme"]:
                total_periodes_confirme_tp += periodes_choisies_tp
                nb_enseignants_confirme_tp += nb_ens_tp

    moyenne_generale_calculee = (
        (total_periodes_global_tp / nb_enseignants_tp_global)
        if nb_enseignants_tp_global > 0
        else 0.0
    )
    moyenne_prelim_conf = (
        (total_periodes_confirme_tp / nb_enseignants_confirme_tp)
        if nb_enseignants_confirme_tp > 0
        else 0.0
    )

    grand_totals = {
        "total_enseignants_tp": float(total_enseignants_tp_etablissement),
        "total_periodes_choisies_tp": total_periodes_choisies_tp_etablissement,
        "total_periodes_magiques": total_periodes_magiques_etablissement,
    }

    return (
        list(enseignants_par_champ_temp.values()),
        moyennes_par_champ_calculees,
        moyenne_generale_calculee,
        moyenne_prelim_conf,
        grand_totals,
    )


# --- ROUTES DES PAGES (HTML) ---


@bp.route("/sommaire")
@dashboard_access_required
def page_sommaire() -> str:
    """Affiche la page du sommaire global des moyennes pour l'année active."""
    annee_active = cast(dict[str, Any] | None, getattr(g, "annee_active", None))
    if not annee_active:
        flash(
            "Aucune année scolaire n'est disponible. Veuillez en créer une "
            "dans la section 'Données'.",
            "warning",
        )
        return render_template(
            "page_sommaire.html",
            moyennes_par_champ={},
            moyenne_generale=0.0,
            moyenne_preliminaire_confirmee=0.0,
            grand_totals={
                "total_enseignants_tp": 0,
                "total_periodes_choisies_tp": 0.0,
                "total_periodes_magiques": 0.0,
            },
        )

    annee_id = annee_active["annee_id"]
    _, moyennes_champs, moyenne_gen, moyenne_prelim_conf, grand_totals_data = (
        calculer_donnees_sommaire(annee_id)
    )

    return render_template(
        "page_sommaire.html",
        moyennes_par_champ=moyennes_champs,
        moyenne_generale=moyenne_gen,
        moyenne_preliminaire_confirmee=moyenne_prelim_conf,
        grand_totals=grand_totals_data,
    )


@bp.route("/detail_taches")
@dashboard_access_required
def page_detail_taches() -> str:
    """Affiche la page de détail des tâches par enseignant pour l'année active."""
    annee_active = cast(dict[str, Any] | None, getattr(g, "annee_active", None))
    if not annee_active:
        flash(
            "Aucune année scolaire n'est disponible. Les détails ne peuvent "
            "être affichés.",
            "warning",
        )
        return render_template("detail_taches.html", enseignants_par_champ=[])

    annee_id = annee_active["annee_id"]
    enseignants_par_champ_data, _, _, _, _ = calculer_donnees_sommaire(annee_id)

    return render_template(
        "detail_taches.html", enseignants_par_champ=enseignants_par_champ_data
    )


# --- API ENDPOINTS (JSON) ---


@bp.route("/api/annees/changer_active", methods=["POST"])
@dashboard_api_access_required
def api_changer_annee_active() -> tuple[Response, int]:
    """API pour changer l'année de travail (stockée en session)."""
    data = request.get_json()
    if not data or not (annee_id := data.get("annee_id")):
        return (
            jsonify({"success": False, "message": "ID de l'année manquant."}),
            400,
        )

    session["annee_scolaire_id"] = annee_id
    toutes_les_annees = cast(list[dict[str, Any]], getattr(g, "toutes_les_annees", []))
    annee_selectionnee = next(
        (annee for annee in toutes_les_annees if annee["annee_id"] == annee_id),
        None,
    )
    if annee_selectionnee:
        current_app.logger.info(
            f"Année de travail changée pour l'utilisateur '{current_user.username}' : "
            f"'{annee_selectionnee['libelle_annee']}'."
        )
    return jsonify({"success": True, "message": "Année de travail changée."}), 200


@bp.route("/api/sommaire/donnees", methods=["GET"])
@dashboard_api_access_required
def api_get_donnees_sommaire() -> tuple[Response, int]:
    """API pour récupérer les données du sommaire pour l'année active."""
    annee_active = cast(dict[str, Any] | None, getattr(g, "annee_active", None))
    if not annee_active:
        current_app.logger.warning(
            "API sommaire: Aucune année active, retour de données vides."
        )
        return (
            jsonify(
                enseignants_par_champ=[],
                moyennes_par_champ={},
                moyenne_generale=0.0,
                moyenne_preliminaire_confirmee=0.0,
                grand_totals={
                    "total_enseignants_tp": 0,
                    "total_periodes_choisies_tp": 0.0,
                    "total_periodes_magiques": 0.0,
                },
            ),
            200,
        )

    annee_id = annee_active["annee_id"]
    (
        enseignants_groupes,
        moyennes_champs,
        moyenne_gen,
        moyenne_prelim_conf,
        grand_totals_data,
    ) = calculer_donnees_sommaire(annee_id)
    return (
        jsonify(
            enseignants_par_champ=enseignants_groupes,
            moyennes_par_champ=moyennes_champs,
            moyenne_generale=moyenne_gen,
            moyenne_preliminaire_confirmee=moyenne_prelim_conf,
            grand_totals=grand_totals_data,
        ),
        200,
    )


@bp.route("/exporter_taches_excel")
@dashboard_access_required
def exporter_taches_excel() -> Response:
    """Exporte toutes les tâches attribuées pour l'année active dans un fichier Excel."""
    annee_active = cast(dict[str, Any] | None, getattr(g, "annee_active", None))
    if not annee_active:
        flash("Exportation impossible : aucune année scolaire n'est active.", "error")
        return redirect(url_for("dashboard.page_sommaire"))

    annee_id = annee_active["annee_id"]
    annee_libelle = annee_active["libelle_annee"]
    attributions_raw = db.get_all_attributions_for_export(annee_id)

    if not attributions_raw:
        flash(f"Aucune tâche attribuée pour '{annee_libelle}'.", "warning")
        return redirect(url_for("dashboard.page_sommaire"))

    attributions_par_champ: dict[str, dict[str, Any]] = {}
    for attr in attributions_raw:
        champ_no = attr["champno"]
        if champ_no not in attributions_par_champ:
            attributions_par_champ[champ_no] = {
                "nom": attr["champnom"],
                "attributions": [],
            }
        attributions_par_champ[champ_no]["attributions"].append(attr)

    mem_file = exports.generer_export_taches(attributions_par_champ)
    filename = f"export_taches_{annee_libelle}.xlsx"
    current_app.logger.info(f"Génération du fichier d'export '{filename}'.")

    return Response(
        mem_file,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@bp.route("/exporter_periodes_restantes_excel")
@dashboard_access_required
def exporter_periodes_restantes_excel() -> Response:
    """Exporte les périodes non attribuées (restantes) pour l'année active."""
    annee_active = cast(dict[str, Any] | None, getattr(g, "annee_active", None))
    if not annee_active:
        flash("Exportation impossible : aucune année scolaire n'est active.", "error")
        return redirect(url_for("dashboard.page_sommaire"))

    annee_id = annee_active["annee_id"]
    annee_libelle = annee_active["libelle_annee"]
    periodes_restantes_raw = db.get_periodes_restantes_for_export(annee_id)

    if not periodes_restantes_raw:
        flash(f"Aucune période restante pour '{annee_libelle}'.", "warning")
        return redirect(url_for("dashboard.page_sommaire"))

    periodes_par_champ: dict[str, dict[str, Any]] = {}
    for periode in periodes_restantes_raw:
        champ_no = periode["champno"]
        if champ_no not in periodes_par_champ:
            periodes_par_champ[champ_no] = {
                "nom": periode["champnom"],
                "periodes": [],
            }
        periodes_par_champ[champ_no]["periodes"].append(periode)

    mem_file = exports.generer_export_periodes_restantes(periodes_par_champ)
    filename = f"export_periodes_restantes_{annee_libelle}.xlsx"
    current_app.logger.info(f"Génération de l'export '{filename}'.")

    return Response(
        mem_file,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@bp.route("/exporter_org_scolaire_excel")
@dashboard_access_required
def exporter_org_scolaire_excel() -> Response:
    """Exporte les données pour l'organisation scolaire pour l'année active."""
    annee_active = cast(dict[str, Any] | None, getattr(g, "annee_active", None))
    if not annee_active:
        flash("Exportation impossible : aucune année scolaire n'est active.", "error")
        return redirect(url_for("dashboard.page_sommaire"))

    annee_id = annee_active["annee_id"]
    annee_libelle = annee_active["libelle_annee"]

    tous_les_financements = db.get_all_financements()
    libelle_to_header_map = {
        f["libelle"].upper(): f"PÉRIODES {f['libelle'].upper()}"
        for f in tous_les_financements
    }
    libelle_to_header_map["SOUTIEN EN SPORT-ÉTUDES"] = "PÉRIODES SOUTIEN SPORT-ÉTUDES"

    code_to_libelle_map = {f["code"]: f["libelle"].upper() for f in tous_les_financements}

    donnees_raw = db.get_data_for_org_scolaire_export(annee_id)
    if not donnees_raw:
        flash(f"Aucune donnée à exporter pour '{annee_libelle}'.", "warning")
        return redirect(url_for("dashboard.page_sommaire"))

    pivot_data: dict[str, dict[str, Any]] = {}
    ALL_HEADERS = [
        "PÉRIODES RÉGULIER",
        "PÉRIODES ADAPTATION SCOLAIRE",
        "PÉRIODES SPORT-ÉTUDES",
        "PÉRIODES ENSEIGNANT RESSOURCE",
        "PÉRIODES AIDESEC",
        "PÉRIODES DIPLÔMA",
        "PÉRIODES MESURE SEUIL (UTILISÉE COORDINATION PP)",
        "PÉRIODES MESURE SEUIL (RESSOURCES AUTRES)",
        "PÉRIODES MESURE SEUIL (POUR FABLAB)",
        "PÉRIODES MESURE SEUIL (BONIFIER ALTERNE)",
        "PÉRIODES ALTERNE",
        "PÉRIODES FORMANUM",
        "PÉRIODES MENTORAT",
        "PÉRIODES COORDINATION SPORT-ÉTUDES",
        "PÉRIODES SOUTIEN SPORT-ÉTUDES",
    ]

    for item in donnees_raw:
        champ_no = item["champno"]
        enseignant_key = (
            f"fictif-{item['nomcomplet']}"
            if item["estfictif"]
            else f"reel-{item['nom']}-{item['prenom']}"
        )

        if enseignant_key not in pivot_data.setdefault(champ_no, {}):
            pivot_data[champ_no][enseignant_key] = {
                "nom": item["nom"],
                "prenom": item["prenom"],
                "nomcomplet": item["nomcomplet"],
                "estfictif": item["estfictif"],
                "champnom": item["champnom"],
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
        else:
            current_app.logger.warning(
                f"L'en-tête de colonne '{target_col}' n'a pas été trouvé. "
                f"Les périodes pour le code '{financement_code}' sont ignorées."
            )

    donnees_par_champ: dict[str, dict[str, Any]] = {}
    for champ_no, enseignants in pivot_data.items():
        donnees_par_champ[champ_no] = {
            "nom": next(iter(enseignants.values()))["champnom"],
            "donnees": list(enseignants.values()),
        }

    mem_file = exports.generer_export_org_scolaire(donnees_par_champ)
    filename = f"export_org_scolaire_{annee_libelle}.xlsx"
    current_app.logger.info(f"Génération de l'export '{filename}'.")

    return Response(
        mem_file,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )