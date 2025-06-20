# .flaskenv
# Ce fichier définit les variables d'environnement pour le CLI de Flask.

# Indique explicitement où trouver la factory de l'application.
FLASK_APP="mon_application:create_app"

# --- NOUVELLE PRATIQUE : Activer le mode debug explicitement ---
# Mettre cette valeur à 1 active le mode debug, y compris le rechargement automatique.
# Mettre à 0 pour la production.
FLASK_DEBUG=1

# Nous gardons FLASK_ENV car notre logique de sélection de BDD l'utilise,
# mais c'est FLASK_DEBUG qui contrôle maintenant le comportement du serveur.
FLASK_ENV="development"