"""Settings, all read from the environment so nothing needs editing in code."""
import os


def _env(name, default):
    value = os.environ.get(name)
    return value if value not in (None, "") else default


DATA_DIR = _env("WHERE_DATA_DIR", "./data")
PHOTO_DIR = os.path.join(DATA_DIR, "photos")
DB_PATH = os.path.join(DATA_DIR, "where.db")

# Where the vision model lives and which one to ask for.
OLLAMA_HOST = _env("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
OLLAMA_MODEL = _env("OLLAMA_MODEL", "moondream")
# A small CPU can take a couple of minutes on one photo; be patient.
OLLAMA_TIMEOUT = int(_env("OLLAMA_TIMEOUT", "300"))

# Optional. The address the app is opened at, baked into QR labels.
# Empty means "use whatever address the browser is on right now".
PUBLIC_URL = _env("WHERE_PUBLIC_URL", "").rstrip("/")

PORT = int(_env("WHERE_PORT", "8080"))

# Longest edge of a stored photo and of its thumbnail, in pixels.
PHOTO_MAX = 1600
THUMB_MAX = 480
