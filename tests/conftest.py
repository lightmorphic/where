import os
import tempfile

import pytest


@pytest.fixture()
def app_client(monkeypatch):
    tmp = tempfile.mkdtemp()
    from app import config
    monkeypatch.setattr(config, "DATA_DIR", tmp)
    monkeypatch.setattr(config, "PHOTO_DIR", os.path.join(tmp, "photos"))
    monkeypatch.setattr(config, "DB_PATH", os.path.join(tmp, "where.db"))
    monkeypatch.setattr(config, "SECRET_PATH", os.path.join(tmp, "secret.key"))
    from app import create_app, db, settings
    app = create_app(start_worker=False)
    app.testing = True
    # Nothing listens on port 9, so the model always looks unreachable.
    with db.db() as conn:
        settings.set_many(conn, {"ollama_host": "http://127.0.0.1:9"})
    return app.test_client()


@pytest.fixture()
def anon(app_client):
    """A client with nobody signed in."""
    return app_client


@pytest.fixture()
def client(app_client):
    """A client signed in as the first account, which runs the place."""
    app_client.post("/signup", data={"username": "charlie", "password": "hunter2hunter2",
                                     "password2": "hunter2hunter2"})
    return app_client
