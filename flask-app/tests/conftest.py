import os
import sys

import pytest

# Add repo root to Python path to allow importing shared modules
_repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

try:
    from dotenv import load_dotenv
    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    load_dotenv(env_path)
except ImportError as error:
    raise RuntimeError(f"Error loading .env file: {error}")

from flaskr import create_app
from shared.db import get_db

# read in SQL for populating test data
with open(os.path.join(os.path.dirname(__file__), "data.sql"), "rb") as f:
    _data_sql = f.read().decode("utf8")


@pytest.fixture
def app():
    """Create and configure a new app instance for each test."""
    # Use CloudSQL connection from .env file
    # Check for CloudSQL connection variables
    cloud_sql_connection_name = os.environ.get("CLOUD_SQL_CONNECTION_NAME")
    db_user = os.environ.get("DB_USER")
    db_pass = os.environ.get("DB_PASS")
    db_name = os.environ.get("DB_NAME")
    
    if not cloud_sql_connection_name:
        pytest.skip("CLOUD_SQL_CONNECTION_NAME must be set in .env for tests")
    
    if not db_user or not db_pass or not db_name:
        pytest.skip("DB_USER, DB_PASS, and DB_NAME must be set in .env for tests")
    
    app = create_app({"TESTING": True})

    # Load test data into existing database tables
    with app.app_context():
        db = get_db()
        cursor = db.cursor()
        # Execute each statement from data.sql
        statements = [s.strip() for s in _data_sql.split(';') if s.strip() and not s.strip().startswith('--')]
        for statement in statements:
            if statement:
                cursor.execute(statement)
        db.commit()
        cursor.close()

    yield app

    # Clean up test data after tests
    with app.app_context():
        db = get_db()
        cursor = db.cursor()
        cursor.execute('DELETE FROM "users"')
        db.commit()
        cursor.close()


@pytest.fixture
def client(app):
    """A test client for the app."""
    return app.test_client()


@pytest.fixture
def runner(app):
    """A test runner for the app's Click commands."""
    return app.test_cli_runner()


class AuthActions:
    def __init__(self, client):
        self._client = client

    def login(self, user_id=1):
        """Login by setting the session directly (since we use Google OAuth now)."""
        with self._client.session_transaction() as sess:
            sess['user_id'] = user_id
        return self._client.get("/")  # Return a response to match old API

    def logout(self):
        return self._client.get("/auth/logout")


@pytest.fixture
def auth(client):
    return AuthActions(client)
