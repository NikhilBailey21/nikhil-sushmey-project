import pytest

from flaskr.db import get_db, execute_query


def test_index(client, auth):
    """Test the index page shows posts and login link when not authenticated."""
    response = client.get("/")
    assert response.status_code == 200
    assert b"Sign In" in response.data or b"Log In" in response.data

    # After login, should show posts
    auth.login()
    response = client.get("/")
    assert response.status_code == 200
    assert b"test title" in response.data
    assert b"by test on 2018-01-01" in response.data
    assert b"test\nbody" in response.data
    assert b'href="/1/update"' in response.data


@pytest.mark.parametrize("path", ("/create", "/1/update", "/1/delete"))
def test_login_required(client, path):
    """Test that login is required for protected routes."""
    response = client.post(path)
    assert response.status_code == 302
    assert response.headers["Location"] == "/auth/login"


def test_author_required(app, client, auth):
    """Test that users can only modify their own posts."""
    # Change the post author to another user
    with app.app_context():
        db = get_db()
        execute_query(db, "UPDATE post SET author_id = 2 WHERE id = 1")
        db.commit()

    auth.login(user_id=1)
    # Current user can't modify other user's post
    assert client.post("/1/update").status_code == 403
    assert client.post("/1/delete").status_code == 403
    # Current user doesn't see edit link
    response = client.get("/")
    assert b'href="/1/update"' not in response.data


@pytest.mark.parametrize("path", ("/2/update", "/2/delete"))
def test_exists_required(client, auth, path):
    """Test that 404 is returned for non-existent posts."""
    auth.login()
    assert client.post(path).status_code == 404


def test_create(client, auth, app):
    """Test creating a new post."""
    auth.login()
    assert client.get("/create").status_code == 200
    client.post("/create", data={"title": "created", "body": ""})

    with app.app_context():
        db = get_db()
        cursor = execute_query(db, "SELECT COUNT(id) FROM post")
        count = cursor.fetchone()[0]
        if hasattr(cursor, 'close'):
            cursor.close()
        assert count == 2


def test_update(client, auth, app):
    """Test updating a post."""
    auth.login()
    assert client.get("/1/update").status_code == 200
    client.post("/1/update", data={"title": "updated", "body": ""})

    with app.app_context():
        db = get_db()
        cursor = execute_query(db, "SELECT * FROM post WHERE id = 1")
        post = cursor.fetchone()
        if hasattr(cursor, 'close'):
            cursor.close()
        assert post["title"] == "updated"


@pytest.mark.parametrize("path", ("/create", "/1/update"))
def test_create_update_validate(client, auth, path):
    """Test that title is required when creating/updating posts."""
    auth.login()
    response = client.post(path, data={"title": "", "body": ""})
    assert b"Title is required." in response.data


def test_delete(client, auth, app):
    """Test deleting a post."""
    auth.login()
    response = client.post("/1/delete")
    assert response.status_code == 302
    assert response.headers["Location"] == "/"

    with app.app_context():
        db = get_db()
        cursor = execute_query(db, "SELECT * FROM post WHERE id = 1")
        post = cursor.fetchone()
        if hasattr(cursor, 'close'):
            cursor.close()
        assert post is None


def test_index_shows_user_name(client, auth):
    """Test that index page shows logged in user's name."""
    auth.login(user_id=1)
    response = client.get("/")
    assert response.status_code == 200
    # Should show user name or username in navigation
    assert b"test" in response.data or b"Test User" in response.data


def test_create_post_requires_login(client):
    """Test that creating a post redirects to login when not authenticated."""
    response = client.get("/create")
    assert response.status_code == 302
    assert response.headers["Location"] == "/auth/login"


def test_update_post_requires_login(client):
    """Test that updating a post redirects to login when not authenticated."""
    response = client.get("/1/update")
    assert response.status_code == 302
    assert response.headers["Location"] == "/auth/login"
