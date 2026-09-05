from app import db, settings, vision


def test_the_settings_page_shows_what_is_in_use(client):
    r = client.get("/settings")
    assert b"moondream" in r.data and b"http://127.0.0.1:9" in r.data


def test_the_shipped_default_points_at_the_bundled_ollama():
    assert settings.DEFAULTS["ollama_host"] == "http://ollama:11434"
    assert settings.DEFAULTS["ollama_model"] == "moondream"


def test_the_model_settings_reach_the_worker(client):
    client.post("/settings/descriptions", data={"ollama_host": "http://box:11434/",
                                                "ollama_model": "minicpm-v",
                                                "ollama_timeout": "600"})
    assert vision.host() == "http://box:11434"
    assert vision.model() == "minicpm-v"
    with db.db() as conn:
        assert settings.get_int("ollama_timeout", conn) == 600


def test_a_silly_timeout_is_brought_back_into_range(client):
    client.post("/settings/descriptions", data={"ollama_host": "http://ollama:11434",
                                                "ollama_model": "moondream",
                                                "ollama_timeout": "999999"})
    with db.db() as conn:
        assert settings.get_int("ollama_timeout", conn) == 3600


def test_the_label_address_is_used_in_qr_codes(client):
    from app.routes import _place_url
    app = client.application
    client.post("/places", data={"name": "Tray 14"})

    # Empty means "whatever address you printed from".
    with app.test_request_context("/labels", base_url="http://box.local:4150"):
        assert _place_url(1) == "http://box.local:4150/places/1"

    # A bare host is assumed to be https, and the label uses it from anywhere.
    client.post("/settings/labels", data={"public_url": "home.example:4150/"})
    with app.test_request_context("/labels", base_url="http://box.local:4150"):
        assert _place_url(1) == "https://home.example:4150/places/1"

    # The page still renders, and the code is a drawing rather than text.
    assert client.get("/labels?all=1").status_code == 200


def test_settings_survive_a_restart(client):
    client.post("/settings/labels", data={"public_url": "https://home.example"})
    with db.db() as conn:
        assert settings.all(conn)["public_url"] == "https://home.example"


def test_nothing_is_read_from_the_environment(client, monkeypatch):
    """The compose file carries no configuration, so stray variables are ignored."""
    monkeypatch.setenv("OLLAMA_MODEL", "something-else")
    monkeypatch.setenv("OLLAMA_HOST", "http://elsewhere:1")
    assert vision.model() == "moondream"
    assert vision.host() == "http://127.0.0.1:9"


def test_a_data_folder_it_cannot_write_to_says_what_to_do(tmp_path, monkeypatch, capsys):
    """A root-owned bind mount is the commonest first-run failure in Docker."""
    import pytest
    from app import config, db
    locked = tmp_path / "locked"
    locked.mkdir()
    locked.chmod(0o555)
    monkeypatch.setattr(config, "DATA_DIR", str(locked))
    monkeypatch.setattr(config, "PHOTO_DIR", str(locked / "photos"))
    monkeypatch.setattr(config, "DB_PATH", str(locked / "where.db"))
    with pytest.raises(SystemExit) as raised:
        db.init()
    message = str(raised.value)
    assert "cannot write to its data folder" in message
    assert "chown" in message
    locked.chmod(0o755)
