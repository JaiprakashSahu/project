"""
Single SQLAlchemy instance for the entire application.
This is the ONLY place where SQLAlchemy() is instantiated.
"""
from flask_sqlalchemy import SQLAlchemy

# ONE and ONLY ONE SQLAlchemy instance
db = SQLAlchemy()
