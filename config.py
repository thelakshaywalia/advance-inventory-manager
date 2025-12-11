# --- config.py ---

import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class Config:
    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(BASE_DIR, 'database.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = 'a_very_secret_and_complex_key_for_offline_pos' 
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')