import pytest


def test_index(client):
    """Test the index page shows hello world."""
    response = client.get("/")
    assert response.status_code == 200
    assert b"Welcome to Credit Card!" in response.data


def test_index_shows_login_link_when_not_authenticated(client):
    """Test that index page shows login link when not authenticated."""
    response = client.get("/")
    assert response.status_code == 200
    assert b"Sign In" in response.data or b"Log In" in response.data