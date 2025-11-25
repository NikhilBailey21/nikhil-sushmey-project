import pytest

from flaskr.db import get_db


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


def test_init_db_command(runner, monkeypatch):
    class Recorder:
        called = False

    def fake_init_db():
        Recorder.called = True

    monkeypatch.setattr("flaskr.db.init_db", fake_init_db)
    result = runner.invoke(args=["init-db"])
    assert "Initialized" in result.output
    assert Recorder.called
