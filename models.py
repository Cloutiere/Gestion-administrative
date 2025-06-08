# models.py
"""
Ce module définit le modèle d'utilisateur pour l'authentification avec Flask-Login.
Il inclut la classe User et des fonctions utilitaires pour le hachage des mots de passe.
"""

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash


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
            _id (int): L'identifiant unique de l'utilisateur dans la base de données.
            username (str): Le nom d'utilisateur.
            is_admin (bool): Indique si l'utilisateur a des privilèges d'administrateur.
            allowed_champs (list[str] | None): Liste des numéros de champ (ChampNo) auxquels
                                              cet utilisateur a un accès explicite.
                                              Ignoré si l'utilisateur est admin (accès à tout).
        """
        self.id = _id
        self.username = username
        self.is_admin = is_admin
        # Si l'utilisateur est admin, il a accès à tous les champs.
        # Sinon, l'accès est limité par la liste fournie.
        self.allowed_champs = allowed_champs if not is_admin else [] # La liste sera vide pour les admins pour simplifier la logique de vérification, puisque is_admin sera prioritaire.

    def get_id(self):
        """
        Retourne l'identifiant unique de l'utilisateur, requis par Flask-Login.
        """
        return str(self.id)

    def can_access_champ(self, champ_no: str) -> bool:
        """
        Vérifie si l'utilisateur a l'autorisation d'accéder à un champ spécifique.

        Args:
            champ_no (str): Le numéro du champ à vérifier.

        Returns:
            bool: True si l'utilisateur est admin ou si le champ est dans sa liste d'accès,
                  False sinon.
        """
        if self.is_admin:
            return True
        return champ_no in self.allowed_champs


def hash_password(password: str) -> str:
    """
    Hache un mot de passe en utilisant une méthode sécurisée (SHA256 par défaut).
    Cette fonction doit être utilisée avant de stocker le mot de passe dans la base de données.

    Args:
        password (str): Le mot de passe en texte clair.

    Returns:
        str: Le hachage du mot de passe.
    """
    return generate_password_hash(password)


def check_hashed_password(hashed_password: str, password: str) -> bool:
    """
    Vérifie si un mot de passe en texte clair correspond à un mot de passe haché.

    Args:
        hashed_password (str): Le mot de passe haché stocké dans la base de données.
        password (str): Le mot de passe en texte clair fourni par l'utilisateur.

    Returns:
        bool: True si les mots de passe correspondent, False sinon.
    """
    return check_password_hash(hashed_password, password)
