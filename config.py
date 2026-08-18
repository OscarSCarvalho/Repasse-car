import os
from pathlib import Path

BASE_DIR = Path(__file__).parent


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-insecure')
    DATABASE = str(BASE_DIR / 'database' / 'repasse.db')
    UPLOAD_FOLDER = str(BASE_DIR / 'static' / 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    TESTING = False


class TestConfig(Config):
    TESTING = True
    SECRET_KEY = 'test-secret'
    DATABASE = None  # sobrescrito por tmp_path em conftest
