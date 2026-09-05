# Changelog

All notable changes to Where are recorded here.

## [0.1.1] — 2026-09-05

- Dark mode is now the default, with a switch in the top corner that remembers your choice.
- Label text never splits a word across lines. The name shrinks to fit instead, measured after the font has loaded.
- Photo descriptions no longer repeat themselves. Output is capped, looping phrases are dropped, and the text is cut at a whole word.

## [0.1.0] — 2026-09-04

First working version.

- Places: a flat list of cupboards, shelves, boxes and trays. Add, rename, remove when empty.
- Items: photo, name, place, note and a gone switch. Adding one takes a photo and a name.
- Descriptions written from the photo by a local vision model through Ollama. The item saves at once and the text fills in when ready; if the model is down the item still saves and can be described again later. Any description can be edited by hand, and a hand edit is never overwritten.
- Add lots from one photo: photograph a tray, get a list back, tick and correct, save them all to that place.
- Search across name, description, note and place name. Results read "USB-C cable — Tray 14".
- QR labels per place, print-ready at 30 × 20 mm for thermal label rolls, with a batch print sheet.
- Scan a label with the phone camera to open that place.
- Installable to the phone home screen, with the app shell cached for poor connections.
- Everything configured from `.env`: port, data folder, Ollama address, model, timezone.
