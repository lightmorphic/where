"""Settings the app stores for itself, edited on the Settings page.

Kept in the database rather than in the environment so nobody has to touch
docker-compose.yml or restart a container to change the model.
"""
from . import db

DEFAULTS = {
    # Where Ollama is. The compose file starts one alongside the app under
    # this name; point it elsewhere to use a machine with more memory.
    "ollama_host": "http://ollama:11434",
    "ollama_model": "moondream",
    # A small model on a small processor can take a couple of minutes.
    "ollama_timeout": "300",
    # Baked into QR labels. Empty means "whatever address the browser is on",
    # which is right until you print a label from one address and scan it from
    # another.
    "public_url": "",
    # Whether anyone reaching the app can make themselves an account. The very
    # first account can always be made, otherwise nobody could get in.
    "allow_signup": "0",
}

INTS = {"ollama_timeout"}
BOOLS = {"allow_signup"}


def all(conn=None):
    if conn is None:
        with db.db() as c:
            return all(c)
    values = dict(DEFAULTS)
    for row in conn.execute("SELECT key, value FROM settings"):
        if row["key"] in DEFAULTS:
            values[row["key"]] = row["value"]
    return values


def get(key, conn=None):
    if conn is None:
        with db.db() as c:
            return get(key, c)
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else DEFAULTS[key]


def get_int(key, conn=None):
    try:
        return int(get(key, conn))
    except (TypeError, ValueError):
        return int(DEFAULTS[key])


def get_bool(key, conn=None):
    return get(key, conn) == "1"


def set_many(conn, values):
    for key, value in values.items():
        if key not in DEFAULTS:
            continue
        conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, str(value)),
        )
