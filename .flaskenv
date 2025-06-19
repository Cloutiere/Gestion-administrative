# .flaskenv
# Ce fichier définit les variables d'environnement pour le CLI de Flask.

# Indique explicitement où trouver la factory de l'application.
# Format: nom_du_paquet:nom_de_la_fonction_factory
# C'est plus robuste que de laisser Flask deviner.
FLASK_APP="mon_application:create_app"

# Définit l'environnement d'exécution de l'application.
# Cela met automatiquement FLASK_DEBUG à True et active d'autres fonctionnalités.
# C'est la variable que notre code utilise pour choisir les BDD.
FLASK_ENV="development"