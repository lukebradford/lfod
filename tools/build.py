"""Build the static GitHub Pages site in docs/ from data/ and archive/.

Usage: python3 tools/build.py   (standard library only)
"""
import html, json, re, shutil, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from lfod import load_pattern, to_rle, classify  # noqa: E402

DATA, ARCHIVE, OUT = ROOT / "data", ROOT / "archive", ROOT / "docs"
esc = html.escape

def load(name, default=None):
    p = DATA / name
    return json.loads(p.read_text()) if p.exists() else default

GLOSSARY = load("glossary.json")
SUPPLEMENTS = load("supplements.json")
TABLES = load("tables.json")
NEWS = load("news.json")
LATER = load("later.json", {"entries": [], "news": [], "files": []})

NAV = [
    ("index.html", "Home"), ("news.html", "News"), ("glossary.html", "Glossary"),
    ("tables.html", "Object tables"), ("periods.html", "Periods"), ("iterations.html", "Iterations"),
    ("challenges.html", "Challenges"), ("files.html", "Files"), ("restoration.html", "About this restoration"),
]

def slug(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower().replace("’", "").replace("'", "")).strip("-")

def asset_version():
    import hashlib
    h = hashlib.sha1()
    for name in ("style.css", "lfod.js"):
        h.update((OUT / "assets" / name).read_bytes())
    return h.hexdigest()[:8]

def page(filename, title, body, description=""):
    v = asset_version()
    nav = "".join(f'<a href="{h}"{" class=\"active\"" if h == filename else ""}>{esc(t)}</a>' for h, t in NAV)
    full_title = "Live Free or Die Universe" if filename == "index.html" else f"{title} · Live Free or Die Universe"
    doc = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(full_title)}</title>
<meta name="description" content="{esc(description or 'An exploration of the Live Free or Die (B2/S0) cellular automaton.')}">
<link rel="icon" href="img/icon.png">
<link rel="stylesheet" href="assets/style.css?v={v}">
<script src="assets/lfod.js?v={v}" defer></script>
</head>
<body>
<header class="site-header"><div class="inner">
<a class="brand" href="index.html">Live Free or Die Universe<small>B2/S0</small></a>
<nav class="main" aria-label="Main">{nav}</nav>
</div></header>
<main>
{body}
</main>
<footer class="site-footer"><div class="inner">
Objects found and named by Luke Bradford unless otherwise credited. Originally published at
mysite.verizon.net/live_free (2007–2012) and lfod.wikispaces.com (2013–2018); restored 2026.
Patterns run live in your browser — click any pattern to pause or play.
</div></footer>
</body>
</html>
"""
    (OUT / filename).write_text(doc)

def player(rle, label, height=170, loop=0, speed=8, autoplay=True):
    attrs = f'data-rle="{esc(rle)}" data-label="{esc(label)}" data-height="{height}" data-speed="{speed}"'
    if loop:
        attrs += f' data-loop="{loop}"'
    if not autoplay:
        attrs += ' data-autoplay="false"'
    return f'<div class="pattern" {attrs}></div>'

def table_html(rows, link_names=None, header=True):
    out = ['<div class="table-wrap"><table>']
    for i, row in enumerate(rows):
        tag = "th" if header and i == 0 else "td"
        cells = []
        for j, c in enumerate(row):
            cls = ' class="num"' if tag == "td" and re.fullmatch(r"[-+]?[\d.]+", c) else ""
            text = esc(c)
            if link_names and tag == "td" and j == 0 and slug(c) in link_names:
                text = f'<a href="glossary.html#{slug(c)}">{text}</a>'
            cells.append(f"<{tag}{cls}>{text}</{tag}>")
        out.append("<tr>" + "".join(cells) + "</tr>")
    out.append("</table></div>")
    return "\n".join(out)

# ---------------------------------------------------------------- glossary data

KIND_LABELS = {
    "oscillator": "Oscillators", "spaceship": "Spaceships", "puffer": "Puffers & rakes",
    "tagalong": "Tagalongs & trailers", "reaction": "Sparks, pre-sparks & reactions", "term": "Terms",
}
TERM_NAMES = {"anchored", "bi-anchored", "left-anchored", "right-anchored", "attached wing", "floating wing",
              "boxy", "dusty", "empty", "heavy", "engine", "engine horn", "flame", "horn", "nose", "wing",
              "wing notation", "W-winged", "phase type", "anchor track flotilla", "anchor stack", "stack"}

def kind_of(e):
    if e["name"] in TERM_NAMES or not e.get("rle"):
        if e["name"] in ("monster puffer", "anchor biter puffer", "anchor eater ship"):
            return "puffer" if "puffer" in e["name"] else "spaceship"
        return "term"
    d = e["desc"].lower()
    m = re.search(r"\b(oscillator|spaceship|puffer|rake|trailer|tagalong|pre-spark|spark|reaction|fuse|predecessor)s?\b", d)
    w = m.group(1) if m else "term"
    if e["name"] in ("bomb", "shrinker"):
        return "reaction"
    if e["name"] in ("dot",):
        return "oscillator"
    if e["name"] in ("checker",):
        return "oscillator"
    if e["name"] in ("anchor biter", "anchor eater", "half anchor eater", "half anchor biter", "dual infinite anchor track"):
        return "tagalong"
    return {"rake": "puffer", "trailer": "tagalong", "pre-spark": "reaction", "spark": "reaction",
            "fuse": "reaction", "predecessor": "reaction"}.get(w, w)

def all_entries():
    entries = []
    for e in GLOSSARY:
        e = dict(e)
        if not e.get("rle") and e["name"] in SUPPLEMENTS:
            e["rle"] = SUPPLEMENTS[e["name"]]
            e["reconstructed"] = True
        e["source"] = e.get("source", "2009 glossary")
        entries.append(e)
    names = {x["name"].lower() for x in entries}
    for e in LATER.get("entries", []):
        if e["name"].lower() in names:
            for x in entries:
                if x["name"].lower() == e["name"].lower():
                    x.setdefault("later_notes", []).append(e)
        else:
            entries.append(dict(e))
    for e in entries:
        e["kind"] = e.get("kind") or kind_of(e)
        e["slug"] = slug(e["name"])
    entries.sort(key=lambda e: e["name"].lower().lstrip("’'"))
    return entries

ENTRIES = all_entries()
SLUGS = {e["slug"] for e in ENTRIES}

GENERIC = {"cell", "generation", "period", "oscillator", "spaceship", "puffer", "spark", "rake", "trailer",
           "tagalong", "stack", "still life", "rotor", "stator", "phoenix", "explosive", "wing", "engine", "nose",
           "horn", "flame", "heavy", "empty", "boxy", "dusty", "phase type"}

def autolink(text, self_slug):
    """Link mentions of other glossary entries (longest names first)."""
    names = sorted({e["name"] for e in ENTRIES if len(e["name"]) > 3 and e["slug"] != self_slug
                    and e["name"] not in GENERIC}, key=len, reverse=True)
    if not names:
        return esc(text)
    pat = re.compile(r"\b(" + "|".join(re.escape(n) for n in names) + r")(s|es)?\b", re.I)
    out, last, used = [], 0, set()
    for m in pat.finditer(text):
        s = slug(m.group(1))
        out.append(esc(text[last:m.start()]))
        if s in used or s not in SLUGS:
            out.append(esc(m.group(0)))
        else:
            used.add(s)
            out.append(f'<a href="#{s}">{esc(m.group(0))}</a>')
        last = m.end()
    out.append(esc(text[last:]))
    return "".join(out)

def loop_for(e):
    if not e.get("rle"):
        return 0
    k = e["kind"]
    m = re.search(r"\bp(\d+)\b", e["desc"])
    p = int(m.group(1)) if m else 4
    if k == "oscillator":
        return max(40, p * 3)
    if k == "spaceship":
        return max(48, p * 8)
    if k == "reaction":
        return 60
    return 120

# ---------------------------------------------------------------- pages

def build_glossary():
    chips = "".join(f'<button class="chip" type="button" data-kind="{k}" aria-pressed="false">{esc(v)}</button>'
                    for k, v in KIND_LABELS.items())
    cards, letter = [], None
    for e in ENTRIES:
        L = e["name"].lstrip("’'")[0].upper()
        if L != letter:
            letter = L
            cards.append(f'<div class="letter" data-letter>{L}</div>')
        tags = [f'<span class="tag">{esc(KIND_LABELS[e["kind"]].rstrip("s").split(" &")[0].split(",")[0])}</span>']
        credit = e.get("credit") or ""
        if credit:
            tags.append(f'<span class="tag credit">{esc(credit)}</span>')
        if e.get("source", "").startswith("wiki") or e.get("source", "").startswith("forum"):
            tags.append(f'<span class="tag">added {esc(e["source"])}</span>')
        if e.get("reconstructed"):
            tags.append('<span class="tag" title="Pattern decoded from the original glossary image">from image</span>')
        body = [f'<p>{autolink(e["desc"], e["slug"])}</p>']
        if e.get("post"):
            body.append(f'<p class="muted"><a href="{esc(e["post"])}">Original forum post</a></p>')
        if e.get("rle"):
            h = 120 if e["kind"] in ("reaction",) else 170
            body.append(player(e["rle"], e["name"], height=h, loop=loop_for(e)))
        elif e.get("images"):
            for im in e["images"][:1]:
                src = "img/glossary/" + Path(im["src"]).name
                body.append(f'<img class="orig" src="{src}" alt="Original 2009 illustration for {esc(e["name"])}" loading="lazy">')
        for n in e.get("later_notes", []):
            body.append(f'<p class="muted"><em>Later ({esc(n.get("source", ""))}):</em> {esc(n["desc"])}</p>')
            if n.get("rle"):
                body.append(player(n["rle"], e["name"] + " (later)", loop=120))
        cls = "entry term" if e["kind"] == "term" else "entry"
        search = esc((e["name"] + " " + e["desc"]).lower())
        cards.append(f'<article class="{cls}" id="{e["slug"]}" data-kind="{e["kind"]}" data-search="{search}">'
                     f'<h3><a href="#{e["slug"]}">{esc(e["name"])}</a></h3><div class="meta">{"".join(tags)}</div>'
                     + "".join(body) + "</article>")
    n_pat = sum(1 for e in ENTRIES if e.get("rle"))
    body = f"""
<h1>Glossary</h1>
<div class="prose">
<p class="lede">Every named object and term in Live Free or Die: {len(ENTRIES)} entries, {n_pat} with runnable patterns.</p>
<p class="muted">Text is from the June 2009 glossary unless marked otherwise. All objects found and named by Luke Bradford
unless otherwise noted. General CA terms are taken from Stephen Silver’s Life Lexicon. Each pattern runs live; click to pause,
or copy its RLE into <a href="https://golly.sourceforge.io/">Golly</a> (rule <code>B2/S0</code>).</p>
</div>
<div class="toolbar" role="search">
<input type="search" id="q" placeholder="Search the glossary…" aria-label="Search the glossary">
{chips}
</div>
<div class="entries" id="entries">
{''.join(cards)}
</div>
<script>
(function(){{
  const q=document.getElementById('q'), chips=[...document.querySelectorAll('.chip')];
  let kind=null;
  function apply(){{
    const t=q.value.trim().toLowerCase();
    document.querySelectorAll('.entry').forEach(el=>{{
      const ok=(!kind||el.dataset.kind===kind)&&(!t||el.dataset.search.includes(t));
      el.hidden=!ok;
    }});
    document.querySelectorAll('[data-letter]').forEach(el=>{{
      let n=el.nextElementSibling, any=false;
      while(n&&!n.hasAttribute('data-letter')){{ if(!n.hidden) any=true; n=n.nextElementSibling; }}
      el.hidden=!any;
    }});
  }}
  q.addEventListener('input',apply);
  chips.forEach(c=>c.addEventListener('click',()=>{{
    kind = kind===c.dataset.kind ? null : c.dataset.kind;
    chips.forEach(x=>x.setAttribute('aria-pressed', String(x.dataset.kind===kind)));
    apply();
  }}));
}})();
</script>
"""
    page("glossary.html", "Glossary", body, "Glossary of every named object in the Live Free or Die cellular automaton, with live patterns.")

def build_tables():
    parts = ["<h1>Object tables</h1>",
             '<div class="prose"><p class="lede">Statistics for every known oscillator, spaceship, puffer, tagalong and pre-spark, '
             'as of June 2009.</p><p class="muted">For objects with multiple or infinite iterations, tables refer to the smallest. '
             'Names link to the glossary. The legend explains the abbreviations, including engine address (EA) notation, '
             'Luke’s shorthand for describing the engine of any lightspeed ship or puffer.</p></div>']
    tables = TABLES["object tables.htm"]
    for t in tables:
        parts.append(f'<h2 id="{slug(t["caption"])}">{esc(t["caption"])}</h2>')
        parts.append(table_html(t["rows"], SLUGS))
    parts.append("""<h2 id="legend">Legend</h2>
<div class="prose">
<h3>Discovery method (Disc)</h3>
<p>N – Natural · C – Constructed · ET – Explosion tracking · WLS – WinLifeSearch program · J.S. – Jason Summers’ Seeds collection ·
D.E. – David Eppstein · J.B. – Josh Ball · PSF – Pre-spark-find program</p>
<h3>Symmetry (Sym)</h3>
<p>O – Eight-way · D – Two-way diagonal · / – Four-way diagonal · S – Two-way rotational · M – Two-way mirror · I – Four-way mirror · G – Glide symmetric</p>
<h3>Engine resultant (ER)</h3>
<p>EaP – Engine as phase · EaI – Engine as initial state · SER – Strictly engine resultant · LER – Loosely engine resultant</p>
<h3>Engine address (EA)</h3>
<p>Numerals correspond to a wing of length n.<br>
<code>_</code> nose with both adjacent wings attached · <code>–</code> nose with both adjacent wings floating ·
<code>/</code> nose with left wing attached and right wing floating · <code>\\</code> nose with left wing floating and right wing attached ·
<code>&amp;</code> a wing not adjacent to a nose, but appended to another wing as in a dot puffer ·
<code>.</code> space of one pixel, with nose on other side at the same vertical location ·
<code>,</code> space of one pixel, with nose on other side displaced down one pixel ·
<code>‘</code> space of one pixel, with nose on other side displaced up one pixel ·
<code>*</code> additional engine element that cannot be described in EA notation</p>
<h3>Pre-spark mechanism</h3>
<p><em>mechanism 1</em> – next generation of a particular mechanism · (n) – unnamed mechanism which is the smallest pre-spark of duration n ·
[n] – unnamed mechanism which is not the smallest pre-spark of duration n, but used in other mechanisms ·
<em>mechanism + mechanism</em> – first mechanism sets off a chain reaction in the second · HSn – hot sand mechanism of n cells</p>
</div>""")
    page("tables.html", "Object tables", "\n".join(parts), "Tables of oscillators, spaceships and puffers in Live Free or Die.")

def build_periods():
    ts = TABLES["period.htm"]
    titles = ["Oscillators", "Puffers", "Spaceships"]
    parts = ["<h1>Period explorations</h1>",
             '<div class="prose"><p class="lede">The smallest known object of each period, as of June 2009.</p>'
             '<p class="muted">[…] denotes a flotilla. Cells is the minimum (oscillators, spaceships) or initial (puffers) population. '
             'For all of these in one file, see <a href="files.html#period-examples-digits">Period examples (digits)</a>.</p></div>']
    for title, t in zip(titles, ts):
        rows = t["rows"]
        rows[0] = ["Period", title[:-1], "Cells"]
        parts.append(f"<h2>{title}</h2>")
        parts.append(table_html(rows, SLUGS))
    if LATER.get("periods_note"):
        parts.append(f'<div class="note prose">{LATER["periods_note"]}</div>')
    page("periods.html", "Period explorations", "\n".join(parts))

ITERATIONS = [
    ("Accidental ships and puffers", "accidental puffer iterations.jpg", "accidental ship"),
    ("Dot ship and dot puffers", "dot puffer iterations.jpg", "dot puffer"),
    ("Dotset ship and dotset puffers", "dotset puffer iterations.jpg", "dotset ship"),
    ("Dual robot puffers", "dual robot puffer iterations.jpg", "dual robot puffer"),
    ("Ferry puffers", "ferry puffer iterations.jpg", "ferry puffer"),
    ("Oof puffers", "oof puffer iterations.jpg", "oof puffer"),
    ("Robot ships and robot puffers", "robot puffer iterations.jpg", "robot puffer"),
    ("Sun cars", "sun car iterations.jpg", "sun car"),
    ("Sun ship and sun puffers", "sun puffer iterations.jpg", "sun puffer"),
    ("Sun trailers", "sun trailer iterations.jpg", "sun trailer"),
    ("Sunset ship and sunset puffers", "sunset puffer iterations.jpg", "sunset puffer"),
    ("Swamp puffers", "swamp puffer iterations.jpg", "swamp puffer"),
    ("Tick puffers", "tick puffer iterations.jpg", "tick puffer"),
    ("Ugly puffers", "ugly puffer iterations.jpg", "ugly puffer"),
]

def build_iterations():
    by = {e["name"]: e for e in ENTRIES}
    parts = ["<h1>Iteration guides</h1>", """<div class="prose">
<p class="lede">Possible iterations of the extensible puffer and spaceship families: which wing lengths work, and which must be anchored.</p>
<p><strong>Key.</strong> Black cells are necessary in any iteration (the minimum length of extensible wings is marked by the first colored cell).
<span style="color:#2a6fdb">Blue</span> cells mark wing lengths which cannot be anchored.
<span style="color:#2f9a3b">Green</span> cells mark wing lengths which can be anchored or non-anchored.
<span style="color:#c8322a">Red</span> cells mark wing lengths which must be anchored.
Black circles mark wing lengths that produce no output if non-anchored, in objects that can be spaceships or eaters.
Gray cells are caused by phase offsets in wings; wings should be extended and anchored in their empty phase, which may not be the phase shown.
To see how the phase offsets work, consult the smallest iteration.</p>
<p class="muted">The diagrams are the original July 2008 images, enlarged. Next to each is the smallest iteration, running live.</p>
</div>"""]
    for title, img, ref in ITERATIONS:
        e = by.get(ref)
        parts.append(f'<h2 id="{slug(title)}">{esc(title)}</h2><div class="iter">'
                     f'<img class="iter-img" src="img/iterations/{esc(img)}" alt="Iteration diagram for {esc(title)}" loading="lazy">'
                     f'<div>{player(e["rle"], ref, height=160, loop=80) if e else ""}'
                     f'<p class="muted">See <a href="glossary.html#{slug(ref)}">{esc(ref)}</a> in the glossary.</p></div></div>')
    parts.append('<h2 id="tables">Iteration tables (May 2008)</h2><div class="prose"><p class="muted">The earlier, tabular form of the same information, '
                 'which the diagrams replaced. X – non-anchored puffer · O – non-anchored spaceship · r – right-anchored puffer · '
                 'l – left-anchored puffer · b – bi-anchored puffer. Rows are the left (upper) wing length; columns the right (lower).</p></div>')
    for t in TABLES["tables.htm"][1:]:
        parts.append(f'<h3>{esc(t["caption"])}</h3>')
        parts.append(table_html(t["rows"]))
    page("iterations.html", "Iteration guides", "\n".join(parts))

def build_challenges():
    later = LATER.get("challenges_html", "")
    body = f"""<h1>Challenges</h1>
<div class="prose">
<p class="lede">To anyone who discovers any of the following, I can guarantee eternal gratitude, naming rights, and a place of glory on this web site.</p>
<p class="muted">Only broad categories that had not been discovered are shown, and any discoveries are gladly accepted. Bold entries are the most significant.
This is the list as it stood in July 2008. Several have since been solved; see the notes below.</p>
<h2>General objects</h2>
<ul>
<li>Objects of undiscovered periods: p10, p11, p13, p14, p15, etc.</li>
<li>Oscillators of undiscovered periods: p7, p8, p9, p16, p24, etc.</li>
<li>Spaceships or puffers of undiscovered periods: p2, p7, p9, p28, etc.</li>
<li><strong>Guns</strong></li>
<li><strong>Reusable reflectors for moons or other spaceships</strong></li>
<li>Eaters for spaceships other than moons</li>
<li><strong>Signal circuitry analogous to Herschel conduits in Conway’s Life</strong></li>
<li>“Clean” (i.e. non-chaotic) breeders or spacefillers</li>
<li>“Knightships” or puffers with similar movement</li>
<li>Spaceships or puffers of unknown speeds: c/3, c/4, c/6, etc.</li>
</ul>
<h2>Live Free or Die-specific objects</h2>
<ul>
<li>Puffers that produce rare objects: levers, Cecil B. DeMilles, etc.</li>
<li>Undiscovered logic gates built with “hot sand” (see <a href="files.html#logic-gates">Logic gates</a> for known gates)</li>
<li>Moon syntheses for significant objects (preferably to be usable with rakes)</li>
<li>New implementations of anchor track flotilla technology</li>
<li>Stabilizers for wicks and other oscillator components that function identically in the Seeds universe</li>
<li>Dot-constructed technology, i.e. stable eaters, reflectors etc.</li>
</ul>
<h2>Since then</h2>
{later}
</div>"""
    page("challenges.html", "Challenges", body)

def build_news():
    items = []
    for n in NEWS:
        items.append((n["date"], n["paras"], "site", None))
    for n in LATER.get("news", []):
        items.append((n["date"], n["paras"], n.get("source", ""), n.get("rle")))
    items.sort(key=lambda x: x[0], reverse=True)
    out, era = [], None
    for date, paras, src, rle in items:
        y = date[:4]
        if y != era:
            era = y
            out.append(f'</ul><h2 class="era" id="y{y}">{y}</h2><ul class="timeline">')
        ps = "".join(f"<p>{p if src != 'site' else esc(p)}</p>" for p in paras)
        tag = f' <span class="tag">{esc(src)}</span>' if src != "site" else ""
        pl = player(rle, re.sub("<[^>]+>", "", paras[0])[:80], height=200, loop=200) if rle else ""
        out.append(f'<li><time datetime="{date}">{date}</time><div>{ps}{tag}{pl}</div></li>')
    body = ('<h1>News</h1><div class="prose"><p class="lede">A dated record of discoveries.</p>'
            '<p class="muted">Entries from December 2007 to September 2009 are Luke’s original News page, verbatim. '
            'Later entries, marked with their source, were reconstructed for this restoration from the ConwayLife forum, '
            'archived wiki pages, and correspondence.</p></div>'
            '<ul class="timeline">' + "".join(out) + "</ul>")
    body = body.replace('<ul class="timeline"></ul>', "")
    page("news.html", "News", body)

FILE_DESCRIPTIONS = {}

def parse_files_page():
    """Name/description pairs from the 2008 Files page, in original order."""
    import subprocess
    text = subprocess.run(["textutil", "-convert", "txt", "-stdout", str(ARCHIVE / "verizon-site/files.htm")],
                          capture_output=True, text=True).stdout
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    lines = lines[2:-1]  # drop title, intro, and footer
    return list(zip(lines[0::2], lines[1::2]))

EXTRA_FILES = [
    ("Live Free or Die summarized", "Live Free or Die summarized.rle", "A summary collection of the most significant objects (June 2009). Not linked from the 2008 Files page."),
    ("Forge puffers", "Forge puffers.rle", "Both known forge puffers, including the iteration with the 14-cell wing (June 2009)."),
    ("Anchor track processor experiments", "Anchor track processor experiments.rle", "Experiments with anchor tracks as signal processors (August 2008)."),
    ("p1 experiments", "p1 experiments.rle", "Experiments with moons, the only p1 spaceship (July 2008)."),
    ("Search template", "Search template.rle", "Template used with the search programs (September 2008)."),
    ("Hot sand", "Hot sand.rle", "Early collection of hot sand fuses (February 2008), later merged into Fuses."),
    ("Iterations", "Iterations.rle", "Early collection of puffer iterations (March 2008)."),
    ("Double moon rake experiment", "Double moon rake experiment.rle", "A double moon rake built from free rakes (February 2008)."),
]

def build_files():
    files_out = OUT / "files"
    files_out.mkdir(exist_ok=True)
    rle_dir = ARCHIVE / "rle-files"
    listed = parse_files_page()
    rows = []
    def add(name, fname, desc, section):
        src = rle_dir / fname
        if not src.exists():
            rows.append((section, name, None, desc, None))
            return
        text = src.read_text(errors="replace")
        cells = load_pattern(text)
        out_name = Path(fname).stem + ".rle"
        if src.suffix == ".rle":
            shutil.copy(src, files_out / out_name)
        else:
            (files_out / out_name).write_text(to_rle(cells) + "\n")
            shutil.copy(src, files_out / Path(fname).name)
        rows.append((section, name, out_name, desc, len(cells)))
    for name, desc in listed:
        add(name, name + ".rle", desc, "listed")
    add("Period examples (digits)", "Period examples (digits).rle",
        "The smallest known object of each period, arranged by digit (March 2008 version; linked from Period Explorations).", "listed")
    for name, fname, desc in EXTRA_FILES:
        add(name, fname, desc, "extra")
    for f in LATER.get("files", []):
        rows.append(("later", f["name"], f.get("file"), f["desc"], f.get("pop")))
        if f.get("file") and (DATA / "later-files" / f["file"]).exists():
            shutil.copy(DATA / "later-files" / f["file"], files_out / f["file"])
    def render(section):
        out = ['<div class="files">']
        for sec, name, fn, desc, pop in rows:
            if sec != section:
                continue
            if fn:
                from urllib.parse import quote
                href = "files/" + quote(fn)
                acts = (f'<a href="viewer.html?f={quote(quote(fn))}">View</a><a href="{href}" download>Download RLE</a>'
                        f'<span class="muted">{pop:,} cells</span>' if pop is not None else f'<a href="{href}" download>Download</a>')
            else:
                acts = '<span class="status lost">not recovered</span>'
            out.append(f'<div class="file" id="{slug(name)}"><div class="name">{esc(name)}</div>'
                       f'<div class="desc">{esc(desc)}</div><div class="actions">{acts}</div></div>')
        out.append("</div>")
        return "\n".join(out)
    body = f"""<h1>Files</h1>
<div class="prose">
<p class="lede">Original files created in Golly containing explorations, experiments, and collections of objects.</p>
<p class="muted">Each file is the latest surviving version (most from 2008–2010). <em>View</em> opens it in the in-browser player;
for the largest files (the p192 backward free rake is about 30,000 cells) <a href="https://golly.sourceforge.io/">Golly</a> is much faster.</p>
</div>
<h2>Files page (2008)</h2>
{render("listed")}
<h2>Other files from the site folder</h2>
<div class="prose"><p class="muted">These were uploaded to the site or kept alongside it but weren’t on the Files page, including the original files of Josh Ball’s discoveries as he sent them.</p></div>
{render("extra")}
{"<h2>Later files</h2>" + render("later") if any(r[0] == "later" for r in rows) else ""}
"""
    page("files.html", "Files", body)

def build_viewer():
    body = """<h1 id="vt">Viewer</h1>
<p class="muted" id="vs">Loading…</p>
<div id="vp"></div>
<p class="muted">Tip: large flotillas take many generations to show their behavior. Scroll to zoom, drag to pan, ⏭ to step. Or paste the RLE into Golly with rule B2/S0.</p>
<script>
(async function(){
  const f = new URLSearchParams(location.search).get('f');
  if(!f){ document.getElementById('vs').textContent='No file given.'; return; }
  const name = decodeURIComponent(f);
  document.getElementById('vt').textContent = name.replace(/\\.rle$/,'');
  document.title = name + ' · Live Free or Die Universe';
  try {
    const txt = await (await fetch('files/' + encodeURIComponent(name))).text();
    const el = document.createElement('div');
    el.className='pattern'; el.dataset.rle=txt; el.dataset.height=String(Math.min(640, Math.max(320, innerHeight-260)));
    el.dataset.autoplay='false'; el.dataset.speed='20'; el.dataset.interactive='true';
    document.getElementById('vp').appendChild(el);
    new LFoD.Player(el);
    document.getElementById('vs').innerHTML = '<a href="files/'+encodeURIComponent(name)+'" download>Download RLE</a> · <a href="files.html">All files</a>';
  } catch(e){ document.getElementById('vs').textContent='Could not load file.'; }
})();
</script>"""
    page("viewer.html", "Viewer", body)

def build_index():
    by = {e["name"]: e for e in ENTRIES}
    feat = [("free ship", 48), ("monster", 57), ("key ship", 40), ("radar puffer", 120)]
    tiles = "".join(f'<div>{player(by[n]["rle"], n, height=150, loop=l)}<p class="muted" style="margin:.3em 0 0;font-size:.85rem">'
                    f'<a href="glossary.html#{slug(n)}">{esc(n)}</a></p></div>' for n, l in feat if n in by)
    counts = {k: sum(1 for e in ENTRIES if e["kind"] == k) for k in KIND_LABELS}
    body = f"""
<div class="hero">
<div class="prose">
<h1>Live Free or Die Universe</h1>
<p class="lede">An exploration of the Moore neighborhood s0/b2 cellular automaton.</p>
<p>Live Free or Die, like Conway’s Game of Life, is a two-dimensional two-state Moore neighborhood cellular automaton. In other words,
it is an infinite grid of cells which can either be live or dead. Given an initial configuration of cells, each cell applies simple rules
based on its eight neighboring cells to determine whether its state will change. <strong>A live cell will die if it has any neighbors,
and a dead cell will come to life if it has exactly two neighbors.</strong> Every cell in the grid changes at the same instant. As the pattern
evolves through consecutive generations, it exhibits emergent and often beautiful behavior.</p>
</div>
<div>{player(by["monster puffer"]["rle"], "monster puffer", 260, 200) if by.get("monster puffer", {}).get("rle") else player(by["radar puffer"]["rle"], "radar puffer", 260, 160)}
<p class="muted" style="font-size:.85rem;margin-top:.4em">A p12 anchor track flotilla: the <a href="glossary.html#radar-puffer">radar puffer</a>.</p></div>
</div>

<div class="cards">
<a class="card" href="news.html"><strong>News</strong><span>Dated list of discoveries and explorations</span></a>
<a class="card" href="glossary.html"><strong>Glossary</strong><span>{len(ENTRIES)} terms and objects, {counts["oscillator"]} oscillators, {counts["spaceship"]} spaceships, {counts["puffer"]} puffers and rakes</span></a>
<a class="card" href="tables.html"><strong>Object tables</strong><span>Statistics for each object or its smallest iteration</span></a>
<a class="card" href="periods.html"><strong>Period explorations</strong><span>The smallest oscillator, puffer and spaceship for each known period</span></a>
<a class="card" href="iterations.html"><strong>Iteration guides</strong><span>Possible iterations of puffer and spaceship families</span></a>
<a class="card" href="challenges.html"><strong>Challenges</strong><span>Objects nobody had found yet</span></a>
<a class="card" href="files.html"><strong>Files</strong><span>Run-length encoded collections and explorations</span></a>
<a class="card" href="restoration.html"><strong>About this restoration</strong><span>What was recovered, from where, and what is lost</span></a>
</div>

<div class="prose">
<h2>A short explanation</h2>
<p>I found Live Free or Die by accident while messing around with simple variations of Seeds (/b2). It is so named because the only cells
that survive between generations are free of neighbors. What first intrigued me about it were the extremely common free ship, the double
and 2-2 dot puffers, and the key ship.</p>
</div>
<div class="cards">{tiles}</div>
<div class="prose">
<p>Live Free or Die is a small, fast, intuitive universe, in which most objects are more reminiscent of machinery than of the organic fluidity
that is characteristic of Conway’s Life (s23/b3). It is full of readily visible patterns, and flotillas and other large projects are easy to
assemble. The explosive nature of the rule makes it receptive to the naturalistic study of mobile objects. It has oscillators of each period
and spaceships of each speed that is possible in the Seeds universe, along with objects that are impossible or undiscovered in Seeds: stable
fuses, oscillators with stators, and oscillators and spaceships of indefinitely large period. In Live Free or Die, unlike Seeds, it seems that
there is the potential to create anything that is possible in Life.</p>
<h2>Disclaimer</h2>
<p>I am not a mathematician. The interest I have taken in cellular automata is purely aesthetic, and I do not profess to know any of the
complexities behind this universe. The methods I have used to find and describe objects are primitive at best, so accept my apologies if
this site is incomplete, misleading, or confusing in places.</p>
<p class="muted">— Luke Bradford. Text from the 2009 home page.</p>
<h2>Contributors</h2>
<p>Most objects were found by Luke Bradford. Major contributions came from <strong>Josh Ball</strong> (dozens of oscillators, ships, puffers and rakes, 2008–2009),
<strong>David Eppstein</strong> (the first slower-than-light ship), <strong>Jason Summers</strong> (oscillators from his Seeds collection) and
<strong>Brian Prentice</strong> (anchor track flotilla explorations){LATER.get("contributors_html", "")}.</p>
</div>
"""
    page("index.html", "Home", body)

def build_restoration():
    page("restoration.html", "About this restoration", (DATA / "restoration.html").read_text(),
         "How the Live Free or Die Universe site was recovered, and what remains lost.")

def copy_assets():
    img = OUT / "img"
    (img / "glossary").mkdir(parents=True, exist_ok=True)
    (img / "iterations").mkdir(parents=True, exist_ok=True)
    for p in (ARCHIVE / "verizon-site/glossary_files").glob("*.jpg"):
        shutil.copy(p, img / "glossary" / p.name)
    for p in (ARCHIVE / "images/iterations").glob("*.jpg"):
        shutil.copy(p, img / "iterations" / p.name)
    shutil.copy(ARCHIVE / "verizon-site/icon.png", img / "icon.png")
    (OUT / ".nojekyll").write_text("")

if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    copy_assets()
    build_index(); build_news(); build_glossary(); build_tables(); build_periods()
    build_iterations(); build_challenges(); build_files(); build_viewer()
    if (DATA / "restoration.html").exists():
        build_restoration()
    print("built", len(ENTRIES), "glossary entries")
