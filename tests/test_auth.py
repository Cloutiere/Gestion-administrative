# tests/test_auth.py
from mon_application.models import User

def test_register_first_admin_success(client, db):
    assert db.session.query(User).count() == 0
    response = client.post("/auth/register", data={
        "username": "admin", "password": "password123", "confirm_password": "password123"
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b"Compte admin 'admin' cr\xc3\xa9\xc3\xa9 avec succ\xc3\xa8s!" in response.data

def test_register_fails_if_user_already_exists(client, db):
    user = User(username="first_user", is_admin=True)
    user.set_password("a_password")
    db.session.add(user)
    db.session.commit()
    response = client.get("/auth/register", follow_redirects=True)
    assert response.status_code == 200
    assert b"L'inscription publique est d\xc3\xa9sactiv\xc3\xa9e" in response.data

def test_login_and_logout(client, db):
    user = User(username="testadmin", is_admin=True)
    user.set_password("securepassword")
    db.session.add(user)
    db.session.commit()
    response_login = client.post("/auth/login", data={
        "username": "testadmin", "password": "securepassword"
    }, follow_redirects=True)
    assert b"Connexion r\xc3\xa9ussie!" in response_login.data
    response_logout = client.get("/auth/logout", follow_redirects=True)
    assert b"Vous avez \xc3\xa9t\xc3\xa9 d\xc3\xa9connect\xc3\xa9(e)." in response_logout.data

def test_login_fails_with_wrong_password(client, db):
    user = User(username="testuser")
    user.set_password("correct_password")
    db.session.add(user)
    db.session.commit()
    response = client.post("/auth/login", data={
        "username": "testuser", "password": "wrong_password"
    }, follow_redirects=True)
    assert b"Nom d'utilisateur ou mot de passe invalide." in response.data