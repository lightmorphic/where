import os
import tempfile

import pytest


@pytest.fixture()
def client(monkeypatch):
    tmp = tempfile.mkdtemp()
    from app import config
    monkeypatch.setattr(config, "DATA_DIR", tmp)
    monkeypatch.setattr(config, "PHOTO_DIR", os.path.join(tmp, "photos"))
    monkeypatch.setattr(config, "DB_PATH", os.path.join(tmp, "where.db"))
    monkeypatch.setattr(config, "OLLAMA_HOST", "http://127.0.0.1:9")  # nothing listens here
    from app import create_app
    app = create_app(start_worker=False)
    app.testing = True
    return app.test_client()
