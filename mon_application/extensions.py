# mon_application/extensions.py
"""
Ce module initialise les extensions Flask partagées pour éviter les importations circulaires.

En instanciant les objets d'extension ici (comme SQLAlchemy), ils peuvent être importés
en toute sécurité dans d'autres modules (par exemple, les modèles dans models.py ou les
blueprints) sans créer de dépendance circulaire avec la factory de l'application
dans __init__.py.

L'initialisation réelle de ces extensions avec l'objet 'app' se fera
dans la factory create_app.
"""

from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy

# Crée une instance de SQLAlchemy. Elle n'est pas encore liée à une application.
db = SQLAlchemy()

# Crée une instance de Fla.
migrate = Migrate()
