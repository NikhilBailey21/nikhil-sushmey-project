import pytest

from shared.db import get_db


def test_get_close_db(app):
    with app.app_context():
        db = get_db()
        assert db is get_db()

    # After context, connection should be closed
    # PostgreSQL connections raise different errors when closed
    with pytest.raises(Exception) as e:
        cursor = db.cursor()
        cursor.execute("SELECT 1")
        cursor.close()

    # Check that it's a connection-related error
    assert "closed" in str(e.value).lower() or "connection" in str(e.value).lower()
