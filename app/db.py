"""SQLite access. One file, a handful of tables, no ORM."""
import os
import sqlite3
import threading
from contextlib import contextmanager

from . import config

_lock = threading.Lock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT NOT NULL UNIQUE COLLATE NOCASE,
    password_hash TEXT NOT NULL,
    is_admin      INTEGER NOT NULL DEFAULT 0,
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS places (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS items (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    place_id    INTEGER NOT NULL REFERENCES places(id),
    name        TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    note        TEXT NOT NULL DEFAULT '',
    photo       TEXT,
    gone        INTEGER NOT NULL DEFAULT 0,
    -- none: no photo so nothing to describe. pending: waiting for the model.
    -- done: filled in (or edited by hand). failed: model unreachable or errored.
    desc_status TEXT NOT NULL DEFAULT 'none',
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS items_place ON items(place_id);

-- A tray photo waiting to be turned into a list of items.
CREATE TABLE IF NOT EXISTS bulk_jobs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    place_id    INTEGER NOT NULL REFERENCES places(id),
    photo       TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'pending',   -- pending / done / failed
    result      TEXT NOT NULL DEFAULT '',          -- one item name per line
    error       TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


def connect():
    conn = sqlite3.connect(config.DB_PATH, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def db():
    """One connection per unit of work, committed on success."""
    conn = connect()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init():
    check_data_dir()
    os.makedirs(config.PHOTO_DIR, exist_ok=True)
    with _lock, db() as conn:
        conn.executescript(SCHEMA)


def check_data_dir():
    """Fail with something a person can act on.

    In Docker the app runs as user 1000 and writes to a folder on the host. If
    that folder belongs to somebody else, every write fails, and the bare
    traceback does not say what to do about it.
    """
    path = os.path.abspath(config.DATA_DIR)
    try:
        os.makedirs(path, exist_ok=True)
    except OSError as exc:
        raise SystemExit(_cannot_write(path, exc))
    probe = os.path.join(path, ".write-test")
    try:
        with open(probe, "w") as f:
            f.write("")
        os.remove(probe)
    except OSError as exc:
        raise SystemExit(_cannot_write(path, exc))


def _cannot_write(path, exc):
    uid, gid = os.getuid(), os.getgid()
    try:
        st = os.stat(path)
        owner = f"user {st.st_uid}, group {st.st_gid}"
    except OSError:
        owner = "unknown"
    return (
        f"\n  Where cannot write to its data folder: {path}\n"
        f"  ({exc.strerror})\n\n"
        f"  The folder belongs to {owner}. Where runs as user {uid}, group {gid}.\n"
        f"  On the host, give it to that user and start the app again:\n\n"
        f"      sudo chown -R {uid}:{gid} <the folder you mounted at /data>\n\n"
        f"  For the usual setup that is:\n\n"
        f"      sudo chown -R {uid}:{gid} /opt/where/data\n"
    )


# ---- places ----

def list_places(conn):
    return conn.execute(
        """SELECT p.*,
                  (SELECT COUNT(*) FROM items i WHERE i.place_id = p.id AND i.gone = 0) AS item_count
           FROM places p ORDER BY p.name COLLATE NOCASE"""
    ).fetchall()


def get_place(conn, place_id):
    return conn.execute("SELECT * FROM places WHERE id = ?", (place_id,)).fetchone()


def create_place(conn, name):
    cur = conn.execute("INSERT INTO places (name) VALUES (?)", (name,))
    return cur.lastrowid


def rename_place(conn, place_id, name):
    conn.execute("UPDATE places SET name = ? WHERE id = ?", (name, place_id))


def delete_place(conn, place_id):
    conn.execute("DELETE FROM bulk_jobs WHERE place_id = ?", (place_id,))
    conn.execute("DELETE FROM places WHERE id = ?", (place_id,))


# ---- items ----

ITEM_SELECT = """SELECT i.*, p.name AS place_name
                 FROM items i JOIN places p ON p.id = i.place_id"""


def get_item(conn, item_id):
    return conn.execute(ITEM_SELECT + " WHERE i.id = ?", (item_id,)).fetchone()


def items_in_place(conn, place_id):
    return conn.execute(
        ITEM_SELECT + " WHERE i.place_id = ? ORDER BY i.gone, i.name COLLATE NOCASE",
        (place_id,),
    ).fetchall()


def search_items(conn, query, include_gone=False):
    words = [w for w in query.split() if w]
    if not words:
        return []
    clauses, params = [], []
    for w in words:
        like = f"%{w}%"
        clauses.append("(i.name LIKE ? OR i.description LIKE ? OR i.note LIKE ? OR p.name LIKE ?)")
        params += [like, like, like, like]
    where = " AND ".join(clauses)
    if not include_gone:
        where += " AND i.gone = 0"
    return conn.execute(
        ITEM_SELECT + f" WHERE {where} ORDER BY i.gone, i.name COLLATE NOCASE LIMIT 200",
        params,
    ).fetchall()


def create_item(conn, place_id, name, note="", photo=None, description="", desc_status=None):
    if desc_status is None:
        desc_status = "pending" if photo else "none"
    cur = conn.execute(
        """INSERT INTO items (place_id, name, note, photo, description, desc_status)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (place_id, name, note, photo, description, desc_status),
    )
    return cur.lastrowid


def update_item(conn, item_id, **fields):
    if not fields:
        return
    sets = ", ".join(f"{k} = ?" for k in fields)
    conn.execute(
        f"UPDATE items SET {sets}, updated_at = datetime('now') WHERE id = ?",
        (*fields.values(), item_id),
    )


def set_description(conn, item_id, text, status="done"):
    """Written by the model. Only lands while the item is still waiting, so a
    hand edit made in the meantime is never overwritten."""
    conn.execute(
        """UPDATE items SET description = ?, desc_status = ?, updated_at = datetime('now')
           WHERE id = ? AND desc_status = 'pending'""",
        (text, status, item_id),
    )


def delete_item(conn, item_id):
    conn.execute("DELETE FROM items WHERE id = ?", (item_id,))


def photo_in_use(conn, photo):
    row = conn.execute(
        "SELECT (SELECT COUNT(*) FROM items WHERE photo = ?) + (SELECT COUNT(*) FROM bulk_jobs WHERE photo = ?)",
        (photo, photo),
    ).fetchone()
    return row[0] > 0


def pending_item_ids(conn):
    return [r[0] for r in conn.execute("SELECT id FROM items WHERE desc_status = 'pending' AND photo IS NOT NULL")]


# ---- bulk jobs ----

def create_bulk_job(conn, place_id, photo):
    return conn.execute("INSERT INTO bulk_jobs (place_id, photo) VALUES (?, ?)", (place_id, photo)).lastrowid


def get_bulk_job(conn, job_id):
    return conn.execute("SELECT * FROM bulk_jobs WHERE id = ?", (job_id,)).fetchone()


def finish_bulk_job(conn, job_id, result="", error=""):
    conn.execute(
        "UPDATE bulk_jobs SET status = ?, result = ?, error = ? WHERE id = ?",
        ("failed" if error else "done", result, error, job_id),
    )


def delete_bulk_job(conn, job_id):
    conn.execute("DELETE FROM bulk_jobs WHERE id = ?", (job_id,))


def pending_bulk_job_ids(conn):
    return [r[0] for r in conn.execute("SELECT id FROM bulk_jobs WHERE status = 'pending'")]


# ---- users ----

def user_count(conn):
    return conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]


def list_users(conn):
    return conn.execute("SELECT * FROM users ORDER BY username COLLATE NOCASE").fetchall()


def get_user(conn, user_id):
    return conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()


def get_user_by_name(conn, username):
    return conn.execute("SELECT * FROM users WHERE username = ? COLLATE NOCASE", (username,)).fetchone()


def create_user(conn, username, password_hash, is_admin=False):
    cur = conn.execute(
        "INSERT INTO users (username, password_hash, is_admin) VALUES (?, ?, ?)",
        (username, password_hash, 1 if is_admin else 0),
    )
    return cur.lastrowid


def set_password(conn, user_id, password_hash):
    conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (password_hash, user_id))


def set_admin(conn, user_id, is_admin):
    conn.execute("UPDATE users SET is_admin = ? WHERE id = ?", (1 if is_admin else 0, user_id))


def delete_user(conn, user_id):
    conn.execute("DELETE FROM users WHERE id = ?", (user_id,))


def admin_count(conn):
    return conn.execute("SELECT COUNT(*) FROM users WHERE is_admin = 1").fetchone()[0]


def counts(conn):
    row = conn.execute(
        """SELECT (SELECT COUNT(*) FROM places),
                  (SELECT COUNT(*) FROM items WHERE gone = 0),
                  (SELECT COUNT(*) FROM items WHERE gone = 1)"""
    ).fetchone()
    return {"places": row[0], "items": row[1], "gone": row[2]}
