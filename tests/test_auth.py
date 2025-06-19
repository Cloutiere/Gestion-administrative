# tests/test_auth.py
"""
Tests pour le blueprint d'authentification, utilisant une BDD SQLite en mémoire.
"""
from mon_application.models import User
from flask_login import current_user

# MODIFIÉ : Le paramètre est maintenant 'db', pour correspondre à la fixture dans conftest.py
def test_register_first_admin_success(client, db):
    """
    Vérifie que l'inscription du premier administrateur réussit.
    """
    assert db.session.query(User).count() == 0

    with client:
        response_post = client.post("/auth/register", data={
            "username": "admin",
            "password": "password123",
            "confirm_password": "password123",
        })
        assert response_post.status_code == 302
        assert response_post.location == "/auth/login"

        response_get = client.get(response_post.location)
        assert response_get.status_code == 200
        assert b"Compte admin 'admin' cr\xc3\xa9\xc3\xa9 avec succ\xc3\xa8s!" in response_get.data

    assert db.session.query(User).count() == 1


# MODIFIÉ : Le paramètre est maintenant 'db'
def test_register_fails_if_user_already_exists(client, db):
    """
    Vérifie que l'inscription est désactivée si un utilisateur existe déjà.
    """
    user = User(username="first_user", is_admin=True)
    user.set_password("a_password")
    db.session.add(user)
    db.session.commit()
    assert db.session.query(User).count() == 1

    response = client.get("/auth/register", follow_redirects=True)
    assert response.status_code == 200
    assert b"L'inscription publique est d\xc3\xa9sactiv\xc3\xa9e" in response.data


# MODIFIÉ : Le paramètre est maintenant 'db'
def test_login_and_logout(client, db):
    """
    Teste le cycle complet de connexion et de déconnexion.
    """
    user = User(username="testadmin", is_admin=True)
    user.set_password("securepassword")
    db.session.add(user)
    db.session.commit()

    with client:
        response_login = client.post("/auth/login", data={
            "username": "testadmin", "password": "securepassword"
        }, follow_redirects=True)
        assert response_login.status_code == 200
        assert b"Connexion r\xc3\xa9ussie!" in response_login.data
        assert b"Page Sommaire" in response_login.data
        assert current_user.is_authenticated

        response_logout = client.get("/auth/logout", follow_redirects=True)
        assert response_logout.status_code == 200
        assert b"Vous avez \xc3\xa9t\xc3\xa9 d\xc3\xa9connect\xc3\xa9(e)." in response_logout.data
        assert not current_user.is_authenticated


# MODIFIÉ : Le paramètre est maintenant 'db'
def test_login_fails_with_wrong_password(client, db):
    """
    Vérifie que la connexion échoue avec un mot de passe incorrect.
    """
    user = User(username="testuser")
    user.set_password("correct_password")
    db.session.add(user)
    db.session.commit()

    response = client.post("/auth/login", data={
        "username": "testuser", "password": "wrong_password"
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b"Nom d'utilisateur ou mot de passe invalide." in response.data