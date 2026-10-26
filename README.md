# Live Free or Die Universe

A restoration of Luke Bradford's collection of patterns in the Live Free or Die cellular automaton (B2/S0).
The collection was originally published at `mysite.verizon.net/live_free/` (2007–2011) and then at `lfod.wikispaces.com` (2013–2018).

The site is static and lives in `docs/`, ready for GitHub Pages (serve from the `main` branch, `/docs` folder).
Every pattern plays live in the browser.

## Layout

- `archive/` (not in this repository; kept locally because most of it was never public): the recovered original material.
  - `verizon-site/`: the 2009 site source.
  - `rle-files/`: the site's pattern files and Josh Ball's files.
  - `early-2006/` and `early-2007/`: the earliest pattern files.
  - `notes/`: Word research notes.
  - `images/`: named pattern images.
  - `wikispaces/`: Wayback captures of the wiki, its images, and the October 2013 collection.
  - `verizon-wayback/`: Wayback captures of the Verizon site.
- `data/`: structured data extracted from the archive: glossary, tables, news, wiki pages, selected forum patterns, and post-2009 additions.
- `tools/`: stdlib-only Python.
  - `lfod.py`: simulator, RLE, Life 1.05 and macrocell I/O.
  - Extractors, one per source.
  - `build.py`: generates `docs/`.
- `docs/`: the generated site.

## Rebuilding

Rebuilding needs the local `archive/` folder. The published `docs/` is checked in, so you don't need to rebuild just to view the site.

```sh
python3 tools/make_later.py    # optional: regenerate data/later.json
python3 tools/build.py         # regenerate docs/
python3 -m http.server -d docs 8000
```

The extractors for the original Word HTML (`parse_glossary.py`, `extract_tables.py`) need `beautifulsoup4`.
`extract_forum.py` reads a local text dump of the ConwayLife thread, which isn't kept in this repo.
Only the selected patterns are kept, each with its poster, date and a link to the post.

See `docs/restoration.html` for what was recovered and what is lost.
