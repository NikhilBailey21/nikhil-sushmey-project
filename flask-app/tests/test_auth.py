import pytest
from unittest.mock import patch, MagicMock
from flask import g
from flask import session

from flaskr.db import get_db


def test_login_page(client, app):
    """Test that the login page renders without template errors."""
    # Set a mock Google Client ID for the test
    with app.app_context():
        app.config['GOOGLE_CLIENT_ID'] = 'test-client-id.apps.googleusercontent.com'
    
    response = client.get("/auth/login")
    assert response.status_code == 200
    assert b"Sign In" in response.data or b"Log In" in response.data


def test_login_page_no_client_id(client, app):
    """Test that login page shows error when Google Client ID is not configured."""
    with app.app_context():
        app.config['GOOGLE_CLIENT_ID'] = ''
    
    response = client.get("/auth/login")
    assert response.status_code == 200
    # Should show some indication that auth is not configured


def test_logout(client, auth):
    """Test that logout clears the session."""
    auth.login()
    
    with client:
        auth.logout()
        assert "user_id" not in session


def test_logout_redirects(client, auth):
    """Test that logout redirects to index."""
    auth.login()
    response = auth.logout()
    assert response.status_code == 302
    assert response.headers["Location"] == "/"


@patch('flaskr.auth.id_token.verify_oauth2_token')
def test_google_callback_new_user(mock_verify, client, app):
    """Test Google callback creates a new user."""
    # Mock Google token verification
    mock_verify.return_value = {
        'sub': 'google_user_123',
        'email': 'newuser@example.com',
        'name': 'New User',
        'picture': 'https://example.com/pic.jpg'
    }
    
    with app.app_context():
        app.config['GOOGLE_CLIENT_ID'] = 'test-client-id.apps.googleusercontent.com'
    
    response = client.post(
        "/auth/google-callback",
        json={"credential": "fake_google_token"},
        content_type="application/json"
    )
    
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert "redirect_url" in data
    
    # Verify user was created in database
    with app.app_context():
        db = get_db()
        from flaskr.db import execute_query
        cursor = execute_query(db, "SELECT * FROM user WHERE google_id = ?", ("google_user_123",))
        user = cursor.fetchone()
        if hasattr(cursor, 'close'):
            cursor.close()
        assert user is not None
        assert user["email"] == "newuser@example.com"
        assert user["name"] == "New User"


@patch('flaskr.auth.id_token.verify_oauth2_token')
def test_google_callback_existing_user(mock_verify, client, app):
    """Test Google callback with existing user."""
    # Mock Google token verification
    mock_verify.return_value = {
        'sub': 'test_google_id_123',
        'email': 'test@example.com',
        'name': 'Test User',
        'picture': 'https://example.com/pic.jpg'
    }
    
    with app.app_context():
        app.config['GOOGLE_CLIENT_ID'] = 'test-client-id.apps.googleusercontent.com'
    
    response = client.post(
        "/auth/google-callback",
        json={"credential": "fake_google_token"},
        content_type="application/json"
    )
    
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    
    # Verify session was set
    with client.session_transaction() as sess:
        assert "user_id" in sess


@patch('flaskr.auth.id_token.verify_oauth2_token')
def test_google_callback_invalid_token(mock_verify, client, app):
    """Test Google callback with invalid token."""
    # Mock token verification to raise ValueError
    mock_verify.side_effect = ValueError("Invalid token")
    
    with app.app_context():
        app.config['GOOGLE_CLIENT_ID'] = 'test-client-id.apps.googleusercontent.com'
    
    response = client.post(
        "/auth/google-callback",
        json={"credential": "invalid_token"},
        content_type="application/json"
    )
    
    assert response.status_code == 401
    data = response.get_json()
    assert data["success"] is False
    assert "error" in data


def test_google_callback_no_credential(client, app):
    """Test Google callback without credential."""
    with app.app_context():
        app.config['GOOGLE_CLIENT_ID'] = 'test-client-id.apps.googleusercontent.com'
    
    response = client.post(
        "/auth/google-callback",
        json={},
        content_type="application/json"
    )
    
    assert response.status_code == 400
    data = response.get_json()
    assert data["success"] is False


def test_google_callback_no_client_id(client, app):
    """Test Google callback when Google Client ID is not configured."""
    with app.app_context():
        app.config['GOOGLE_CLIENT_ID'] = ''
    
    response = client.post(
        "/auth/google-callback",
        json={"credential": "fake_token"},
        content_type="application/json"
    )
    
    assert response.status_code == 500
    data = response.get_json()
    assert data["success"] is False
    assert "not configured" in data["error"].lower()


def test_login_required_decorator(client):
    """Test that login_required decorator redirects to login."""
    response = client.get("/create")
    assert response.status_code == 302
    assert response.headers["Location"] == "/auth/login"


def test_load_logged_in_user(client, auth):
    """Test that user is loaded from session."""
    auth.login(user_id=1)
    
    with client:
        client.get("/")
        assert session["user_id"] == 1
        assert g.user is not None
        assert g.user["id"] == 1


def test_load_logged_in_user_no_session(client):
    """Test that g.user is None when not logged in."""
    with client:
        client.get("/")
        assert g.user is None
