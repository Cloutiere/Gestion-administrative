# mon_application/models.py
"""
Ce module définit le modèle d'utilisateur pour l'authentification avec Flask-Login.

Il ne contient que la classe User, qui représente un utilisateur de l'application
et fournit les méthodes requises par Flask-Login pour gérer la session utilisateur.
"""

from flask_login import UserMixin


class User(UserMixin):
    """
    Représente un utilisateur de l'application avec des rôles distincts.

    Cette classe hérite de UserMixin, qui fournit les implémentations par défaut
    des propriétés et méthodes requises par Flask-Login (is_authenticated,
    is_active, etc.). Elle gère trois types de rôles :
    - Administrateur (`is_admin` = True) : Accès complet.
    - Observateur de Tableau de Bord (`is_dashboard_only` = True) : Accès en lecture
      seule aux pages de sommaire global et aux pages de détail des champs.
    - Utilisateur Standard : Accès limité à des champs spécifiques via `allowed_champs`.
    """

    def __init__(
        self,
        _id: int,
        username: str,
        is_admin: bool = False,
        is_dashboard_only: bool = False,
        allowed_champs: list[str] | None = None,
    ):
        """
        Initialise un nouvel objet User.

        Args:
            _id (int): L'identifiant unique de l'utilisateur.
            username (str): Le nom d'utilisateur.
            is_admin (bool): Si True, l'utilisateur a des privilèges d'administrateur.
                             Ce rôle prime sur les autres.
            is_dashboard_only (bool): Si True, l'utilisateur a un accès en lecture
                                      aux tableaux de bord et aux détails des champs.
                                      Ce rôle est exclusif avec `is_admin`.
            allowed_champs (list[str] | None): Liste des numéros de champ (ChampNo)
                                              auxquels un utilisateur standard a
                                              accès. Ignoré pour les admins et les
                                              observateurs de tableau de bord.
        """
        self.id = _id
        self.username = username
        self.is_admin = is_admin
        self.is_dashboard_only = is_dashboard_only

        # Un utilisateur standard a des accès basés sur les champs autorisés.
        # Pour les admins ou les observateurs, la liste des champs n'est pas
        # pertinente pour leur mode d'accès principal et doit être vide.
        self.allowed_champs = allowed_champs if allowed_champs is not None else []

    def get_id(self) -> str:
        """
        Retourne l'identifiant unique de l'utilisateur (requis par Flask-Login).
        L'identifiant est converti en chaîne de caractères.
        """
        return str(self.id)

    def can_access_champ(self, champ_no: str) -> bool:
        """
        Vérifie si l'utilisateur a l'autorisation d'accéder à une page de champ
        spécifique (/champ/<champ_no>).

        Args:
            champ_no (str): Le numéro du champ à vérifier.

        Returns:
            bool: True si l'utilisateur est admin, un observateur de tableau de bord,
                  ou si le champ est dans sa liste d'accès explicite (pour les
                  utilisateurs standards).
        """
        # CORRECTION : Les admins ET les observateurs de tableau de bord ont maintenant
        # accès à toutes les pages de détail des champs.
        if self.is_admin or self.is_dashboard_only:
            return True

        # Pour les utilisateurs standards (ni admin, ni dashboard_only), l'accès
        # est déterminé par la liste `allowed_champs`.
        return champ_no in self.allowed_champs