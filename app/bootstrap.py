"""Start-up chores that have to happen before the app runs.

In Docker the container is launched as root so that it can hand its data folder
to the unprivileged user, and then it drops to that user for good. That way
`docker compose up -d` works on a fresh host without anyone having to know that
a bind mount needs chowning first.
"""
import grp
import os
import pwd
import sys

APP_UID = 1000
APP_GID = 1000


def prepare(data_dir):
    """Returns a line to log, or None when there was nothing to do."""
    if os.geteuid() != 0:
        # Running as an ordinary user already: nothing to hand over, and the
        # readable "cannot write" check in db.init will catch a bad folder.
        return None

    os.makedirs(data_dir, exist_ok=True)
    note = None
    if owner_uid(data_dir) != APP_UID:
        _chown_tree(data_dir)
        note = f"handed {data_dir} to user {APP_UID}"
    drop_privileges()
    return note


def owner_uid(path):
    return os.stat(path).st_uid


def _chown_tree(path):
    os.chown(path, APP_UID, APP_GID)
    for base, dirs, files in os.walk(path):
        for name in dirs + files:
            try:
                os.chown(os.path.join(base, name), APP_UID, APP_GID, follow_symlinks=False)
            except OSError:
                pass


def drop_privileges():
    """Give up root permanently, before a single request is served."""
    try:
        name = pwd.getpwuid(APP_UID).pw_name
        groups = [g.gr_gid for g in grp.getgrall() if name in g.gr_mem]
    except KeyError:
        groups = []
    os.setgroups(sorted(set(groups + [APP_GID])))
    os.setgid(APP_GID)
    os.setuid(APP_UID)
    # If any of that silently failed we must not carry on with root's powers.
    if os.geteuid() != APP_UID or os.getegid() != APP_GID:
        raise SystemExit("Where could not give up root, so it has stopped.")
    os.environ.setdefault("HOME", "/tmp")
    try:
        os.setuid(0)
    except OSError:
        return  # good: root cannot be regained
    raise SystemExit("Where could not give up root for good, so it has stopped.")


def log_line(note):
    if note:
        print(f"where: {note}", file=sys.stderr, flush=True)
