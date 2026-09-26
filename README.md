# FF14 Gather List Builder

A small local web app for building FFXIV gathering lists. It looks up items via
[xivapi](https://v2.xivapi.com/), resolves crafting recipes down to base materials, shows live
spawn timers for timed nodes, and helps you farm collectables — with as few API calls as
possible thanks to aggressive local caching.

## Features at a glance

- **Gathering lists** — create as many as you like, add items with live name suggestions,
  amounts merge automatically, everything is stored as plain JSON on your machine.
- **Recipe resolution** — craftable items get a "+ Materials" button that adds all base
  materials (nested recipes included).
- **Live node timers** — timed items count down to their next spawn window in real seconds,
  with zone, in-game coordinates and the nearest aetheryte one click away.
- **Alarms** — a sound (pick one, or drop your own into `static/alarms/`) when a node on your
  list comes up, mutable per item, silent for done items.
- **Progress tracking** — done-checkboxes, item pinning, and automatic grouping: craftables on top, materials middle, crystals bottom.
- **Sharing** — export a list as a JSON file, import someone else's; all game data is
  re-fetched locally, in your language.
- **Your look** — random background images from `static/backgrounds/`.

## Getting it running

1. **Install Python 3.14** (any 3.12+ works) from [python.org](https://www.python.org/downloads/).
   - **Important (Windows):** in the installer, tick **"Add python.exe to PATH"** on the first
     screen. Without it, the commands below won't be found.
2. Download or clone this repository.
3. Open a terminal in the project folder and install the dependencies:

   ```
   python -m pip install -r requirements.txt
   ```

4. Start the server:

   ```
   python app.py
   ```

5. Open http://127.0.0.1:5000 in your browser. That's it — everything runs locally.

## How to use it

### Lists (main tab)

- **Create a list** with the "New list name" field, or open an existing one from the dropdown.
- **Add items** by name — after a short pause while typing, a suggestion dropdown offers matching
  item names straight from the game data.
- Craftable items get a **"+ Materials" button** that resolves their recipe (including nested
  recipes) and adds all base materials, scaled by the item's amount.
- The list sorts itself: **craftable items on top, materials in the middle, crystals at the
  bottom**, with divider lines between the groups.
- **Tick the socket** in front of an item to mark it as done — it lights up and the row is
  struck through. Progress is saved with the list.
- **Pin rows** with the thin strip on the row's left edge — pinned items stay visible at the
  top while you scroll. Works on the collectables tabs too.
- Adding the same item again sums the amounts. Amounts are editable in place (Save), items can be
  deleted individually, and the whole list can be emptied or deleted.
- **Share lists**: Export downloads the selected list as a JSON file; the Import button in the
  bottom-right corner opens a small popup to add a shared file as a new list — its game data is
  re-fetched in the background, in your language.
- **Click an item name** to copy it to your clipboard — paste it into the in-game chat and press
  Tab to turn it into a real, clickable item link.
- The **Game ID** column links to the item on Garland Tools.

### Timers and alarms

- Items from timed gathering nodes (unspoiled/ephemeral) show a live countdown — green while the
  node is up. Clicking the timer shows the zone and its aetheryte.
- Turn on the **alarm** (top left) to hear a sound whenever a node on your list comes up — it
  works even when the browser tab is in the background. Pick a sound from the dropdown, test it
  with the Test button, or drop your own `.mp3`/`.wav`/`.ogg` into `static/alarms/`.
- The small red socket next to a timer **mutes that item's alarm**; done items are silent
  automatically. Crystals never show timers — they're gatherable in enough other ways.

### Gatherable Collectables

A browsable table of all gathering collectables with job, level, stars, scrip rewards, spawn
timer, and node position (zone and aetheryte link to the wiki). Filter by name, job, level and
scrips — filters apply live — and sort by clicking the column headers. One click adds an item to
your selected list. The gold socket in front of timed items **alarm-marks** them: with the
"Marked alarms" switch (top right of the panel) on, those nodes sound the alarm straight from
this tab, and the row of filters includes a view showing only your alarm-marked items.

### Craftable Collectables

The same for crafter collectables: job (with icon), recipe level, and scrip rewards, with the
same live filters (by default only items with a current scrip reward are shown — legacy
collectables are one dropdown away). The
**"Add + materials"** button puts the collectable itself *and* all its base materials on your
list, so you always know what you meant to craft. Adding runs in the background — you can keep
browsing or switch tabs, and the list page refreshes itself when everything has arrived. Job
display names and icons can be adjusted in `job_names.json`.

### Language

The dropdown in the top right switches both the interface and the game data (item names,
suggestions, zones) between EN, DE, FR and JA. The open list is translated immediately; other
lists follow when you open them, item by item from cache. Interface translations live in `translations/`
as simple JSON files (EN and DE are included). To contribute a new one, copy
`translations/_template.json` to `<code>.json` and fill in the `"translation"` values — see
`translations/README.md`. Untranslated entries fall back to English.

### Caching

All game data fetched from xivapi is cached locally in `data/cache/` for 60 days, so the API is
asked about each item at most once. **Clear caches** (top right) wipes it, for example after a
game patch. Your lists live in `data/lists/` as plain JSON files — back them up by copying that
folder.

### Backgrounds

Drop images into `static/backgrounds/` and every new browser tab uses a random one as the page
background. The bundled background images are AI-generated (Midjourney).

---

Built with [Claude](https://claude.com/claude-code).
