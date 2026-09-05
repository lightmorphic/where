import os

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


def test_an_ordinary_user_is_left_alone(tmp_path):
    """Outside Docker the app is not root, so start-up must change nothing."""
    from app import bootstrap
    folder = tmp_path / "data"
    assert bootstrap.prepare(str(folder)) is None
    assert not folder.exists()


def test_the_handover_is_skipped_when_the_folder_is_already_right(tmp_path, monkeypatch):
    from app import bootstrap
    folder = tmp_path / "data"
    folder.mkdir()
    exists_before = folder.exists()
    dropped = []
    monkeypatch.setattr(bootstrap.os, "geteuid", lambda: 0)
    monkeypatch.setattr(bootstrap, "owner_uid", lambda p: 1000)
    monkeypatch.setattr(bootstrap, "_chown_tree", lambda p: dropped.append("chown"))
    monkeypatch.setattr(bootstrap, "drop_privileges", lambda: dropped.append("drop"))
    assert bootstrap.prepare(str(folder)) is None
    assert dropped == ["drop"] and exists_before


def test_a_root_owned_folder_is_handed_over_then_root_is_given_up(tmp_path, monkeypatch):
    from app import bootstrap
    folder = tmp_path / "data"
    done = []
    monkeypatch.setattr(bootstrap.os, "geteuid", lambda: 0)
    monkeypatch.setattr(bootstrap, "owner_uid", lambda p: 0)
    monkeypatch.setattr(bootstrap, "_chown_tree", lambda p: done.append("chown"))
    monkeypatch.setattr(bootstrap, "drop_privileges", lambda: done.append("drop"))
    note = bootstrap.prepare(str(folder))
    assert done == ["chown", "drop"]
    assert "user 1000" in note
    assert os.path.isdir(folder)
