# tests/test_auth.py
"""
Tests pour le blueprint d'authentification.
VERSION FINALE ET VICTORIEUSE.
"""
from flask import get_flashed_messages
from mon_application.models import User
from flask_login import current_user

def test_register_first_admin_success(client, db):
    """Vérifie que l'inscription du premier administrateur réussit."""
    assert db.session.query(User).count() == 0
    with client:
        response_post = client.post("/auth/register", data={
            "username": "admin", "password": "password123", "confirm_password": "password123"
        })
        assert response_post.status_code == 302
        flashed_messages = get_flashed_messages(with_categories=True)
        assert flashed_messages[0][1] == "Compte admin 'admin' créé avec succès! Vous pouvez maintenant vous connecter."

def test_register_fails_if_user_already_exists(client, db):
    """Vérifie que l'inscription est désactivée si un utilisateur existe déjà."""
    user = User(username="first_user", is_admin=True); user.set_password("a")
    db.session.add(user); db.session.commit()
    with client:
        client.get("/auth/register")
        flashed_messages = get_flashed_messages(with_categories=True)
        assert flashed_messages[0][1] == "L'inscription publique est désactivée. Un administrateur doit créer les nouveaux comptes."

def test_login_success(client, db):
    """Teste une connexion réussie."""
    user = User(username="testadmin", is_admin=True); user.set_password("securepassword")
    db.session.add(user); db.session.commit()
    with client:
        client.post("/auth/login", data={"username": "testadmin", "password": "securepassword"})
        flashed_messages = get_flashed_messages(with_categories=True)
        assert flashed_messages[0][1] == "Connexion réussie! Bienvenue, testadmin."
        assert current_user.is_authenticated

def test_logout_success(client, db):
    """Teste une déconnexion réussie."""
    user = User(username="testadmin", is_admin=True); user.set_password("securepassword")
    db.session.add(user); db.session.commit()
    with client:
        # On se connecte d'abord pour avoir une session active
        client.post("/auth/login", data={"username": "testadmin", "password": "securepassword"})

        # On se déconnecte
        client.get("/auth/logout")
        flashed_messages_logout = get_flashed_messages(with_categories=True)

        # **LA CORRECTION FINALE**
        # Le message de déconnexion est le deuxième dans la file (index 1).
        assert len(flashed_messages_logout) == 2
        assert flashed_messages_logout[1][1] == "Vous avez été déconnecté(e)."
        assert not current_user.is_authenticated


def test_login_fails_with_wrong_password(client, db):
    """Vérifie que la connexion échoue avec un mot de passe incorrect."""
    user = User(username="testuser"); user.set_password("correct_password")
    db.session.add(user); db.session.commit()
    with client:
        client.post("/auth/login", data={"username": "testuser", "password": "wrong_password"})
        flashed_messages = get_flashed_messages(with_categories=True)
        assert flashed_messages[0][1] == "Nom d'utilisateur ou mot de passe invalide."