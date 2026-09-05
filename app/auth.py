"""Accounts. Everyone signed in shares one list of places and items: two
people in the same house need to find the same cable."""
import functools
import os
import secrets

from flask import g, redirect, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from . import config, db

MIN_PASSWORD = 8

# Pages anyone can reach without signing in.
PUBLIC_ENDPOINTS = {"main.login", "main.signup", "main.health", "main.manifest",
                    "main.service_worker", "static"}


def secret_key():
    """A key kept beside the database, so sign-ins survive a restart."""
    try:
        with open(config.SECRET_PATH) as f:
            key = f.read().strip()
        if key:
            return key
    except OSError:
        pass
    key = secrets.token_hex(32)
    old = os.umask(0o077)
    try:
        with open(config.SECRET_PATH, "w") as f:
            f.write(key)
    finally:
        os.umask(old)
    return key


def hash_password(password):
    return generate_password_hash(password)


def check_password(user, password):
    return check_password_hash(user["password_hash"], password)


def password_problem(password, again=None):
    if len(password or "") < MIN_PASSWORD:
        return f"Use at least {MIN_PASSWORD} characters."
    if again is not None and password != again:
        return "The two passwords are not the same."
    return None


def username_problem(name):
    if not name:
        return "Choose a name to sign in with."
    if len(name) > 40:
        return "That name is too long."
    if not all(c.isalnum() or c in "-_. " for c in name):
        return "Use letters, numbers, spaces, dots, dashes or underscores."
    return None


def sign_in(user):
    session.clear()
    session["user_id"] = user["id"]
    session.permanent = True


def sign_out():
    session.clear()


def load_user():
    """Runs before every request, so templates can name who is signed in."""
    g.user = None
    user_id = session.get("user_id")
    if user_id is None:
        return
    with db.db() as conn:
        g.user = db.get_user(conn, user_id)
    if g.user is None:
        session.clear()


def require_login():
    if g.get("user") is not None:
        return None
    endpoint = request.endpoint or ""
    if endpoint in PUBLIC_ENDPOINTS:
        return None
    with db.db() as conn:
        first_run = db.user_count(conn) == 0
    if first_run:
        return redirect(url_for("main.signup"))
    return redirect(url_for("main.login", next=request.full_path.rstrip("?")))


def admin_only(view):
    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        if not g.get("user") or not g.user["is_admin"]:
            return redirect(url_for("main.settings_page"))
        return view(*args, **kwargs)
    return wrapped


def safe_next(target):
    """Only ever redirect inside this app, never to another site."""
    if target and target.startswith("/") and not target.startswith("//"):
        return target
    return url_for("main.index")
