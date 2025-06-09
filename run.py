# run.py
"""
Point d'entrée pour l'exécution de l'application Flask.

Ce script importe la factory `create_app` depuis le paquet `mon_application`
et lance le serveur de développement Flask.
C'est le seul fichier à exécuter pour démarrer l'application.
"""

import os

from mon_application import create_app

# Crée l'instance de l'application en utilisant la factory.
app = create_app()

if __name__ == "__main__":
    # Récupère le port depuis les variables d'environnement, avec une valeur par défaut.
    port = int(os.environ.get("PORT", 8080))
    # Active le mode debug si la variable d'environnement FLASK_DEBUG est 'true'.
    debug_mode = os.environ.get("FLASK_DEBUG", "False").lower() == "true"
    # Lance l'application. 'host="0.0.0.0"' la rend accessible sur le réseau.
    app.run(host="0.0.0.0", port=port, debug=debug_mode)
