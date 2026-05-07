"""
This file serves as an aggregation point for all SQLAlchemy models across the application.
Alembic uses this file to detect schema changes when generating migrations.

Import every model from each of your application's 'models.py' files here.
"""

# Import the base model definition if you have one, e.g., from sqlmodel or a custom base.

from src.auth.models import *  # noqa: F403

