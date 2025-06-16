# tests/test_auth.py
from mon_application.services import create_user_account # On importe nos fonctions de service

# On ne se soucie PAS de la connexion à la BDD, de la création de l'app, etc.
# Pytest gère tout cela en coulisses.

def test_successful_login(client):
    """
    Teste un scénario de connexion réussi.
    """
    # 1. ÉTAT INITIAL : Puisque la BDD est vide, on crée un utilisateur pour le test.
    # Note : Pour cela, il nous faudrait un contexte d'application, mais c'est un détail.
    # On peut le faire via un service ou une autre fixture.
    create_user_account(username="testuser", password="password123", is_admin=False)

    # 2. ACTION : On simule l'envoi du formulaire de connexion.
    response = client.post("/auth/login", data={
        "username": "testuser",
        "password": "password123"
    })

    # 3. VÉRIFICATION : On vérifie que la connexion a réussi.
    # Une connexion réussie doit rediriger l'utilisateur (code 302).
    assert response.status_code == 302
    # La redirection doit pointer vers la page d'accueil.
    assert response.headers["Location"] == "/"

def test_failed_login_bad_password(client):
    """
    Teste un scénario de connexion échoué (mauvais mot de passe).
    """
    # 1. ÉTAT INITIAL : On crée le même utilisateur.
    create_user_account(username="testuser2", password="password123", is_admin=False)

    # 2. ACTION : On essaie de se connecter avec un mauvais mot de passe.
    response = client.post("/auth/login", data={
        "username": "testuser2",
        "password": "wrongpassword"
    })

    # 3. VÉRIFICATION :
    # La page doit se recharger (code 200) et afficher un message d'erreur.
    assert response.status_code == 200
    assert b"Identifiants invalides" in response.data # On vérifie la présence du message flash.