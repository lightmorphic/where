import datetime
import logging
import os

from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix

from . import auth, config, db, vision


def version():
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    try:
        with open(os.path.join(here, "VERSION")) as f:
            return f.read().strip()
    except OSError:
        return "dev"


def _static_mtime():
    """Newest static file time, so a rebuilt image busts browser caches."""
    root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
    newest = 0
    for base, _dirs, files in os.walk(root):
        for f in files:
            newest = max(newest, os.path.getmtime(os.path.join(base, f)))
    return newest


def create_app(start_worker=True):
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    app = Flask(__name__, static_folder="static", template_folder="templates")
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
    app.config["MAX_CONTENT_LENGTH"] = 40 * 1024 * 1024
    app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 3600
    app.jinja_env.globals["app_version"] = version() + "-" + str(int(_static_mtime()))

    db.init()

    app.secret_key = auth.secret_key()
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    # Lax stops another site posting a form into this one on your behalf.
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.permanent_session_lifetime = datetime.timedelta(days=90)

    from .routes import bp
    app.register_blueprint(bp)
    app.before_request(auth.load_user)
    app.before_request(auth.require_login)

    if start_worker:
        vision.start()
    return app
