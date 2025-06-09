# mon_application/models.py
"""
Ce module définit le modèle d'utilisateur pour l'authentification avec Flask-Login.

Il ne contient que la classe User, qui représente un utilisateur de l'application
et fournit les méthodes requises par Flask-Login.
"""

from flask_login import UserMixin


class User(UserMixin):
    """
    Représente un utilisateur de l'application.

    Cette classe hérite de UserMixin, qui fournit les implémentations par défaut
    des propriétés et méthodes requises par Flask-Login (is_authenticated, is_active, etc.).
    """

    def __init__(self, _id: int, username: str, is_admin: bool = False, allowed_champs: list[str] | None = None):
        """
        Initialise un nouvel objet User.

        Args:
            _id (int): L'identifiant unique de l'utilisateur.
            username (str): Le nom d'utilisateur.
            is_admin (bool): Indique si l'utilisateur a des privilèges d'administrateur.
            allowed_champs (list[str] | None): Liste des numéros de champ (ChampNo) auxquels
                                              cet utilisateur a un accès explicite.
                                              Une liste vide si admin (accès à tout).
        """
        self.id = _id
        self.username = username
        self.is_admin = is_admin
        # Si l'utilisateur est admin, allowed_champs sera une liste vide car l'accès est
        # géré par is_admin. Sinon, l'accès est limité par la liste fournie.
        self.allowed_champs = allowed_champs if allowed_champs is not None else []

    def get_id(self) -> str:
        """
        Retourne l'identifiant unique de l'utilisateur (requis par Flask-Login).
        """
        return str(self.id)

    def can_access_champ(self, champ_no: str) -> bool:
        """
        Vérifie si l'utilisateur a l'autorisation d'accéder à un champ spécifique.

        Args:
            champ_no (str): Le numéro du champ à vérifier.

        Returns:
            bool: True si l'utilisateur est admin ou si le champ est dans sa liste d'accès.
        """
        if self.is_admin:
            return True
        return champ_no in self.allowed_champs
