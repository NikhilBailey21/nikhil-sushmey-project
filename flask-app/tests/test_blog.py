import pytest


def test_index(client):
    """Test the index page shows hello world."""
    response = client.get("/")
    assert response.status_code == 200
    assert b"Hello, World!" in response.data
    assert b"Welcome to Flaskr!" in response.data


def test_index_shows_login_link_when_not_authenticated(client):
    """Test that index page shows login link when not authenticated."""
    response = client.get("/")
    assert response.status_code == 200
    assert b"Sign In" in response.data or b"Log In" in response.data


def test_index_shows_user_name_when_authenticated(client, auth):
    """Test that index page shows logged in user's name in navigation."""
    auth.login(user_id=1)
    response = client.get("/")
    assert response.status_code == 200
    # Should show user name or username in navigation
    assert b"test" in response.data or b"Test User" in response.data
    # Should still show hello world
    assert b"Hello, World!" in response.data
