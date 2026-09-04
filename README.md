# Where

*Where did I put that thing?*

A small self-hosted web app for one job: remembering which cupboard, shelf, box or tray a thing is in. Not an inventory system. No prices, no receipts, no categories. Adding an item takes a photo and a name.

- **Places** are a flat list: "Cupboard 1", "Top shelf", "Storage box", "Tray 14".
- **Items** each live in one place, with a photo, a name, a description, a note and a *gone* switch.
- **Descriptions are written for you** from the photo by a local vision model (Ollama, Moondream by default), so "USB-C cable" becomes "black, right-angle, about a metre". Nothing leaves your network.
- **Add lots from one photo**: photograph a whole tray, tick what it found, fix names, save them all.
- **QR labels** for each place, sized for 30 × 20 mm thermal labels. Scan one with the phone camera and the place opens.
- **Search** across name, description and note. Results say plainly: "USB-C cable — Tray 14".
- Works as a phone app: mobile-first, installable to the home screen, camera capture for photos and scanning.

## Run it

You need Docker. Everything you might change lives in `.env`.

```bash
sudo mkdir -p /opt/where/data /opt/where/ollama
sudo chown -R 1000:1000 /opt/where/data
cp .env.example .env
docker compose up -d
```

Then open `http://<your-server>:4150`. The vision model downloads itself the first time it is needed (about 1.7 GB for Moondream), so the first description takes a while.

The app runs as user 1000 inside the container, which is why the data folder is owned by 1000 on the host.

### Settings (`.env`)

| Setting | What it does | Default |
|---|---|---|
| `WHERE_PORT` | Port you open in the browser | `4150` |
| `WHERE_DATA` | Host folder holding database, photos and the model | `/opt/where` |
| `OLLAMA_HOST` | Where Ollama is. The bundled container is `http://ollama:11434` | bundled |
| `OLLAMA_MODEL` | Vision model to use. Swap for `llava` or `minicpm-v` on a bigger machine | `moondream` |
| `WHERE_PUBLIC_URL` | Address baked into QR labels. Blank uses whatever you are browsing from | blank |
| `TZ` | Timezone | `Europe/London` |

### Updating

```bash
docker compose pull
docker compose down
docker compose up -d
```

### Backing up

Everything is in `WHERE_DATA` (`/opt/where` by default): `data/where.db` and `data/photos/`. Copy that folder and you have it all. The `ollama/` folder is just the downloaded model and can be re-downloaded.

## Camera on the phone

Browsers only open the camera on a secure address. Over Tailscale Serve (`https://...ts.net:4150`) it just works. On plain `http://` you can still add items by choosing a photo from the gallery, but live QR scanning needs `https`.

## Printing labels

Home → *Print labels* → pick the places → *Make the print sheet* → print. Set the printer's paper size to the label (30 × 20 mm) with no margins; each label is one page. Amazon FBA style thermal labels fit as they are.

## Development

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
pytest
python run.py        # http://127.0.0.1:8080, data in ./data
```

## Licence

GPL-3.0. See `LICENSE`.
