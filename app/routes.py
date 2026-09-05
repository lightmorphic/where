import os

from flask import (Blueprint, abort, g, jsonify, redirect, render_template, request,
                   send_from_directory, url_for)

from . import auth, config, db, photos, qr, settings, vision

bp = Blueprint("main", __name__)


@bp.app_context_processor
def _template_globals():
    return {"user": g.get("user")}


def _base_url():
    return settings.get("public_url").rstrip("/") or request.url_root.rstrip("/")


def _place_url(place_id):
    return f"{_base_url()}/places/{place_id}"


def _clean(value, limit=200):
    return " ".join((value or "").split())[:limit]


# ---- accounts ----

@bp.route("/signup", methods=["GET", "POST"])
def signup():
    with db.db() as conn:
        first_run = db.user_count(conn) == 0
        open_to_all = settings.get_bool("allow_signup", conn)
    if not first_run and not open_to_all:
        if g.get("user"):
            return redirect(url_for("main.settings_page"))
        return render_template("signup.html", closed=True, first_run=False), 403

    error = None
    username = ""
    if request.method == "POST":
        username = _clean(request.form.get("username"), 40)
        password = request.form.get("password") or ""
        again = request.form.get("password2") or ""
        error = auth.username_problem(username) or auth.password_problem(password, again)
        if error is None:
            with db.db() as conn:
                if db.get_user_by_name(conn, username):
                    error = "That name is taken."
                else:
                    user_id = db.create_user(conn, username, auth.hash_password(password),
                                             is_admin=first_run)
                    user = db.get_user(conn, user_id)
            if error is None:
                auth.sign_in(user)
                return redirect(url_for("main.index"))

    return render_template("signup.html", error=error, username=username,
                           first_run=first_run, closed=False)


@bp.route("/login", methods=["GET", "POST"])
def login():
    with db.db() as conn:
        if db.user_count(conn) == 0:
            return redirect(url_for("main.signup"))
        open_to_all = settings.get_bool("allow_signup", conn)
    error = None
    username = ""
    if request.method == "POST":
        username = _clean(request.form.get("username"), 40)
        password = request.form.get("password") or ""
        with db.db() as conn:
            user = db.get_user_by_name(conn, username)
        if user and auth.check_password(user, password):
            auth.sign_in(user)
            return redirect(auth.safe_next(request.form.get("next")))
        error = "That name and password do not match."
    return render_template("login.html", error=error, username=username,
                           open_to_all=open_to_all, next=request.args.get("next", ""))


@bp.route("/logout", methods=["POST"])
def logout():
    auth.sign_out()
    return redirect(url_for("main.login"))


# ---- settings ----

@bp.route("/settings")
def settings_page():
    with db.db() as conn:
        values = settings.all(conn)
        users = db.list_users(conn)
    return render_template("settings.html", values=values, users=users,
                           model=vision.status(), saved=request.args.get("saved"))


@bp.route("/settings/descriptions", methods=["POST"])
@auth.admin_only
def settings_descriptions():
    with db.db() as conn:
        settings.set_many(conn, {
            "ollama_host": _clean(request.form.get("ollama_host"), 200) or settings.DEFAULTS["ollama_host"],
            "ollama_model": _clean(request.form.get("ollama_model"), 80) or settings.DEFAULTS["ollama_model"],
            "ollama_timeout": max(10, min(3600, request.form.get("ollama_timeout", type=int) or 300)),
        })
    vision.forget_status()
    return redirect(url_for("main.settings_page", saved="descriptions") + "#descriptions")


@bp.route("/settings/labels", methods=["POST"])
@auth.admin_only
def settings_labels():
    url = _clean(request.form.get("public_url"), 200).rstrip("/")
    if url and not url.startswith(("http://", "https://")):
        url = "https://" + url
    with db.db() as conn:
        settings.set_many(conn, {"public_url": url})
    return redirect(url_for("main.settings_page", saved="labels") + "#labels")


@bp.route("/settings/signup", methods=["POST"])
@auth.admin_only
def settings_signup():
    allow = "1" if request.form.get("allow_signup") or (request.json or {}).get("allow_signup") else "0"
    with db.db() as conn:
        settings.set_many(conn, {"allow_signup": allow})
    if request.is_json:
        return jsonify(ok=True, allow_signup=allow == "1")
    return redirect(url_for("main.settings_page", saved="accounts") + "#accounts")


@bp.route("/settings/password", methods=["POST"])
def settings_password():
    current = request.form.get("current") or ""
    password = request.form.get("password") or ""
    again = request.form.get("password2") or ""
    if not auth.check_password(g.user, current):
        return redirect(url_for("main.settings_page", saved="password-wrong") + "#password")
    if auth.password_problem(password, again):
        return redirect(url_for("main.settings_page", saved="password-bad") + "#password")
    with db.db() as conn:
        db.set_password(conn, g.user["id"], auth.hash_password(password))
    return redirect(url_for("main.settings_page", saved="password") + "#password")


@bp.route("/settings/users", methods=["POST"])
@auth.admin_only
def settings_add_user():
    username = _clean(request.form.get("username"), 40)
    password = request.form.get("password") or ""
    problem = auth.username_problem(username) or auth.password_problem(password)
    if problem is None:
        with db.db() as conn:
            if db.get_user_by_name(conn, username):
                problem = "taken"
            else:
                db.create_user(conn, username, auth.hash_password(password),
                               is_admin=bool(request.form.get("is_admin")))
    return redirect(url_for("main.settings_page",
                            saved="user-added" if problem is None else "user-failed") + "#accounts")


@bp.route("/settings/users/<int:user_id>/delete", methods=["POST"])
@auth.admin_only
def settings_delete_user(user_id):
    with db.db() as conn:
        user = db.get_user(conn, user_id) or abort(404)
        # Never leave the app with nobody who can administer it.
        if user["is_admin"] and db.admin_count(conn) <= 1:
            return redirect(url_for("main.settings_page", saved="last-admin") + "#accounts")
        db.delete_user(conn, user_id)
    return redirect(url_for("main.settings_page", saved="user-removed") + "#accounts")


# ---- home, search ----

@bp.route("/")
def index():
    with db.db() as conn:
        places = db.list_places(conn)
        totals = db.counts(conn)
    return render_template("index.html", places=places, totals=totals, model=vision.status())


@bp.route("/search")
def search():
    q = _clean(request.args.get("q", ""), 100)
    include_gone = request.args.get("gone") == "1"
    with db.db() as conn:
        results = db.search_items(conn, q, include_gone) if q else []
    return render_template("search.html", q=q, results=results, include_gone=include_gone)


# ---- places ----

@bp.route("/places", methods=["POST"])
def place_create():
    name = _clean(request.form.get("name"), 60)
    if not name:
        return redirect(url_for("main.index"))
    with db.db() as conn:
        existing = conn.execute("SELECT id FROM places WHERE name = ? COLLATE NOCASE", (name,)).fetchone()
        place_id = existing["id"] if existing else db.create_place(conn, name)
    nxt = request.form.get("next")
    if nxt == "item":
        return redirect(url_for("main.item_new", place=place_id))
    return redirect(url_for("main.place", place_id=place_id))


@bp.route("/places/<int:place_id>")
def place(place_id):
    with db.db() as conn:
        place = db.get_place(conn, place_id) or abort(404)
        items = db.items_in_place(conn, place_id)
    live = [i for i in items if not i["gone"]]
    gone = [i for i in items if i["gone"]]
    return render_template("place.html", place=place, items=live, gone=gone)


@bp.route("/places/<int:place_id>/rename", methods=["POST"])
def place_rename(place_id):
    name = _clean(request.form.get("name"), 60)
    with db.db() as conn:
        db.get_place(conn, place_id) or abort(404)
        if name:
            db.rename_place(conn, place_id, name)
    return redirect(url_for("main.place", place_id=place_id))


@bp.route("/places/<int:place_id>/delete", methods=["POST"])
def place_delete(place_id):
    with db.db() as conn:
        db.get_place(conn, place_id) or abort(404)
        if conn.execute("SELECT COUNT(*) FROM items WHERE place_id = ?", (place_id,)).fetchone()[0]:
            return redirect(url_for("main.place", place_id=place_id))
        job_photos = [j["photo"] for j in conn.execute("SELECT photo FROM bulk_jobs WHERE place_id = ?", (place_id,))]
        db.delete_place(conn, place_id)
        for name in job_photos:
            if not db.photo_in_use(conn, name):
                photos.remove(name)
    return redirect(url_for("main.index"))


# ---- items ----

@bp.route("/items/new")
def item_new():
    with db.db() as conn:
        places = db.list_places(conn)
        saved = db.get_item(conn, request.args.get("saved", type=int)) if request.args.get("saved") else None
    selected = request.args.get("place", type=int)
    return render_template("item_form.html", places=places, selected=selected, saved=saved)


@bp.route("/items", methods=["POST"])
def item_create():
    name = _clean(request.form.get("name"), 120)
    place_id = request.form.get("place_id", type=int)
    note = _clean(request.form.get("note"), 500)
    if not name or not place_id:
        return redirect(url_for("main.item_new", place=place_id))
    photo = photos.save_upload(request.files.get("photo"))
    with db.db() as conn:
        db.get_place(conn, place_id) or abort(404)
        item_id = db.create_item(conn, place_id, name, note=note, photo=photo)
    if photo:
        vision.enqueue_describe(item_id)
    return redirect(url_for("main.item_new", place=place_id, saved=item_id))


@bp.route("/items/<int:item_id>")
def item(item_id):
    with db.db() as conn:
        item = db.get_item(conn, item_id) or abort(404)
        places = db.list_places(conn)
    return render_template("item.html", item=item, places=places, model=vision.status())


@bp.route("/items/<int:item_id>/edit", methods=["POST"])
def item_edit(item_id):
    with db.db() as conn:
        item = db.get_item(conn, item_id) or abort(404)
        fields = {
            "name": _clean(request.form.get("name"), 120) or item["name"],
            "description": _clean(request.form.get("description"), 400),
            "note": _clean(request.form.get("note"), 500),
        }
        place_id = request.form.get("place_id", type=int)
        if place_id and db.get_place(conn, place_id):
            fields["place_id"] = place_id
        # A hand edit while the model is still thinking wins over the model.
        if fields["description"] != item["description"] and item["desc_status"] == "pending":
            fields["desc_status"] = "done"
        new_photo = photos.save_upload(request.files.get("photo"))
        if new_photo:
            fields["photo"] = new_photo
            if not fields["description"]:
                fields["desc_status"] = "pending"
        db.update_item(conn, item_id, **fields)
        old_photo = item["photo"]
        if new_photo and old_photo and not db.photo_in_use(conn, old_photo):
            photos.remove(old_photo)
    if new_photo and fields.get("desc_status") == "pending":
        vision.enqueue_describe(item_id)
    return redirect(url_for("main.item", item_id=item_id))


@bp.route("/items/<int:item_id>/gone", methods=["POST"])
def item_gone(item_id):
    gone = 1 if (request.form.get("gone") or (request.json or {}).get("gone")) in (1, "1", True, "true") else 0
    with db.db() as conn:
        db.get_item(conn, item_id) or abort(404)
        db.update_item(conn, item_id, gone=gone)
    if request.is_json:
        return jsonify(ok=True, gone=gone)
    return redirect(url_for("main.item", item_id=item_id))


@bp.route("/items/<int:item_id>/describe", methods=["POST"])
def item_describe(item_id):
    with db.db() as conn:
        item = db.get_item(conn, item_id) or abort(404)
        if item["photo"]:
            db.update_item(conn, item_id, desc_status="pending")
    if item["photo"]:
        vision.enqueue_describe(item_id)
    return redirect(url_for("main.item", item_id=item_id))


@bp.route("/items/<int:item_id>/delete", methods=["POST"])
def item_delete(item_id):
    with db.db() as conn:
        item = db.get_item(conn, item_id) or abort(404)
        db.delete_item(conn, item_id)
        if item["photo"] and not db.photo_in_use(conn, item["photo"]):
            photos.remove(item["photo"])
    return redirect(url_for("main.place", place_id=item["place_id"]))


@bp.route("/api/items/<int:item_id>")
def item_json(item_id):
    with db.db() as conn:
        item = db.get_item(conn, item_id) or abort(404)
    return jsonify(id=item["id"], description=item["description"], desc_status=item["desc_status"])


# ---- bulk add from one photo ----

@bp.route("/bulk")
def bulk():
    with db.db() as conn:
        places = db.list_places(conn)
    return render_template("bulk.html", places=places, selected=request.args.get("place", type=int))


@bp.route("/bulk", methods=["POST"])
def bulk_start():
    place_id = request.form.get("place_id", type=int)
    photo = photos.save_upload(request.files.get("photo"))
    if not place_id or not photo:
        return redirect(url_for("main.bulk", place=place_id))
    with db.db() as conn:
        db.get_place(conn, place_id) or abort(404)
        job_id = db.create_bulk_job(conn, place_id, photo)
    vision.enqueue_bulk(job_id)
    return redirect(url_for("main.bulk_review", job_id=job_id))


@bp.route("/bulk/<int:job_id>")
def bulk_review(job_id):
    with db.db() as conn:
        job = db.get_bulk_job(conn, job_id) or abort(404)
        place = db.get_place(conn, job["place_id"])
    names = [n for n in job["result"].splitlines() if n.strip()]
    return render_template("bulk_review.html", job=job, place=place, names=names, model=vision.status())


@bp.route("/api/bulk/<int:job_id>")
def bulk_json(job_id):
    with db.db() as conn:
        job = db.get_bulk_job(conn, job_id) or abort(404)
    return jsonify(id=job["id"], status=job["status"], error=job["error"])


@bp.route("/bulk/<int:job_id>/save", methods=["POST"])
def bulk_save(job_id):
    names = [_clean(n, 120) for n in request.form.getlist("name")]
    keep = set(request.form.getlist("keep"))
    chosen = [n for i, n in enumerate(names) if str(i) in keep and n]
    attach_photo = request.form.get("attach_photo") == "1"
    with db.db() as conn:
        job = db.get_bulk_job(conn, job_id) or abort(404)
        place_id = job["place_id"]
        for n in chosen:
            db.create_item(conn, place_id, n, photo=job["photo"] if attach_photo else None,
                           desc_status="done" if attach_photo else "none")
        db.delete_bulk_job(conn, job_id)
        if not attach_photo or not chosen:
            if not db.photo_in_use(conn, job["photo"]):
                photos.remove(job["photo"])
    return redirect(url_for("main.place", place_id=place_id))


@bp.route("/bulk/<int:job_id>/cancel", methods=["POST"])
def bulk_cancel(job_id):
    with db.db() as conn:
        job = db.get_bulk_job(conn, job_id) or abort(404)
        db.delete_bulk_job(conn, job_id)
        if not db.photo_in_use(conn, job["photo"]):
            photos.remove(job["photo"])
    return redirect(url_for("main.place", place_id=job["place_id"]))


# ---- labels and scanning ----

@bp.route("/places/<int:place_id>/label")
def label(place_id):
    with db.db() as conn:
        place = db.get_place(conn, place_id) or abort(404)
    return render_template("labels.html", places=[place], qr_svg=qr.svg, place_url=_place_url)


@bp.route("/labels")
def labels():
    ids = request.args.getlist("id", type=int)
    with db.db() as conn:
        places = [p for p in db.list_places(conn) if not ids or p["id"] in ids]
    if not ids and request.args.get("all") != "1":
        return render_template("labels_pick.html", places=places)
    return render_template("labels.html", places=places, qr_svg=qr.svg, place_url=_place_url)


@bp.route("/scan")
def scan():
    return render_template("scan.html")


# ---- files ----

@bp.route("/photos/<path:name>")
def photo(name):
    if "/" in name or not name.endswith(".jpg"):
        abort(404)
    return send_from_directory(os.path.abspath(config.PHOTO_DIR), name, max_age=86400)


@bp.route("/manifest.webmanifest")
def manifest():
    resp = send_from_directory(os.path.join(bp.root_path, "static"), "manifest.webmanifest")
    resp.mimetype = "application/manifest+json"
    return resp


@bp.route("/sw.js")
def service_worker():
    resp = send_from_directory(os.path.join(bp.root_path, "static", "js"), "sw.js", max_age=0)
    resp.headers["Service-Worker-Allowed"] = "/"
    return resp


@bp.route("/health")
def health():
    from . import version
    return jsonify(ok=True, version=version())
