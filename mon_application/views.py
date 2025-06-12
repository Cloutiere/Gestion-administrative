# mon_application/views.py
"""
Ce module contient le Blueprint pour les vues principales de l'application.

Il gère les routes qui ne sont ni liées à l'authentification ni à l'administration,
comme la page d'accueil et la page de visualisation d'un champ.
Toutes les données affichées sont relatives à l'année scolaire active.
"""

from typing import Any

from flask import Blueprint, flash, g, redirect, render_template, url_for
from flask_login import current_user, login_required

# Importe les fonctions de base de données nécessaires
from . import database as db

# Crée un Blueprint nommé 'views'.
bp = Blueprint("views", __name__)


@bp.route("/")
@login_required
def index() -> Any:
    """
    Affiche la page d'accueil, listant les champs accessibles à l'utilisateur.
    Si aucune année scolaire n'est configurée, guide l'administrateur.
    """
    # Si aucune année n'est active, on ne peut rien afficher.
    if not g.annee_active:
        if current_user.is_admin:
            flash("Aucune année scolaire n'est active. Veuillez en créer une dans la page 'Administration (Données)'.", "warning")
        else:
            flash("L'application n'est pas encore configurée pour l'année en cours. Veuillez contacter un administrateur.", "error")
        return render_template("index.html", champs=[])

    all_champs = db.get_all_champs()
    if current_user.is_admin:
        champs_accessible = all_champs
    else:
        champs_accessible = [champ for champ in all_champs if current_user.can_access_champ(champ["champno"])]

    # Si un utilisateur non-admin n'a accès qu'à un seul champ, le rediriger directement.
    if not current_user.is_admin and len(champs_accessible) == 1:
        return redirect(url_for("views.page_champ", champ_no=champs_accessible[0]["champno"]))

    return render_template("index.html", champs=champs_accessible)


@bp.route("/champ/<string:champ_no>")
@login_required
def page_champ(champ_no: str) -> Any:
    """
    Affiche la page détaillée d'un champ spécifique pour l'année scolaire active.
    Accessible aux admins ou aux utilisateurs ayant la permission.
    """
    # Vérification cruciale : pas de données sans année active.
    if not g.annee_active:
        flash("Impossible d'afficher le champ : aucune année scolaire n'est active.", "error")
        return redirect(url_for("views.index"))

    annee_id = g.annee_active["annee_id"]

    # Vérifie si l'utilisateur est autorisé à voir ce champ.
    if not current_user.can_access_champ(champ_no):
        flash("Vous n'avez pas la permission d'accéder à ce champ.", "error")
        return redirect(url_for("views.index"))

    # Récupère les détails du champ, y compris son statut de verrouillage pour l'année active.
    champ_details = db.get_champ_details(champ_no, annee_id)
    if not champ_details:
        flash(f"Le champ {champ_no} n'a pas été trouvé.", "error")
        return redirect(url_for("views.index"))

    # Récupération des données pour l'année active.
    enseignants_du_champ = db.get_enseignants_par_champ(champ_no, annee_id)
    cours_disponibles_bruts = db.get_cours_disponibles_par_champ(champ_no, annee_id)
    cours_enseignement_champ = [c for c in cours_disponibles_bruts if not c["estcoursautre"]]
    cours_autres_taches_champ = [c for c in cours_disponibles_bruts if c["estcoursautre"]]

    # Agrégation et calcul des données pour le template Jinja2.
    enseignants_complets = []
    total_periodes_tp = 0.0
    nb_enseignants_tp = 0
    for ens in enseignants_du_champ:
        # L'ID de l'enseignant est unique pour une année, donc ces appels sont correctement ciblés.
        attributions = db.get_attributions_enseignant(ens["enseignantid"])
        periodes = db.calculer_periodes_pour_attributions(attributions)
        enseignants_complets.append({"attributions": attributions, "periodes_actuelles": periodes, **ens})
        if ens["esttempsplein"] and not ens["estfictif"]:
            total_periodes_tp += periodes["total_periodes"]
            nb_enseignants_tp += 1

    moyenne_champ = (total_periodes_tp / nb_enseignants_tp) if nb_enseignants_tp > 0 else 0.0

    return render_template(
        "page_champ.html",
        champ=champ_details,
        enseignants_data=enseignants_complets,
        cours_enseignement_champ=cours_enseignement_champ,
        cours_autres_taches_champ=cours_autres_taches_champ,
        moyenne_champ_initiale=moyenne_champ,
    )