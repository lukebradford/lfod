"""Build the static GitHub Pages site in docs/ from data/ and archive/.

Usage: python3 tools/build.py   (standard library only)
"""
import functools, html, json, re, shutil, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from lfod import load_pattern, to_rle, classify, parse_rle, step, object_stats, front_period, symmetry_code  # noqa: E402

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
ITER_GRIDS = load("iterations.json", {})

NAV = [
    ("index.html", "Home"), ("news.html", "News"), ("glossary.html", "Glossary"), ("periods.html", "Periods"),
    ("challenges.html", "Challenges"), ("files.html", "Files"), ("restoration.html", "About this restoration"),
]
# Reference pages: linked from the footer of every page and from the glossary, not the header or home page.
REFERENCE = [("tables.html", "Object tables"), ("iterations.html", "Iteration guides")]

def slug(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower().replace("’", "").replace("'", "")).strip("-")

def asset_version():
    import hashlib
    h = hashlib.sha1()
    for name in ("style.css", "lfod.js", "w110.js"):
        h.update((OUT / "assets" / name).read_bytes())
    return h.hexdigest()[:8]

def page(filename, title, body, description=""):
    v = asset_version()
    nav = "".join(f'<a href="{h}"{" class=\"active\"" if h == filename else ""}>{esc(t)}</a>' for h, t in NAV)
    ref = " · ".join(f'<a href="{h}"{" aria-current=\"page\"" if h == filename else ""}>{esc(t)}</a>' for h, t in REFERENCE)
    # Home has the large title in its hero, so the small one in the header is left out there.
    is_home = filename == "index.html"
    brand = "" if is_home else '<a class="brand" href="index.html">Live Free or Die Universe</a>\n'
    home = " home" if is_home else ""
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
<header class="site-header{home}"><div class="inner">
{brand}<nav class="main" aria-label="Main">{nav}</nav>
</div></header>
<main>
{body}
</main>
<footer class="site-footer"><div class="inner">
<p class="ref">{ref}</p>
Objects found and named by Luke Bradford unless otherwise credited. Originally published at
mysite.verizon.net/live_free (2007–2012) and lfod.wikispaces.com (2013–2018); restored 2026.
</div></footer>
</body>
</html>
"""
    (OUT / filename).write_text(sup_tags(doc))

SUPERSCRIPTS = "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁽⁾ⁿ"
NORMAL = str.maketrans(SUPERSCRIPTS, "0123456789+-()n")

def sup_tags(doc):
    """Show exponents stored as Unicode superscripts (2ⁿ) with <sup> outside tags, in the site's own font."""
    run = re.compile(f"[{SUPERSCRIPTS}]+")
    return "".join(part if part.startswith("<") else run.sub(lambda m: f"<sup>{m.group(0).translate(NORMAL)}</sup>", part)
                   for part in re.split(r"(<[^>]+>)", doc))

MATH_OPS = {"-": "−", "*": "×"}

def mathml(expr):
    """Typeset a formula such as “4 × 2^(n+1) − 4” as inline MathML: numbers upright, variables italic,
    true minus and times signs, and ^ for a superscript (a parenthesized exponent loses its parentheses)."""
    toks = re.findall(r"\d+|[a-z]|[-+−×*()^]", expr)
    pos = 0

    def atom():
        nonlocal pos
        t = toks[pos]; pos += 1
        if t == "(":
            inner = seq(")"); pos += 1
            return inner, True
        if t.isdigit():
            return f"<mn>{t}</mn>", False
        if t.isalpha():
            return f"<mi>{t}</mi>", False
        return f"<mo>{MATH_OPS.get(t, t)}</mo>", False

    def seq(end=None):
        nonlocal pos
        out = []
        while pos < len(toks) and toks[pos] != end:
            a, grouped = atom()
            if pos < len(toks) and toks[pos] == "^":
                pos += 1
                e, _ = atom()
                base = f"<mo>(</mo>{a}<mo>)</mo>" if grouped else a
                out.append(f"<msup><mrow>{base}</mrow><mrow>{e}</mrow></msup>")
            else:
                out.append(f"<mo>(</mo>{a}<mo>)</mo>" if grouped else a)
        return "".join(out)

    return f"<math>{seq()}</math>"

def is_formula(text):
    return bool(re.search(r"[a-z^]", text)) and not re.search(r"[a-z]{2}", text)

@functools.cache
def behaviour(rle, gens):
    """Whether a pattern dies out within `gens` generations, and whether it travels or grows:
    its bounding box, accumulated over generations, is still expanding after 24 of them."""
    cells = parse_rle(rle)
    if not cells:
        return False, False
    xs = [x for x, _ in cells]; ys = [y for _, y in cells]
    box, settled = [min(xs), min(ys), max(xs), max(ys)], None
    for g in range(1, max(gens, 48) + 1):
        cells = step(cells)
        if not cells:
            return g <= gens, False
        for x, y in cells:
            box = [min(box[0], x), min(box[1], y), max(box[2], x), max(box[3], y)]
        if g == 24:
            settled = list(box)
        if g >= 48 and (len(cells) > 400 or g >= gens):
            break  # large or long-lived; it isn't about to vanish
    return False, settled is not None and box != settled

def player(rle, label, height=170, loop=0, speed=8, autoplay=True):
    attrs = f'data-rle="{esc(rle)}" data-label="{esc(label)}" data-height="{height}" data-speed="{speed}"'
    if loop:
        attrs += f' data-loop="{loop}"'
    dies, moves = behaviour(rle, loop or 200)
    if moves:
        attrs += ' data-moves="true"'
    if dies or not autoplay:
        attrs += ' data-autoplay="false"'
    return f'<div class="pattern" {attrs}></div>'

TABLE_RENAMES = {"Giraffe": "Giraffe ship"}  # 2009 table names that differ from the glossary's

def table_html(rows, link_names=None, header=True, sortable=False):
    out = ['<div class="table-wrap"><table class="sortable">' if sortable else '<div class="table-wrap"><table>']
    for i, row in enumerate(rows):
        tag = "th" if header and i == 0 else "td"
        cells = []
        for j, c in enumerate(row):
            cls = ' class="num"' if tag == "td" and re.fullmatch(r"[-+]?[\d.]+", c) else ""
            if tag == "td" and j == 0:
                c = TABLE_RENAMES.get(c, c)
            text = esc(c)
            target = slug(c)
            if link_names and tag == "td" and j == 0 and target in link_names:
                text = f'<a href="glossary.html#{target}">{text}</a>'
            elif sortable and tag == "th":
                text = f'<button type="button" class="sort">{text}</button>'
            cells.append(f"<{tag}{cls}>{text}</{tag}>")
        tr = "<tr>" + "".join(cells) + "</tr>"
        if header and i == 0:
            tr = f"<thead>{tr}</thead><tbody>"
        out.append(tr)
    out.append("</tbody></table></div>" if header and rows else "</table></div>")
    return "\n".join(out)

# ---------------------------------------------------------------- glossary data

KIND_LABELS = {
    "oscillator": "Oscillators", "spaceship": "Spaceships", "puffer": "Puffers, rakes & guns",
    "tagalong": "Tagalongs & trailers", "reaction": "Sparks, pre-sparks & reactions", "term": "Terms",
}
TERM_NAMES = {"anchored", "bi-anchored", "left-anchored", "right-anchored", "attached wing", "floating wing",
              "boxy", "dusty", "empty", "heavy", "engine", "engine horn", "flame", "horn", "nose", "wing",
              "wing notation", "W-winged", "phase type", "anchor track flotilla", "stack"}

TAG_OVERRIDES = {"moon laser": "Gun", "sawtooth": "Sawtooth"}

def kind_of(e):
    if e["name"] in TERM_NAMES or not e.get("rle"):
        if e["name"] in ("monster puffer", "anchor biter puffer", "anchor eater ship"):
            return "puffer" if "puffer" in e["name"] else "spaceship"
        return "term"
    d = e["desc"].lower()
    m = re.search(r"\b(oscillator|spaceship|puffer|rake|trailer|tagalong|pre-spark|spark|reaction|fuse|predecessor)s?\b", d)
    w = m.group(1) if m else "term"
    if e["name"] in ("bomb", "shrinker", "sawtooth"):
        return "reaction"
    if e["name"] == "moon laser":
        return "puffer"
    if e["name"] in ("dot",):
        return "oscillator"
    if e["name"] in ("checker",):
        return "oscillator"
    if e["name"] in ("anchor biter", "anchor eater", "half anchor eater", "half anchor biter", "dual infinite anchor track"):
        return "tagalong"
    return {"rake": "puffer", "trailer": "tagalong", "pre-spark": "reaction", "spark": "reaction",
            "fuse": "reaction", "predecessor": "reaction"}.get(w, w)

# Corrections to the original text: claims that were wrong when written, typos, and a stray footnote mark.
EDITS = {
    "hex ship": [("the only known p6 object other than", "the only known p6 spaceship other than")],
    "short free ship": [("This is the smallest known p6 object.", "This is the smallest known p6 spaceship.")],
    "tricycle rake": [(", which is the only known backward rake and clean moon rake, and one of few known p3 objects",
                       ", which is one of few known p3 objects")],
    "metronome puffer": [("plus-like reactions occur follow behind", "plus-like reactions follow behind")],
    "metronome ship": [("plus-like reactions occur follow behind", "plus-like reactions follow behind")],
    "anchor track": [("(mod 2s + 1). (1)", "(mod 2s + 1).")],
    "period": [(", making p3 the shortest period with known puffers and rakes.", ".")],
    "eclipse puffer": [("with an initial population of 13 cells.",
                        "with an initial population of 13 cells, which is the smallest known p8 puffer.")],
}
# Claims in the 2009 glossary that were true then but that later finds overtook (the wiki's are in make_later.py).
NOTES = {
    "hex ship": 'Michael Simkin found another p6 spaceship, the c/3 <a href="glossary.html#wasp-ship">wasp ship</a>, in October 2014.',
    "long arrow puffer": 'It and the arrow puffer are no longer the only p9 objects: Arie Paap found a <a href="news.html#y2015">p9 dot puffer</a> '
                         'in February 2015, and AforAmpere posted another <a href="news.html#y2021">p9 puffer</a> in 2021.',
    "flip-flop rake": 'It is no longer the only p4 rake: Josh Ball’s <a href="news.html#y2014">c p4 side rake</a> (July 2014), '
                      'the c/2 <a href="glossary.html#buffalo-rake">buffalo rake</a> (Arie Paap, August 2014) and '
                      '<a href="glossary.html#horned-rake">horned rake</a> (Nora Brown, December 2014), and the pocket rake and '
                      'zipper rake on the later wiki are all p4 rakes.',
}

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
            x = next(x for x in entries if x["name"].lower() == e["name"].lower())
            x.update(desc=e["desc"], source=e["source"], url=e.get("url"), captured=e.get("captured"),
                     paras=e.get("paras"), rles=e.get("rles"), note=e.get("note"))
            if e.get("credit"):
                x["credit"] = e["credit"]
            if e.get("rle"):
                x["rle"] = e["rle"]
                x.pop("reconstructed", None)
        else:
            entries.append(dict(e))
    for e in entries:
        for old, new in EDITS.get(e["name"], []):
            assert old in e["desc"], (e["name"], old)
            e["desc"] = e["desc"].replace(old, new)
            if e.get("paras"):
                e["paras"] = [q.replace(old, new) for q in e["paras"]]
        if e["name"] in NOTES:
            assert not e.get("note"), e["name"]
            e["note"] = NOTES[e["name"]]
        e["kind"] = e.get("kind") or kind_of(e)
        e["slug"] = slug(e["name"])
    entries.sort(key=lambda e: e["name"].lower().lstrip("’'"))
    return entries

ENTRIES = all_entries()
SLUGS = {e["slug"] for e in ENTRIES}

ALIASES = {"anchor nibbler": "half anchor eater"}  # other names that glossary text uses for an entry

GENERIC = {"cell", "generation", "period", "oscillator", "spaceship", "puffer", "spark", "rake", "trailer",
           "tagalong", "stack", "still life", "rotor", "stator", "phoenix", "explosive", "wing", "engine", "nose",
           "horn", "flame", "heavy", "empty", "boxy", "dusty", "phase type"}

SHORT_LINKS = {"still-life": {"dot"}}  # names of three letters or fewer, which autolink skips, to link in particular entries

def autolink(text, self_slug=None, prefix="#", used=None):
    """Link the first mention of each other glossary entry (longest names first)."""
    names = sorted({e["name"] for e in ENTRIES if len(e["name"]) > 3 and e["slug"] != self_slug
                    and e["name"] not in GENERIC} | {a for a, t in ALIASES.items() if slug(t) != self_slug}
                   | SHORT_LINKS.get(self_slug, set()),
                   key=len, reverse=True)
    if not names:
        return esc(text)
    # Either apostrophe matches either: the wiki writes “Eppstein's slow ship”, the glossary “Eppstein’s slow ship”.
    alts = "|".join(re.escape(n).replace("’", "['’]") for n in names)
    pat = re.compile(r"\b(" + alts + r")(s|es)?\b", re.I)
    out, last, used = [], 0, set() if used is None else used
    for m in pat.finditer(text):
        s = slug(ALIASES.get(m.group(1).lower(), m.group(1)))
        out.append(esc(text[last:m.start()]))
        if s in used or s not in SLUGS:
            out.append(esc(m.group(0)))
        else:
            used.add(s)
            out.append(f'<a href="{prefix}{s}">{esc(m.group(0))}</a>')
        last = m.end()
    out.append(esc(text[last:]))
    return "".join(out)

def autolink_html(markup, prefix="#", used=None):
    """autolink for HTML: link mentions in text outside tags and existing links."""
    used = set() if used is None else used
    out, depth = [], 0
    for part in re.split(r"(<[^>]+>)", markup):
        if part.startswith("<"):
            if re.match(r"<a\b", part):
                depth += 1
            elif part.startswith("</a"):
                depth -= 1
            out.append(part)
        elif depth or not part:
            out.append(part)
        else:
            out.append(autolink(html.unescape(part), prefix=prefix, used=used))
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

def wiki_body(e, h):
    """Wiki pages interleave text and patterns: each pattern follows the paragraph that introduces it.
    Short unpunctuated paragraphs are subsection names (e.g. the three kinds of anchor stack)."""
    rles = list(e.get("rles") or ([e["rle"]] if e.get("rle") else []))
    out = []
    for para in e["paras"]:
        if len(para) < 40 and not para.rstrip().endswith((".", ":", ")")):
            out.append(f'<h4>{esc(para)}</h4>')
            continue
        out.append(f'<p>{autolink(para, e["slug"])}</p>')
        if rles and re.search(r"\b(following|shown below|below is|as below)\b|\bbelow[.:]\s*$", para, re.I):
            out.append(player(rles.pop(0), e["name"], height=h, loop=loop_for(e)))
    for r in rles:
        out.append(player(r, e["name"], height=h, loop=loop_for(e)))
    return out

# ---------------------------------------------------------------- pages

ITER_REFS = {"twin puffer": "robot puffer"}  # entries that point at another family's diagram

def iteration_link(html_text, name):
    """Lower-case the glossary's “see Iteration Guides” and link its first mention to the entry's own
    family diagram where there is one."""
    pat = re.compile(r"Iteration [Gg]uides")
    if not pat.search(html_text):
        return html_text
    n = ITER_REFS.get(name.lower(), name.lower())
    titles = [t for t, _, ref in ITERATIONS if ref == n] or [t for t, _, _ in ITERATIONS if n in t.lower()] \
        or [t for t, _, _ in ITERATIONS if (n.split()[0] + " ") in t.lower() + " "]
    href = f"iterations.html#{slug(titles[0])}" if titles else "iterations.html"
    html_text = pat.sub(f'<a href="{href}">iteration guides</a>', html_text, count=1)
    return pat.sub("iteration guides", html_text)

LIFEWIKI = re.compile(r"\b(Gun|Oscillator|Period|Puffer|Rake|Spaceship|Speed|Still life) on LifeWiki\b")
FILES_REF = re.compile(r'(?:<a href="#[^"]*">)?(Metronome puffers|Oscillators|Output examples)(?:</a>)? in Files\b')
# Other mentions of collections that are on the Files page.
COLLECTIONS = [("download the Live Free or Die collection", "files.html#later-files", "Live Free or Die collection"),
               ("Nora Brown’s 2014 collection", "files.html#nora-brown-c-2-collection", "2014 collection")]

def reference_links(html_text):
    """Link the glossary's “see Speed on LifeWiki” and “see Oscillators in Files”."""
    html_text = LIFEWIKI.sub(lambda m: f'<a href="https://conwaylife.com/wiki/{m.group(1).replace(" ", "_")}">'
                                       f'{m.group(1)} on LifeWiki</a>', html_text)
    html_text = FILES_REF.sub(lambda m: f'<a href="files.html#{slug(m.group(1))}">{m.group(1)}</a> in Files', html_text)
    for phrase, href, linked in COLLECTIONS:
        html_text = html_text.replace(esc(phrase), esc(phrase).replace(esc(linked), f'<a href="{href}">{esc(linked)}</a>'), 1)
    return html_text

def build_glossary():
    chips = "".join(f'<button class="chip" type="button" data-kind="{k}" aria-pressed="false">{esc(v)}</button>'
                    for k, v in KIND_LABELS.items())
    cards, letter = [], None
    for e in ENTRIES:
        L = e["name"].lstrip("’'")[0].upper()
        if L != letter:
            letter = L
            cards.append(f'<div class="letter" data-letter>{L}</div>')
        label = TAG_OVERRIDES.get(e["name"]) or KIND_LABELS[e["kind"]].split(" &")[0].split(",")[0].rstrip("s")
        tags = [f'<span class="tag">{esc(label)}</span>']
        credit = e.get("credit") or ""
        if credit:
            tags.append(f'<span class="tag credit">{esc(credit)}</span>')
        if e.get("reconstructed"):
            tags.append('<span class="tag" title="Pattern decoded from the original glossary image">from image</span>')
        h = 120 if e["kind"] in ("reaction",) else 170
        if e.get("paras"):
            body = wiki_body(e, h)
        else:
            body = [f'<p>{autolink(e["desc"], e["slug"])}</p>']
            if e.get("rle"):
                body.append(player(e["rle"], e["name"], height=h, loop=loop_for(e)))
        if not (e.get("rle") or e.get("paras")) and e.get("images"):
            for im in e["images"][:1]:
                src = "img/glossary/" + Path(im["src"]).name
                body.append(f'<img class="orig" src="{src}" alt="Original 2009 illustration for {esc(e["name"])}" loading="lazy">')
        if e.get("note"):
            body.append(f'<div class="note">{e["note"]}</div>')
        src = e.get("source", "")
        if src == "wiki":
            cite = f'<a href="{esc(e["url"])}">Wiki page</a>, archived {esc(e["captured"])}'
        elif src == "forum":
            cite = f'<a href="{esc(e["url"])}">Forum post</a>, {esc(e["captured"])}'
        elif src == "lost":
            pages = ", ".join(f'<a href="{esc(m["url"])}">{esc(m["name"])}</a>' for m in e["mentions"])
            cite = (f"archived wiki pages that mention it: {pages}" if len(e["mentions"]) > 1
                    else f"archived wiki page that mentions it: {pages}")
        else:
            cite = "Live Free or Die Universe glossary, 2009"
        body.append(f'<p class="src">Source: {cite}</p>')
        cls = "entry term" if e["kind"] == "term" else "entry"
        search = esc((e["name"] + " " + e["desc"]).lower())
        cards.append(f'<article class="{cls}" id="{e["slug"]}" data-kind="{e["kind"]}" data-search="{search}">'
                     f'<h3><a href="#{e["slug"]}">{esc(e["name"])}</a></h3><div class="meta">{"".join(tags)}</div>'
                     + reference_links(iteration_link("".join(body), e["name"])) + "</article>")
    n_pat = sum(1 for e in ENTRIES if e.get("rle"))
    body = f"""
<h1>Glossary</h1>
<p class="lede">Every named object and term in Live Free or Die: {len(ENTRIES)} entries, {n_pat} with runnable patterns.</p>
<div class="prose">
<p class="muted">Text is from the Live Free or Die wiki (2013–2018) where an archived copy of the page survives, and otherwise from
the June 2009 Live Free or Die Universe glossary or the ConwayLife forum; each entry links to its source. All objects found and named
by Luke Bradford unless otherwise noted. General CA terms are taken from Stephen Silver’s Life Lexicon. Each pattern runs live; click to pause,
or copy its RLE into <a href="https://golly.sourceforge.io/">Golly</a> (rule <code>B2/S0</code>).
To compare objects, see the <a href="tables.html">object tables</a>; for which wing lengths each extensible family allows,
see the <a href="iterations.html">iteration guides</a>.</p>
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

LATER_SKIP = {"ant stack"}
# Puffers whose glossary pattern holds more than the puffer: its initial population, and a note under the table.
INITIAL_POP = {"buffalo rake": ("88", "The buffalo rake pattern also shows the ship it converts into, and a moon the rake has "
                                      "already released; its initial population counts the rake alone.")}  # the 2009 tables already list its three forms

def fmt_avg(x):
    from decimal import Decimal, ROUND_HALF_UP
    return f"{Decimal(repr(x)).quantize(Decimal('0.01'), ROUND_HALF_UP):f}".rstrip("0").rstrip(".")

def later_disc(e):
    credit = re.sub(r"\s*\(.*?\)", "", e.get("credit") or "")
    return "" if "not recorded" in credit else credit

def later_tables():
    """Statistics for objects catalogued after June 2009, computed from their glossary patterns."""
    known = {slug(TABLE_RENAMES.get(r[0], r[0])) for t in TABLES["object tables.htm"] for r in t["rows"][1:]}
    in_2009 = {g["name"].lower() for g in GLOSSARY}
    osc = [["Name", "Min", "Avg", "Max", "Pd", "Area", "Box", "Sym", "Disc"]]
    ships = [["Name", "Min", "Avg", "Max", "Pd", "Speed", "Area", "Box", "Sym", "Disc"]]
    puffers = [["Name", "Type", "In pop", "Pd", "Speed", "Sym", "Disc"]]
    tags = [["Name", "Pd", "Speed", "Type", "Disc"]]
    notes = []
    for e in ENTRIES:
        if (e["name"].lower() in in_2009 or e["slug"] in known or e["name"] in LATER_SKIP
                or not e.get("rle") or e["kind"] not in ("oscillator", "spaceship", "puffer", "tagalong")):
            continue
        cells = parse_rle(e["rle"])
        disc = later_disc(e)
        name = e["name"][0].upper() + e["name"][1:]
        if e["kind"] == "tagalong":
            st = object_stats(cells)  # the pattern shows it riding a ship, so only period and speed are its own
            tags.append([name, str(st["period"]), st["speed"], "Tagalong", disc])
            continue
        if e["kind"] == "puffer":
            kind = TAG_OVERRIDES.get(e["name"]) or ("Rake" if "rake" in e["desc"].lower() else "Puffer")
            pd, speed = front_period(cells, gun=kind == "Gun")
            pop = str(len(cells))
            if e["name"] in INITIAL_POP:  # the pattern holds more than the object itself
                pop, note = INITIAL_POP[e["name"]]
                notes.append(note)
            puffers.append([name, kind, pop, str(pd or ""), speed, symmetry_code([cells]), disc])
            continue
        st = object_stats(cells)
        w, h = st["box"]
        row = [name, str(st["min"]), fmt_avg(st["avg"]), str(st["max"]), str(st["period"])]
        if st["kind"] == "spaceship":
            row.append(st["speed"])
        row += [str(w * h), f"{w}x{h}", st["sym"], disc]
        (ships if st["kind"] == "spaceship" else osc).append(row)
    for t in (osc, ships, puffers, tags):
        t[1:] = sorted(t[1:], key=lambda r: int(r[1]) if r[1].isdigit() else (int(r[2]) if r[2].isdigit() else 10**9))
    return [("Oscillators", osc), ("Spaceships", ships), ("Puffers, rakes and guns", puffers),
            ("Tagalongs", tags)], notes

def build_tables():
    tables = TABLES["object tables.htm"]
    later, later_notes = later_tables()
    toc = " · ".join(f'<a href="#{slug(t["caption"])}">{esc(t["caption"])}</a>' for t in tables)
    parts = ["<h1>Object tables</h1>",
             '<div class="prose"><p class="lede">Statistics for every oscillator, spaceship, puffer, tagalong and pre-spark '
             'known in June 2009, followed by the objects found since.</p><p class="muted">For objects with multiple or infinite '
             'iterations, tables refer to the smallest. Names link to the glossary. Click a column heading to sort by it. '
             'The legend explains the abbreviations, including engine address (EA) notation, '
             'Luke’s shorthand for describing the engine of any lightspeed ship or puffer.</p>'
             f'<p class="toc">{toc} · <a href="#later-finds">Later finds</a> · <a href="#legend">Legend</a></p></div>']
    for t in tables:
        parts.append(f'<h2 id="{slug(t["caption"])}">{esc(t["caption"])}</h2>')
        parts.append(table_html(t["rows"], SLUGS, sortable=True))
    parts.append('<h2 id="later-finds">Later finds</h2><div class="prose"><p class="muted">Objects catalogued after June 2009, '
                 'on the wiki (2013–2018) or the ConwayLife forum. These tables were not part of the original site: population, '
                 'period, speed, bounding box and symmetry are computed by simulating each glossary pattern, and the columns '
                 'that need a human eye (noses, wings, sparks, engine address) are left out. A puffer’s symmetry is that of its '
                 'initial pattern. Disc names the discoverer as the glossary credits them.</p></div>')
    for title, rows in later:
        if len(rows) > 1:
            parts.append(f'<h3 id="later-{slug(title)}">{esc(title)}</h3>')
            parts.append(table_html(rows, SLUGS, sortable=True))
            if title.startswith("Puffers"):
                parts += [f'<p class="muted table-note">{n}</p>' for n in later_notes]
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

PERIODS = load("periods.json")

def period_name(row):
    """An object's name in the period tables: glossary links, {formula} spans as MathML,
    and, for later finds, who found it and when, linked to the post."""
    used, out = {"anchor"}, []  # “anchor” here is part of “anchor nibbler”, not the anchor oscillator
    for i, part in enumerate(re.split(r"\{([^}]*)\}", row["name"])):
        if i % 2:
            out.append(mathml(part))
        elif row.get("slug"):
            out.append(esc(part))
        elif re.fullmatch(r"[A-Za-z ]+", part) and slug(part) in SLUGS:  # short names autolink skips, such as Dot
            used.add(slug(part))
            out.append(f'<a href="glossary.html#{slug(part)}">{esc(part)}</a>')
        else:
            out.append(autolink(part, prefix="glossary.html#", used=used))
    name = "".join(out)
    if row.get("slug"):
        name = f'<a href="glossary.html#{row["slug"]}">{name}</a>'
    if row.get("credit"):
        credit = esc(row["credit"])
        if row.get("url"):
            credit = f'<a href="{esc(row["url"])}">{credit}</a>'
        name += f' <span class="credit">{credit}</span>'
    return name

def period_cell(text):
    if not text:
        return '<td class="num">?</td>'
    return f'<td class="num">{mathml(text) if is_formula(text) else esc(text)}</td>'

def build_periods():
    parts = ["<h1>Period explorations</h1>", f'<div class="prose">{PERIODS["intro"]}</div>']
    for t in PERIODS["tables"]:
        rows = "".join(f"<tr>{period_cell(r['period'])}<td>{period_name(r)}</td>{period_cell(r['cells'])}</tr>"
                       for r in t["rows"])
        parts.append(f'<h2 id="{slug(t["title"])}">{esc(t["title"])}</h2>'
                     f'<div class="table-wrap"><table class="periods"><thead><tr><th class="num">Period</th>'
                     f'<th>{esc(t["column"])}</th><th class="num">Cells</th></tr></thead><tbody>{rows}</tbody></table></div>')
        if t.get("note"):
            note = re.sub(r"\{([^}]*)\}", lambda m: mathml(m.group(1)), t["note"])
            parts.append(f'<p class="muted table-note">{note}</p>')
    page("periods.html", "Period explorations", "\n".join(parts),
         "The smallest known oscillator, spaceship and puffer of each period in Live Free or Die.")

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

def iter_cell(x, y, color, circle=False, p=10):
    if circle:
        return f'<circle class="ic-{color} ic-ring" cx="{x*p + p/2}" cy="{y*p + p/2}" r="{p/2 - 1.2}"/>'
    return f'<rect class="ic-{color}" x="{x*p + 0.75}" y="{y*p + 0.75}" width="{p - 1.5}" height="{p - 1.5}" rx="1.5"/>'

def iter_svg(d, title, p=10):
    """Redraw an iteration diagram from its cell grid, with a one-cell margin and faint grid lines."""
    cols, rows = d["cols"] + 2, d["rows"] + 2
    w, h = cols * p, rows * p
    grid = "".join(f"M{i*p} 0V{h}" for i in range(1, cols)) + "".join(f"M0 {j*p}H{w}" for j in range(1, rows))
    cells = "".join(iter_cell(x + 1, y + 1, c, bool(rest), p) for x, y, c, *rest in d["cells"])
    return (f'<svg class="iter-svg" viewBox="0 0 {w} {h}" width="{w*1.4:g}" height="{h*1.4:g}" role="img" '
            f'aria-label="Iteration diagram for {esc(title)}"><path class="grid" d="{grid}"/>{cells}</svg>')

def swatch(color, circle=False):
    return f'<svg class="swatch" viewBox="0 0 10 10" width="13" height="13" aria-hidden="true">{iter_cell(0, 0, color, circle)}</svg>'

def build_iterations():
    by = {e["name"]: e for e in ENTRIES}
    parts = ["<h1>Iteration guides</h1>", f"""<div class="prose">
<p class="lede">Possible iterations of the extensible puffer and spaceship families: which wing lengths work, and which must be anchored.</p>
<p><strong>Key.</strong> {swatch("black")}Black cells are necessary in any iteration (the minimum length of extensible wings is marked by the first colored cell).
{swatch("blue")}Blue cells mark wing lengths which cannot be anchored.
{swatch("green")}Green cells mark wing lengths which can be anchored or non-anchored.
{swatch("red")}Red cells mark wing lengths which must be anchored.
{swatch("green", True)}Circled cells mark wing lengths that produce no output if non-anchored, in objects that can be spaceships or eaters.
{swatch("gray")}Gray cells are caused by phase offsets in wings; wings should be extended and anchored in their empty phase, which may not be the phase shown.
To see how the phase offsets work, consult the smallest iteration.</p>
<p class="muted">The diagrams are redrawn cell for cell from the original July 2008 images. Next to each is the smallest iteration, running live.</p>
</div>"""]
    for title, img, ref in ITERATIONS:
        e = by.get(ref)
        parts.append(f'<h2 id="{slug(title)}">{esc(title)}</h2><div class="iter">'
                     f'{iter_svg(ITER_GRIDS[img], title)}'
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
    body = """<h1>Challenges</h1>
<div class="prose">
<p class="lede">Patterns not yet known in Live Free or Die, as of November 2026.</p>
<p class="muted">Compiled from the <a href="periods.html">period tables</a>, the wiki’s last list of challenges (April 2015),
and the <a href="https://conwaylife.com/forums/viewtopic.php?t=649">ConwayLife forum thread</a>.</p>
<ul>
<li>Objects of period 11, 13, 14, 15, 17, 21, 22 and 23, and of most higher periods not in the <a href="periods.html">period tables</a></li>
<li>Oscillators of period 7, 9, 10, 11, 13 to 18, or 20 to 27</li>
<li>Spaceships of period 7, 9, 11, 13, 14, 15, 17, 18 or 19. Partial p9 lightspeed ships were posted to the forum in 2021, but none was completed.</li>
<li>Puffers and rakes of period 11, 13, 14, 15, 17 or 19</li>
<li>Spaceships of speeds other than c, c/2, 2c/5, c/3, c/4 and c/5 orthogonally, and c/4 diagonally</li>
<li>Puffers and rakes slower than c, other than at c/2 and c/5</li>
<li>Knightships: spaceships or puffers that travel obliquely. A (2,1)c/5 front end was posted in 2018, but never completed.</li>
<li>A reusable reflector for <a href="glossary.html#moon">moons</a>, ideally a stable one. The only known moon reflectors destroy themselves.</li>
<li>Guns for any spaceship other than the moon, and moon guns of periods other than 4 and 5</li>
<li>Signal circuitry analogous to Herschel conduits in Conway’s Life</li>
<li>Spacefillers, other than the light-speed expansion of <a href="glossary.html#chaos">chaos</a></li>
<li>Replicators</li>
<li>Stabilizations for wicks and oscillator components that work the same way in Seeds (B2/S)</li>
</ul>
<h2>History</h2>
<p>The 2008 site kept a list of open problems, promising “eternal gratitude, naming rights, and a place of glory on this web site”
to anyone who solved one. The wiki carried it on from 2013 and in July 2014 added cash prizes: $25 for a spaceship of a new speed,
$25 for any moon reflector and $50 for a stable one. Michael Simkin’s c/3 <a href="glossary.html#wasp-ship">wasp ship</a> won the speed prize
in October 2014. Many of the 2008 challenges have since been met, among them guns (2012), c/3 and c/4 spaceships, period 10 (2012),
p2 puffers (2014), breeders (2015), and a <a href="rule110.html">Rule 110 unit cell</a> showing that the rule is universal (2020).
Neither offer stands today.</p>
</div>"""
    page("challenges.html", "Challenges", body, "Undiscovered patterns in the Live Free or Die cellular automaton.")

def news_date(iso):
    import datetime
    d = datetime.date.fromisoformat(iso)
    return f"{d:%B} {d.day}, {d.year}"

def build_news():
    # Newest first. The 2009 page already lists same-day items newest first; later items are
    # listed oldest first, so their same-day order is reversed (e.g. a reply above its post).
    items = [((n["date"], -i), n["paras"], "site", None) for i, n in enumerate(NEWS)]
    items += [((n["date"], i), n["paras"], n.get("source", ""), n.get("rle")) for i, n in enumerate(LATER.get("news", []))]
    items.sort(key=lambda x: x[0], reverse=True)
    out, era = [], None
    for (date, _), paras, src, rle in items:
        y = date[:4]
        if y != era:
            era = y
            out.append(f'</ul><h2 class="era" id="y{y}">{y}</h2><ul class="timeline">')
        used = set()
        ps = "".join(f"<p>{autolink(p, prefix='glossary.html#', used=used) if src == 'site' else autolink_html(p, 'glossary.html#', used)}</p>"
                     for p in paras)
        tag = f' <span class="tag">{esc(src)}</span>' if src != "site" else ""
        pl = player(rle, re.sub("<[^>]+>", "", paras[0])[:80], height=200, loop=200) if rle else ""
        out.append(f'<li><time datetime="{date}">{news_date(date)}</time><div>{ps}{tag}{pl}</div></li>')
    body = ('<h1>News</h1><div class="prose"><p class="lede">A dated record of discoveries.</p>'
            '<p class="muted">Entries from December 2007 to September 2009 are the original Live Free or Die Universe News page, verbatim. '
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

# Updates for out-of-date claims in the verbatim 2008 descriptions, keyed by file (HTML).
FILE_NOTES = {
    "p192 backward free rake.rle": 'No longer the largest: FWKnightship’s <a href="rule110.html">Rule 110 unit cell</a> (2020) has about 73,000 cells.',
}

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
            note = f' <strong>Update:</strong> {FILE_NOTES[fn]}' if fn in FILE_NOTES else ""
            out.append(f'<div class="file" id="{slug(name)}"><div class="name">{esc(name)}</div>'
                       f'<div class="desc">{esc(desc)}{note}</div><div class="actions">{acts}</div></div>')
        out.append("</div>")
        return "\n".join(out)
    body = f"""<h1>Files</h1>
<div class="prose">
<p class="lede">Original files created in Golly containing explorations, experiments, and collections of objects.</p>
<p class="muted">Each file is the latest surviving version (most from 2008–2010). <em>View</em> opens it in the in-browser player;
for the largest files (the p192 backward free rake is about 30,000 cells) <a href="https://golly.sourceforge.io/">Golly</a> is much faster.</p>
<p class="muted">Descriptions are as of when each file was made, so “known” means known then. For current records, see <a href="periods.html">Period explorations</a>.</p>
</div>
<h2>Files page (2008)</h2>
{render("listed")}
<h2>Other files from the site folder</h2>
<div class="prose"><p class="muted">These were uploaded to the site or kept alongside it but weren’t on the Files page.</p></div>
{render("extra")}
{'<h2 id="later-files">Later files</h2>' + render("later") if any(r[0] == "later" for r in rows) else ""}
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

def build_rule110():
    # FWKnightship's pattern, as distributed with Golly (identical to the forum post). Too big for lfod.js,
    # so the page runs it on the GPU with assets/w110.js.
    name = "lfod-flying-rule110-simulator.rle"
    shutil.copy(DATA / name, OUT / "files" / name)
    body = f"""<h1>Rule 110 unit cell</h1>
<div class="prose">
<p>FWKnightship’s Rule 110 emulator in Live Free or Die, posted on 20 October 2020. Rule 110 is a one-dimensional cellular automaton
that is known to be universal, so emulating it showed that Live Free or Die is Turing-complete.</p>
<p>The torus is 4320 × 7200 and holds six unit cells, each 720 cells wide. Each unit cell stores its Rule 110 state in a lone dot at
the top (circled): a live dot means 1. Fleets of lightspeed ships sweep down the torus, read the dots, and rewrite them. Each sweep takes
7200 generations, the height of the torus, and computes one Rule 110 generation.</p>
<p class="muted">Simulated on your GPU. Scroll to zoom, drag to pan. The panel shows the six dots, read every 7200 generations.
<a href="https://conwaylife.com/forums/viewtopic.php?p=107139#p107139">Forum post</a> ·
<a href="files/{name}" download>Download RLE</a> (also distributed with <a href="https://golly.sourceforge.io/">Golly</a>).</p>
</div>
<div class="w110">
<div class="stage">
<canvas id="gl"></canvas>
<canvas id="ov"></canvas>
<span class="pinfo" id="info">Loading…</span>
<div class="pbar">
<button type="button" id="play" title="Play / pause">▶</button>
<button type="button" id="step" title="Step one generation">⏭</button>
<button type="button" id="next" title="Run to the next Rule 110 generation">Next Rule 110 step</button>
<button type="button" id="reset" title="Reset">⟲</button>
<button type="button" id="fit" title="Fit the whole torus">Fit</button>
<span class="grow"></span>
<label for="speed" class="muted">Speed</label>
<select id="speed">
<option value="1">1 gen/frame</option>
<option value="10">10 gen/frame</option>
<option value="100">100 gen/frame</option>
<option value="max" selected>Max</option>
</select>
</div>
</div>
<aside class="side">
<h3>Rule 110 state</h3>
<div id="hist"></div>
</aside>
</div>
<script src="assets/w110.js?v={asset_version()}" defer></script>"""
    page("rule110.html", "Rule 110 unit cell", body,
         "FWKnightship’s Rule 110 unit cell in Live Free or Die (B2/S0), running in the browser.")

def build_index():
    by = {e["name"]: e for e in ENTRIES}
    def tile(label, name, loop, note=""):
        return (f'<div>{player(by[name]["rle"], label, height=150, loop=loop)}<p class="muted" style="margin:.3em 0 0;font-size:.85rem">'
                f'<a href="glossary.html#{slug(name)}">{esc(label)}</a>{" " + esc(note) if note else ""}</p></div>')
    # The four objects the text names; the glossary's dot puffer pattern is the 2-2 dot puffer.
    feat = [("free ship", "free ship", 48), ("double dot puffer", "double dot puffer", 60),
            ("2-2 dot puffer", "dot puffer", 60), ("key ship", "key ship", 40)]
    tiles = "".join(tile(*f) for f in feat)
    monster = tile("monster", "monster", 57, "(a p19 oscillator)")
    counts = {k: sum(1 for e in ENTRIES if e["kind"] == k) for k in KIND_LABELS}
    body = f"""
<div class="hero">
<div class="prose">
<h1>Live Free or Die Universe</h1>
<p class="lede">An exploration of the Moore neighborhood s0/b2 cellular automaton.</p>
<p>Live Free or Die, like Conway’s <a href="https://en.wikipedia.org/wiki/Conway%27s_Game_of_Life">Game of Life</a>, is a two-dimensional two-state Moore neighborhood cellular automaton. In other words,
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
<a class="card" href="periods.html"><strong>Period explorations</strong><span>The smallest oscillator, puffer and spaceship for each known period</span></a>
<a class="card" href="challenges.html"><strong>Challenges</strong><span>Undiscovered patterns</span></a>
<a class="card" href="files.html"><strong>Files</strong><span>Run-length encoded collections and explorations</span></a>
<a class="card" href="restoration.html"><strong>About this restoration</strong><span>What was recovered, from where, and what is lost</span></a>
</div>

<div class="prose">
<h2>A short explanation</h2>
<p>I found Live Free or Die while messing around with simple variations of Seeds (/b2). It is so named because the only cells
that survive between generations are free of neighbors. What first intrigued me about it were the extremely common free ship, the double
and 2-2 dot puffers, and the key ship.</p>
</div>
<div class="cards">{tiles}</div>
<div class="prose">
<p>Live Free or Die is a small, fast, intuitive universe, in which most objects are more reminiscent of machinery than of the organic fluidity
that is characteristic of Conway’s Life (s23/b3). It is full of readily visible patterns, and flotillas and other large projects are easy to
assemble. The explosive nature of the rule makes it receptive to the naturalistic study of mobile objects. It has oscillators of each period
and spaceships of each speed that is possible in the Seeds universe, along with objects that are impossible or undiscovered in Seeds: stable
fuses, oscillators with stators, and oscillators and spaceships of indefinitely large period.</p>
<p>Over the years, thanks to the contributions of a large number of fellow explorers, objects of many periods and speeds have been discovered, such as the p10 <a href="glossary.html#decade-ship">decade ship</a>,
the c/3 <a href="glossary.html#wasp-ship">wasp ship</a> and the <a href="glossary.html#moon-laser">moon laser</a> gun, along with various types
of breeders, from the <a href="https://conwaylife.com/forums/viewtopic.php?p=17412#p17412">first MMS breeder</a> in 2015 to the
<a href="https://conwaylife.com/forums/viewtopic.php?p=212337#p212337">first MMM breeder</a> in 2025 (see <a href="news.html">News</a>).
The construction of a <a href="rule110.html">Rule 110 unit cell</a> in 2020 proved that
Live Free or Die is <a href="https://en.wikipedia.org/wiki/Turing_completeness">Turing-complete</a>.</p>
<p>— Luke Bradford</p>
</div>
<div class="cards">{monster}</div>
<div class="prose">
<div class="note">Most of this site is a historical restoration, not a complete and actively maintained catalog of patterns and discoveries in Live Free or Die.</div>
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
    for p in (ARCHIVE / "verizon-site/glossary_files").glob("*.jpg"):
        shutil.copy(p, img / "glossary" / p.name)
    shutil.copy(DATA / "icon.png", img / "icon.png")  # the 2009 icon without its drop shadow
    (OUT / ".nojekyll").write_text("")

if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    copy_assets()
    build_index(); build_news(); build_glossary(); build_tables(); build_periods()
    build_iterations(); build_challenges(); build_files(); build_viewer(); build_rule110()
    if (DATA / "restoration.html").exists():
        build_restoration()
    print("built", len(ENTRIES), "glossary entries")
