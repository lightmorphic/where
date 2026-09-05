# Where

*Where did I put that thing?*

> **Beta.** Where is early software. Everything described here works, but it has
> not yet been through much use by many people, so expect rough edges and keep a
> copy of your data folder. Problems are welcome on the
> [issue tracker](https://github.com/lightmorphic/where/issues).

**Website: [where.lightmorphic.com](https://where.lightmorphic.com/)**

A small self-hosted web app for one job: remembering which cupboard, shelf, box or tray a thing is in. Not an inventory system. No prices, no receipts, no categories. Adding an item takes a photo and a name.

- **Places** are a flat list: "Cupboard 1", "Top shelf", "Storage box", "Tray 14".
- **Items** each live in one place, with a photo, a name, a description, a note and a *gone* switch.
- **Descriptions are written for you** from the photo by a local vision model (Ollama, Moondream by default), so "USB-C cable" becomes "black, right-angle, about a metre". Nothing leaves your network.
- **Add lots from one photo**: photograph a whole tray, tick what it found, fix names, save them all.
- **QR labels** for each place, sized for 30 × 20 mm thermal labels. Scan one with the phone camera and the place opens.
- **Search** across name, description and note. Results say plainly: "USB-C cable — Tray 14".
- **Accounts** so a household can share one list. Everyone signs in with their own name and password and sees the same places and items.
- **Everything is set up inside the app.** There is nothing to configure in `docker-compose.yml` and no `.env` file: the model, its address, the label address and who may sign in all live on the Settings page.
- Works as a phone app: mobile-first, installable to the home screen, camera capture for photos and scanning.

## Run it

You need Docker.

```bash
sudo mkdir -p /opt/where/data /opt/where/ollama
sudo chown -R 1000:1000 /opt/where/data
docker compose up -d
```

**Do not skip the second line.** Where runs as user 1000 inside the container, so
the folder on the host has to belong to user 1000 or the app cannot write to it
and will not start. If you ever delete the data folder, Docker recreates it owned
by root, and you have to run that line again:

```bash
sudo chown -R 1000:1000 /opt/where/data
docker compose up -d --force-recreate
```

Then open `http://<your-server>:4150`. The first visit asks you to create an account, and that first account runs the place. The vision model downloads itself the first time it is needed (about 1.7 GB for Moondream), so the first description takes a while.

### Settings

There is no `.env` file and nothing to configure in the compose file. Everything is on the **Settings** page inside the app:

| Setting | What it does |
|---|---|
| Address of the model | Where Ollama is. Leave it on the bundled container, or point it at a machine with more memory |
| Model name | Which vision model to use. See below |
| Give up after | How long to wait for one photo |
| Address in QR codes | Baked into printed labels. Leave it empty to use whatever address you print from |
| Let anyone make an account | Off by default. With it off, you add people yourself |

The only two things left in `docker-compose.yml` are the port to open the app on and the folder your data lives in, because neither can be set from inside a running container.

### Accounts

Everyone signed in shares one list, because two people in the same house need to find the same cable. The first account created runs the place: it can change the settings above and add or remove other accounts. New accounts are closed by default, so an address handed to a visitor does not let them sign themselves up.

### Choosing the model

Moondream is the default: small, quick, and good at a short description of one
item. It is weak at listing everything in a tray photo. If *add lots from one
photo* disappoints, set `OLLAMA_MODEL=minicpm-v` (about 5.5 GB) in `.env` and
restart. The new model downloads itself on first use.

### Updating

```bash
docker compose pull
docker compose down
docker compose up -d
```

### Backing up

Everything is in `/opt/where/data`: `where.db`, `photos/` and `secret.key`, which is what keeps people signed in across a restart. Copy that folder and you have it all. The `ollama/` folder is just the downloaded model and can be re-downloaded.

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
