import logging
import os

from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix

from . import config, db, vision


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
    from .routes import bp
    app.register_blueprint(bp)

    if start_worker:
        vision.start()
    return app
