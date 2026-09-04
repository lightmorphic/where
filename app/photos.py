"""Store an uploaded photo as a sensible-sized JPEG plus a thumbnail."""
import os
import secrets

from PIL import Image, ImageOps

from . import config


def save_upload(file_storage):
    """Returns the stored filename, or None if nothing usable was uploaded."""
    if file_storage is None or not file_storage.filename:
        return None
    try:
        img = Image.open(file_storage.stream)
        img = ImageOps.exif_transpose(img)
    except Exception:
        return None
    img = img.convert("RGB")
    name = secrets.token_hex(8) + ".jpg"
    full = img.copy()
    full.thumbnail((config.PHOTO_MAX, config.PHOTO_MAX))
    full.save(os.path.join(config.PHOTO_DIR, name), "JPEG", quality=85, optimize=True)
    thumb = img.copy()
    thumb.thumbnail((config.THUMB_MAX, config.THUMB_MAX))
    thumb.save(os.path.join(config.PHOTO_DIR, thumb_name(name)), "JPEG", quality=80, optimize=True)
    return name


def thumb_name(name):
    return name[:-4] + "_t.jpg"


def path(name):
    return os.path.join(config.PHOTO_DIR, name)


def remove(name):
    for n in (name, thumb_name(name)):
        try:
            os.remove(path(n))
        except FileNotFoundError:
            pass
