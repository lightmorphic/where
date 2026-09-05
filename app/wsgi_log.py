"""One line per request in the container log.

Without this there is no way to tell "the app is broken" apart from "nothing
ever reached the app", which is the difference between a bug and a network
problem.
"""
import logging
import time

log = logging.getLogger("where.access")

# Pictures and the stylesheet would drown out everything worth reading.
QUIET_PREFIXES = ("/static/", "/photos/")


class AccessLog:
    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        started = time.monotonic()
        status_holder = {}

        def capture(status, headers, exc_info=None):
            status_holder["status"] = status.split(" ", 1)[0]
            return start_response(status, headers, exc_info)

        try:
            return self.app(environ, capture)
        finally:
            path = environ.get("PATH_INFO", "")
            if not path.startswith(QUIET_PREFIXES):
                query = environ.get("QUERY_STRING", "")
                log.info(
                    "%s %s%s %s %.0fms",
                    environ.get("REQUEST_METHOD", "?"),
                    path,
                    "?" + query if query else "",
                    status_holder.get("status", "?"),
                    (time.monotonic() - started) * 1000,
                )
