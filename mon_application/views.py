# mon_application/views.py
"""
Ce module contient le Blueprint pour les vues principales de l'application.

Il gère les routes qui ne sont ni liées à l'authentification ni à l'administration,
comme la page de visualisation d'un champ.
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
    Page d'accueil de l'application.
    Redirige les utilisateurs vers la page appropriée en fonction de leur rôle.
    - Admin et Observateur: vers le tableau de bord global.
    - Utilisateur Standard: vers la page du premier champ auquel il a accès.
    """
    if current_user.is_admin or current_user.is_dashboard_only:
        return redirect(url_for("admin.page_sommaire"))

    # Pour les utilisateurs standards, on les redirige vers le premier champ accessible.
    if current_user.allowed_champs:
        premier_champ = current_user.allowed_champs[0]
        return redirect(url_for("views.page_champ", champ_no=premier_champ))

    # Cas par défaut : si un utilisateur n'a aucun rôle ni aucun champ,
    # on le déconnecte avec un message car il ne peut rien faire.
    flash(
        "Votre compte n'a aucune permission configurée. Veuillez contacter un administrateur.",
        "warning",
    )
    return redirect(url_for("auth.logout"))


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
        # Redirige vers la page d'accueil qui choisira la bonne destination.
        return redirect(url_for("views.index"))

    # Vérifie si l'utilisateur est autorisé à voir ce champ.
    if not current_user.can_access_champ(champ_no):
        flash("Vous n'avez pas la permission d'accéder à ce champ.", "error")
        return redirect(url_for("views.index"))

    # Récupère les détails du champ, y compris son statut de verrouillage pour l'année active.
    champ_details = db.get_champ_details(champ_no, g.annee_active["annee_id"])
    if not champ_details:
        flash(f"Le champ {champ_no} n'a pas été trouvé.", "error")
        return redirect(url_for("views.index"))

    # Récupération des données pour l'année active.
    enseignants_du_champ = db.get_enseignants_par_champ(
        champ_no, g.annee_active["annee_id"]
    )
    cours_disponibles_bruts = db.get_cours_disponibles_par_champ(
        champ_no, g.annee_active["annee_id"]
    )
    cours_enseignement_champ = [
        c for c in cours_disponibles_bruts if not c["estcoursautre"]
    ]
    cours_autres_taches_champ = [
        c for c in cours_disponibles_bruts if c["estcoursautre"]
    ]

    # Agrégation et calcul des données pour le template Jinja2.
    enseignants_complets = []
    total_periodes_tp = 0.0
    nb_enseignants_tp = 0
    for ens in enseignants_du_champ:
        # L'ID de l'enseignant est unique pour une année, donc ces appels sont correctement ciblés.
        attributions = db.get_attributions_enseignant(ens["enseignantid"])
        periodes = db.calculer_periodes_pour_attributions(attributions)
        enseignants_complets.append(
            {"attributions": attributions, "periodes_actuelles": periodes, **ens}
        )
        if ens["esttempsplein"] and not ens["estfictif"]:
            total_periodes_tp += periodes["total_periodes"]
            nb_enseignants_tp += 1

    moyenne_champ = (
        (total_periodes_tp / nb_enseignants_tp) if nb_enseignants_tp > 0 else 0.0
    )

    return render_template(
        "page_champ.html",
        champ=champ_details,
        enseignants_data=enseignants_complets,
        cours_enseignement_champ=cours_enseignement_champ,
        cours_autres_taches_champ=cours_autres_taches_champ,
        moyenne_champ_initiale=moyenne_champ,
    )