import pytest


def test_index(client):
    """Test the landing page shows transaction analyzer."""
    response = client.get("/")
    assert response.status_code == 200
    assert b"Transaction Analyzer" in response.data


def test_index_shows_login_link_when_not_authenticated(client):
    """Test that landing page shows login link when not authenticated."""
    response = client.get("/")
    assert response.status_code == 200
    assert b"Sign In" in response.data or b"Log In" in response.data


def test_analyzer_requires_login(client):
    """Test that analyzer page requires authentication."""
    response = client.get("/analyzer/")
    assert response.status_code == 302  # Redirect to login
    assert b"login" in response.url.lower() or response.location.endswith("/auth/login")