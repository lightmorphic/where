"""Paths, and the two things that cannot live in the database.

Everything a person might reasonably want to change is on the Settings page
inside the app, so the compose file carries no configuration at all.
"""
import os


def _env(name, default):
    value = os.environ.get(name)
    return value if value not in (None, "") else default


# Where the database, the photos and the session key live. Set by the
# Dockerfile; the bind mount in compose decides where that lands on the host.
DATA_DIR = _env("WHERE_DATA_DIR", "./data")
PHOTO_DIR = os.path.join(DATA_DIR, "photos")
DB_PATH = os.path.join(DATA_DIR, "where.db")
SECRET_PATH = os.path.join(DATA_DIR, "secret.key")

# The port inside the container. Docker maps a host port onto this one, so it
# is not something the Settings page could usefully change.
PORT = int(_env("WHERE_PORT", "8080"))

# Longest edge of a stored photo and of its thumbnail, in pixels.
PHOTO_MAX = 1600
THUMB_MAX = 480
