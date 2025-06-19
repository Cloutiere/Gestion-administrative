# mon_application/extensions.py
"""
Ce module initialise les extensions Flask partagées pour éviter les importations circulaires.
...
"""

from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
migrate = Migrate()
