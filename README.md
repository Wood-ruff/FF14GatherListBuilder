# FF14 Gather List Builder

A small local web app for building FFXIV gathering lists. It looks up items via
[xivapi](https://v2.xivapi.com/), resolves crafting recipes down to base materials, shows live
spawn timers for timed nodes, and helps you farm collectables — with as few API calls as
possible thanks to aggressive local caching.

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
- **Add materials**: type a craftable item into the second field and the app resolves its recipe
  (including nested recipes) and adds all base materials instead.
- Adding the same item again sums the amounts. Amounts are editable in place (Save), items can be
  deleted individually, and the whole list can be emptied or deleted.
- **Click an item name** to copy it to your clipboard — paste it into the in-game chat and press
  Tab to turn it into a real, clickable item link.
- The **Game ID** column links to the item on Garland Tools.

### Timers and alarms

- Items from timed gathering nodes (unspoiled/ephemeral) show a live countdown — green while the
  node is up. Clicking the timer shows the zone and its aetheryte.
- Turn on the **alarm** (top left) to hear a sound whenever a node on your list comes up — it
  works even when the browser tab is in the background. Pick a sound from the dropdown, test it
  with the Test button, or drop your own `.mp3`/`.wav`/`.ogg` into `static/alarms/`.

### Gatherable Collectables

A browsable table of all gathering collectables with job, level, stars, scrip rewards, spawn
timer, and node position (zone links to the wiki). Filter by job and level, sort by clicking the
column headers, and add items to your selected list with one click.

### Craftable Collectables

The same for crafter collectables: job (with icon), recipe level, and scrip rewards. The
**"Add + materials"** button puts the collectable itself *and* all its base materials on your
list, so you always know what you meant to craft.

### Language

The dropdown in the top right switches both the interface and the game data (item names,
suggestions, zones) between EN, DE, FR and JA. Interface translations live in `translations/`
as simple JSON files — copy `en.json`, translate the values, and name it after your language
code to add a new one. (EN and DE are included.)

### Caching

All game data fetched from xivapi is cached locally in `data/cache/` for 60 days, so the API is
asked about each item at most once. **Clear caches** (top right) wipes it, for example after a
game patch. Your lists live in `data/lists/` as plain JSON files — back them up by copying that
folder.

---

Built with [Claude](https://claude.com/claude-code).
