# Changelog

All notable changes to Where are recorded here.

## [0.3.0] — 2026-09-06

- **One theme.** Where is dark, full stop. The light theme and the switch that chose between them are gone, along with every trace of them in the stylesheet, the templates and the script. Nothing is stored in your browser about how you like it to look.

## [0.2.3] — 2026-09-05

- **The app no longer pretends to be online.** If the server cannot be reached, you now get a page that says so and explains the usual reasons. Before this, a saved copy of a page was shown instead, which looked perfectly normal until you filled a form in and it hung. Nothing you type is ever saved on the device.
- **Every request is written to the container log**, one short line each, so it is possible to tell "the app is broken" apart from "nothing ever reached the app". Pictures and the stylesheet are left out so the log stays readable.

## [0.2.2] — 2026-09-05

- **`docker compose up -d` now works on a fresh machine with nothing else to do.** The container starts as root only long enough to hand its data folder to the unprivileged user it runs as, then gives up root for good before serving anything. No folders to make in advance, no `chown`, and deleting the data folder no longer leaves the app unable to start. Add `user: "1000:1000"` to the service if you would rather it never started as root.

## [0.2.1] — 2026-09-05

- If Where cannot write to its data folder it now says so in one readable line, names the user it runs as, and gives you the command to fix it, instead of repeating a stack trace until you give up. This is what happens when the folder on the host belongs to root, which is what Docker does if you delete it.

## [0.2.0] — 2026-09-05

A breaking change to how Where is set up. Nothing is configured in
`docker-compose.yml` any more, and the app now asks you to sign in.

- **Accounts.** Everyone signs in with their own name and password and shares one list of places and items, because two people in the same house need to find the same cable. The first account created runs the copy: it changes the settings and adds or removes everyone else. Self-service sign-up is off unless you switch it on.
- **A Settings page.** The model, its address, how long to wait for one photograph, the address printed into QR labels and who may sign in all live in the app now.
- **No configuration in the compose file and no `.env` file.** Only the port to open the app on and the folder your data lives in are left, because neither can be set from inside a running container. If you are upgrading, delete your `.env`, replace the compose file with the one in the README, and put your old settings in on the Settings page.
- The timezone setting has gone. Nothing in Where displays a time, so it did nothing.
- Collapsible sections now show an arrow, and password fields are full width.

## [0.1.4] — 2026-09-05

- Label names now sit on one line wherever they will fit, shrinking to suit, and only wrap when a single line would be too small to read. A word is never split.
- Items with no photograph show a small box outline instead of an empty grey square.
- Searching no longer reopens the phone keyboard over your results.
- Added the project website at [where.lightmorphic.com](https://where.lightmorphic.com/), carrying the privacy, cookies, terms, accessibility and complaints pages.

## [0.1.3] — 2026-09-05

- If the model cannot describe an item under the name you gave it, the app asks again without the name rather than giving up.

## [0.1.2] — 2026-09-05

- Dark mode is now the default, with a switch in the top corner that remembers your choice.
- Label text never splits a word across lines. The name shrinks to fit instead, measured after the font has loaded.
- Photo descriptions no longer repeat themselves or come back as a single stray word. The wording asked of the model is shorter and plainer, output is capped, looping phrases are dropped, and the text is cut at a whole word.
- A description that comes back as junk is not saved. The item says the photo could not be described, and it can be tried again.

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
