# run.py
"""
Point d'entrée pour l'exécution de l'application Flask.

Ce script importe la factory `create_app` depuis le paquet `mon_application`
et lance le serveur de développement intégré de Flask. C'est le fichier
principal à exécuter pour démarrer l'application.
"""

import os

from mon_application import create_app

# Crée une instance de l'application en appelant la factory.
app = create_app()

if __name__ == "__main__":
    # Récupère le port depuis les variables d'environnement.
    # Replit définit automatiquement la variable PORT. La valeur par défaut 8080 est un fallback.
    port = int(os.environ.get("PORT", 8080))

    # Détermine si le mode debug doit être activé, en se basant sur la variable d'environnement FLASK_DEBUG.
    # Cette configuration est plus sûre pour la production où la variable ne devrait pas être définie sur "true".
    debug_mode = os.environ.get("FLASK_DEBUG", "False").lower() == "true"

    # Lance l'application.
    # host="0.0.0.0" rend l'application accessible depuis l'extérieur du conteneur (nécessaire sur Replit).
    app.run(host="0.0.0.0", port=port, debug=debug_mode)
