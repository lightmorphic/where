import io

from PIL import Image

from app import vision


def _jpeg():
    buf = io.BytesIO()
    Image.new("RGB", (900, 600), (200, 30, 30)).save(buf, "JPEG")
    buf.seek(0)
    return buf


def test_home_empty(client):
    r = client.get("/")
    assert r.status_code == 200
    assert b"No places yet" in r.data


def test_place_and_item_flow(client):
    r = client.post("/places", data={"name": "Tray 14"}, follow_redirects=False)
    assert r.status_code == 302 and "/places/1" in r.headers["Location"]

    r = client.post("/items", data={"name": "USB-C cable", "place_id": 1, "note": "usually on the desk",
                                    "photo": (_jpeg(), "cable.jpg")},
                    content_type="multipart/form-data")
    assert r.status_code == 302 and "saved=1" in r.headers["Location"]

    r = client.get("/api/items/1").get_json()
    assert r["desc_status"] == "pending"   # photo present, model not asked yet

    r = client.get("/places/1")
    assert b"USB-C cable" in r.data and b"Describing photo" in r.data

    r = client.get("/search?q=usb")
    assert b"USB-C cable" in r.data and b"Tray 14" in r.data

    r = client.get("/search?q=desk")
    assert b"USB-C cable" in r.data

    # A hand edit while pending marks it done so the model cannot overwrite it.
    client.post("/items/1/edit", data={"name": "USB-C cable", "description": "black, one metre", "note": "", "place_id": 1})
    assert client.get("/api/items/1").get_json()["desc_status"] == "done"

    r = client.post("/items/1/gone", json={"gone": True})
    assert r.get_json()["gone"] == 1
    assert b"USB-C cable" not in client.get("/search?q=usb").data
    assert b"USB-C cable" in client.get("/search?q=usb&gone=1").data

    assert client.post("/places/1/delete").status_code == 302
    assert client.get("/places/1").status_code == 200   # still there, not empty

    client.post("/items/1/delete")
    client.post("/places/1/delete")
    assert client.get("/places/1").status_code == 404


def test_item_without_photo_has_no_description_job(client):
    client.post("/places", data={"name": "Shelf"})
    client.post("/items", data={"name": "Tape", "place_id": 1})
    assert client.get("/api/items/1").get_json()["desc_status"] == "none"


def test_labels_and_qr(client):
    client.post("/places", data={"name": "Cupboard 1"})
    client.post("/places", data={"name": "Cupboard 2"})
    r = client.get("/places/1/label")
    assert r.status_code == 200 and b"<svg" in r.data and b"Cupboard 1" in r.data
    r = client.get("/labels?id=1&id=2")
    assert r.data.count(b'class="label"') == 2
    r = client.get("/labels")
    assert b"Make the print sheet" in r.data


def test_bulk_flow_with_model_down(client):
    client.post("/places", data={"name": "Tray 1"})
    r = client.post("/bulk", data={"place_id": 1, "photo": (_jpeg(), "tray.jpg")}, content_type="multipart/form-data")
    assert "/bulk/1" in r.headers["Location"]
    assert client.get("/api/bulk/1").get_json()["status"] == "pending"
    # Run the worker step by hand: Ollama is unreachable so the job fails cleanly.
    vision._bulk(1)
    assert client.get("/api/bulk/1").get_json()["status"] == "failed"
    r = client.get("/bulk/1")
    assert b"did not work" in r.data
    # Items can still be typed in and saved.
    r = client.post("/bulk/1/save", data={"name": ["Screwdriver", "Pliers", "junk"], "keep": ["0", "1"], "attach_photo": "1"})
    assert r.status_code == 302
    r = client.get("/places/1")
    assert b"Screwdriver" in r.data and b"Pliers" in r.data and b"junk" not in r.data


def test_clean_sentence_strips_lead_in_and_loops():
    looped = "The image shows a black, rectangular, USB-C, black, rectangular, USB-C, black."
    assert vision.clean_sentence(looped) == "Black, rectangular, USB-C"
    assert vision.clean_sentence("  A  short   one  ") == "A short one"
    long = vision.clean_sentence("word " * 200)
    assert len(long) <= 300 and not long.endswith("wor")


def test_parse_list_cleans_model_output():
    text = "1. USB-C cable\n- AA batteries, four of them\n* Tray\n\nScrewdriver.\nusb-c cable"
    assert vision.parse_list(text) == ["USB-C cable", "AA batteries", "Screwdriver"]


def test_describe_marks_failed_when_model_unreachable(client):
    client.post("/places", data={"name": "Tray 1"})
    client.post("/items", data={"name": "Cable", "place_id": 1, "photo": (_jpeg(), "c.jpg")}, content_type="multipart/form-data")
    vision._describe(1)
    assert client.get("/api/items/1").get_json()["desc_status"] == "failed"


def test_health(client):
    assert client.get("/health").get_json()["ok"] is True
