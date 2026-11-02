"""Assemble data/later.json: what happened after the 2009 site, from the archived wiki
(data/wiki.json) and selected forum patterns (data/forum_patterns.json).

Usage: python3 tools/make_later.py
"""
import json, re, shutil, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
sys.path.insert(0, str(ROOT / "tools"))
from lfod import parse_macrocell, parse_life105, parse_rle, to_rle

WIKI = json.loads((DATA / "wiki.json").read_text())
GLOSSARY = {e["name"].lower(): e for e in json.loads((DATA / "glossary.json").read_text())}
FORUM = json.loads((DATA / "forum_patterns.json").read_text())
THREAD = "https://conwaylife.com/forums/viewtopic.php?t=649"
NAMES = {"Sokwe": "Matthias Merzenich (Sokwe)", "wildmyron": "Arie Paap (wildmyron)",
         "simsim314": "Michael Simkin (simsim314)", "glider_rider": "Nora Brown",
         "bprentice": "Brian Prentice", "velcrorex": "Josh Ball (velcrorex)", "lukebradford": "Luke Bradford"}
CONCEPTS = {"chaos", "natural", "flotilla", "gun", "speed of light"}

def post_url(pid):
    return f"https://conwaylife.com/forums/viewtopic.php?p={pid[1:]}#{pid}"

def norm(t):
    return re.sub(r"\W", "", (t or "").lower())

entries = []
for p in WIKI:
    name = p["name"]
    if name.lower() in ("home", "challenges"):
        continue
    old = GLOSSARY.get(name.lower())
    if old:
        # The wiki text supersedes the 2009 text; keep the 2009 pattern only if the wiki page had none.
        entries.append({"name": old["name"], "desc": p["desc"] or old["desc"], "rle": p["rle"], "credit": p["credit"],
                        "paras": p["paras"] if p["desc"] else None, "rles": ([p["rle"]] if p["rle"] else []) + p["extra_rles"],
                        "replace": True, "source": "wiki", "url": p["url"], "captured": p["captured"]})
    elif p["rle"] or name in CONCEPTS:
        desc = p["desc"] if p["rle"] else " ".join(p["paras"][:2])
        entries.append({"name": name, "desc": desc, "rle": p["rle"], "credit": p["credit"] or "",
                        "paras": p["paras"] if p["rle"] else p["paras"][:2],
                        "rles": ([p["rle"]] if p["rle"] else []) + p["extra_rles"],
                        "source": "wiki", "url": p["url"], "captured": p["captured"]})

# The wiki's "Period" page ends with tables of the smallest objects per period, which don't survive as paragraphs.
for e in entries:
    if e["name"].lower() == "period" and e.get("paras"):
        cut = e["paras"].index("Smallest known objects for each period")
        e["paras"] = [q.replace("A table of the smallest objects for each known period is at the end of this article. The rest is a summary",
                                "Below is a summary") for q in e["paras"][:cut]]
        e["desc"] = " ".join(e["paras"])
        break

# A mid-sentence parenthetical on the wiki sometimes closes over the sentence's period: "(a p1 oscillator.)".
MIDSENTENCE_PAREN = re.compile(r"(\w \([^()]*)\.\)")
for e in entries:
    e["desc"] = MIDSENTENCE_PAREN.sub(r"\1).", e["desc"])
    if e.get("paras"):
        e["paras"] = [MIDSENTENCE_PAREN.sub(r"\1).", q) for q in e["paras"]]

# Claims on archived wiki pages that later finds (most posted before the last capture) made wrong.
# The wiki text stays as it was; the note follows it.
P5_GUN = ('Arie Paap found a much smaller <a href="news.html#y2016">p5 moon gun</a> in August 2016, '
          "so the moon laser is no longer the only known gun.")
NOTES = {
    "gun": P5_GUN,
    "moon laser": P5_GUN,
    "flotsam": P5_GUN,
    "decade ship": 'It is no longer the only p10 object: Arie Paap found the first <a href="news.html#y2015">p10 puffers</a> in February 2015.',
    "arrow puffer": 'They are no longer the only p9 objects: Arie Paap found a <a href="news.html#y2015">p9 dot puffer</a> in February 2015, '
                    'and AforAmpere posted another <a href="news.html#y2021">p9 puffer</a> in 2021.',
    "starfish": 'Arie Paap found a third p5 oscillator, the <a href="news.html#y2016">bow tie</a>, in August 2016.',
    "crossroads": 'Arie Paap found a third p5 oscillator, the <a href="news.html#y2016">bow tie</a>, in August 2016.',
    "moon": 'Not only moon rakes: the <a href="glossary.html#freedom-collider">freedom collider</a> (Arie Paap, January 2015) '
            "is a backward short free ship rake that isn’t a flotilla.",
    "rake": 'Not only flotillas: the <a href="glossary.html#freedom-collider">freedom collider</a>, described in the same paragraph, '
            'is a short free ship rake, and in 2025 Game of Life Fun posted <a href="news.html#y2025">very small p12 and p24 free ship rakes</a>.',
    "puffer": 'Not only flotillas: Josh Ball’s c p4 side rake (<a href="news.html#y2014">July 2014</a>) is a sideways rake that isn’t a flotilla, '
              'and the <a href="glossary.html#freedom-collider">freedom collider</a> (Arie Paap, January 2015) is a backward short free ship rake.',
    "period": "Several “only known” claims here are out of date. "
              'P2: Josh Ball’s c p2 backrake (<a href="news.html#y2014">July 2014</a>) came before the flicker rake, and Arie Paap posted a p2 wick puffer in 2015. '
              'P4: Arie Paap’s <a href="news.html#y2016">p5 moon gun</a> (2016) means the moon laser is not the only gun. '
              'P5: the <a href="news.html#y2016">bow tie</a> (2016) is a third p5 oscillator. '
              'P9: Arie Paap’s <a href="news.html#y2015">p9 dot puffer</a> (2015) and AforAmpere’s p9 puffer (2021). '
              'P10: Arie Paap’s <a href="news.html#y2015">p10 puffers</a> (2015), which travel at c.',
}
for e in entries:
    if e["name"].lower() in NOTES:
        e["note"] = NOTES[e["name"].lower()]
assert {e["name"].lower() for e in entries if "note" in e} == set(NOTES)

# Names that survive only on the wiki's speed table and in the forum: take the pattern from the forum post.
BY_TITLE = {f["title"]: f for f in FORUM}
for name, title, desc in [
    ("buffalo rake", "Buffalo rake and ship",
     "A p4 c/2 clean backward moon rake with an initial population of 88 cells, the smallest known c/2 puffer or rake. "
     "Can be converted to a spaceship with a trailer. Shown below as a rake (with one moon already released) and as a ship."),
    ("buffalo bird", "Buffalo bird",
     "A small c/2 tagalong for a majority of the known c/2 spaceships and rakes. Shown riding a ship."),
    ("flicker rake", "p2 rake (flicker rake)",
     "The following p2 c clean backward moon rake with an initial population of 384 cells. Discovered by Nora Brown "
     "and named by Luke Bradford in March 2015."),
]:
    f = BY_TITLE[title]
    entries.append({"name": name, "desc": desc, "rle": f["rle"], "credit": NAMES.get(f["by"], f["by"]),
                    "source": "forum", "url": post_url(f["post"]), "captured": f["date"]})
FORUM_NOTES = {
    "flicker rake": "Luke hailed the flicker rake as the first p2 puffer, but Josh Ball’s "
                    '<a href="news.html#y2014">c p2 backrake</a>, posted in July 2014, is an earlier p2 rake. That backrake was never named. '
                    "The wiki’s period table later listed the flicker rake as the smallest known p2 puffer with an initial population "
                    "of 82 cells, which is the backrake’s population, not the flicker rake’s.",
}
for e in entries:
    if e["name"] in FORUM_NOTES:
        e["note"] = FORUM_NOTES[e["name"]]

# Families in Nora Brown's organized c/2 collection (forum, 2014-12-29), named in private messages
# between Luke and Nora that week: rows of horned, unicorn, hippo and buffalo ships, and the fox ship.
C2 = json.loads((DATA / "c2_families.json").read_text())
C2_POST = post_url("p15361")
for name, key, desc, credit in [
    ("horned ship", "horned",
     "Any of a family of p4 and p8 c/2 spaceships sharing the front end of the horned rake. Nora Brown’s 2014 collection has {count}; "
     "the smallest, shown below, has a minimum population of {minpop} cells.", "Nora Brown"),
    ("hippo ship", "hippo",
     "Any of a family of p4 c/2 spaceships with the same front-end mechanism. Nora Brown’s 2014 collection has {count}; "
     "the smallest, shown below, has a minimum population of {minpop} cells. The original hippo ship page is lost, and no surviving source records who found the first one.", "discoverer not recorded"),
    ("buffalo ship", "buffalo",
     "Any of a family of p4 and p8 c/2 spaceships with even bilateral symmetry, found by Arie Paap with gfind and WinLifeSearch in August 2014. "
     "Nora Brown’s 2014 collection has {count} with the buffalo front end; the smallest, shown below, has a minimum population of {minpop} cells.",
     "Arie Paap (wildmyron)"),
    ("fox ship", "fox",
     "The following p4 c/2 spaceship with a minimum population of {minpop} cells, the one ship in Nora Brown’s 2014 collection that fit no family. "
     "Nora Brown named it the fox ship because each of its four phases looks like a dog or fox.", "Nora Brown"),
]:
    f = C2[key]
    entries.append({"name": name, "desc": desc.format(count=f["count"], minpop=f["smallest"]["minpop"]),
                    "rle": f["smallest"]["rle"], "credit": credit, "source": "forum", "url": C2_POST, "captured": "2014-12-29"})
for name, title, desc in [
    ("horned rake", "c/2 backrake",
     "A p4 c/2 clean backward moon rake, named by its discoverer in December 2014. Can be stabilized into a horned ship."),
    ("sawtooth", "Sawtooth",
     "A sawtooth (a pattern whose population grows without bound but repeatedly falls back): a c/2 ship adds a moon eater to a stream of moons, "
     "which a pair of monsters then destroys, and the cycle starts again. Its population repeatedly drops to 915. The first known in the rule; "
     "it had its own wiki page, now lost."),
]:
    f = BY_TITLE[title]
    entries.append({"name": name, "desc": desc, "rle": f["rle"], "credit": NAMES.get(f["by"], f["by"]),
                    "source": "forum", "url": post_url(f["post"]), "captured": f["date"]})

# Objects whose wiki pages were never archived, but which surviving pages name. Each entry gathers what those pages say,
# so that the names can link somewhere; a note says the page is lost.
WIKI_URL = {p["name"]: p["url"] for p in WIKI}
for name, kind, desc, pages in [
    ("collider ship", "spaceship", "A spaceship that the wiki’s freedom collider page asks readers to compare with the freedom collider.",
     ["freedom collider"]),
    ("ellipsis puffer", "puffer", "A p3 puffer.", ["period"]),
    ("hex rake", "puffer", "A p6 c sideways moon rake.", ["period", "rake"]),
    ("hippo rake", "puffer", "A p4 c/2 backward moon rake.", ["period", "puffer", "rake"]),
    ("plow trailer", "tagalong", "A p4 c trailer that can be used to build rakes.", ["period"]),
    ("pocket rake", "puffer", "A p4 c clean backward moon rake.", ["period", "rake"]),
    ("quintessential rake", "puffer", "A p5 c/5 backward moon rake with the same front-end mechanism as the quintessential ships.",
     ["quintessential ship", "hammerhead ship", "period", "rake"]),
    ("wave puffer", "puffer", "Any of a family of c puffers whose wings can be extended infinitely.", ["wing"]),
    ("wave ship", "spaceship", "Any of a family of c spaceships whose wings can be extended infinitely.", ["wing"]),
    ("wide rhino ship", "spaceship", "A p4 c/2 spaceship with the same front-end mechanism as the unicorn ships, "
     "named separately because it was found before them.", ["unicorn ship", "dust mite ship", "period"]),
    ("zipper rake", "puffer", "A p4 c sideways moon rake.", ["period", "rake"]),
]:
    entries.append({"name": name, "kind": kind, "desc": desc, "rle": "", "credit": "", "source": "lost",
                    "mentions": [{"name": p, "url": WIKI_URL[p]} for p in pages],
                    "note": f"The wiki’s {name} page was never archived, and no pattern under this name survives. "
                            "This entry gathers what other wiki pages say about it."})
# The big six shooter stack's page is lost too, but Josh Ball's July 2014 post includes one (the leftmost pattern).
f = BY_TITLE["New p4 oscillators and a big six shooter stack"]
stack = {(x, y) for x, y in parse_rle(f["rle"]) if x < 35}
entries.append({"name": "big six shooter stack", "rle": to_rle(stack), "credit": NAMES[f["by"]],
                "desc": "Any p6 oscillator formed by combining big six shooters. The one below, from Josh Ball’s July 2014 forum post, "
                        "has a minimum population of 89 cells.",
                "source": "forum", "url": post_url(f["post"]), "captured": f["date"],
                "note": "The wiki’s big six shooter stack page was never archived; this example comes from the forum."})

# Which way each moving News pattern travels, as posted (screen coordinates, y down), checked by simulation.
# The News page shows orthogonal craft travelling right and diagonal ones down and to the right.
# Oscillators, guns, the seed and the four-way wave-riding ship are left as posted.
HEADING = {
    "c/4 diagonal ship": (-1, -1), "p10 c/5 ship (decade ship)": (0, -1), "Two growing spaceships": (0, 1),
    "p12 anchor track flotillas": (1, 0), "p8 c/2 ship": (-1, 0), "c/2 p4 spaceship and backrake": (-1, 0),
    "c p4 side rake": (-1, 0), "c p2 backrake": (-1, 0), "c p6 side rake": (-1, 0), "Buffalo ships": (1, 0),
    "Buffalo rake and ship": (1, 0), "Buffalo bird": (1, 0), "p3 puffers (bent tricycle puffer)": (1, 0),
    "c/3 ship (wasp ship)": (-1, 0), "Extended wasp ships": (-1, 0), "c/2 backrake": (0, 1),
    "c/2 backrake stabilized into a ship": (0, 1), "Sawtooth": (1, 0), "Short free ship rake (freedom collider)": (1, 0),
    "Anchored freedom collider": (1, 0), "Tiny c/2 ships (fruit fly ship)": (0, 1), "Small c/2 ships": (-1, 0),
    "p9 dot puffer": (1, 0), "p10 puffers": (1, 0), "MMS breeder": (1, 0), "p5 c spaceship": (0, 1),
    "p2 rake (flicker rake)": (0, 1), "p2 wick puffer, stabilized": (1, 0), "Short-necked giraffe": (1, 1),
    "Completed almost-rake": (1, 0), "p9 puffer": (0, -1), "Small periodic MMS breeder": (0, -1),
    "Tiny p12 and p24 free ship rakes": (0, -1), "c/5 spaceship collection": (1, 0),
}
ROTATIONS = [lambda x, y: (x, y), lambda x, y: (-y, x), lambda x, y: (-x, -y), lambda x, y: (y, -x)]

def orient(rle, heading):
    """Rotate a pattern so that it travels right, or down and to the right if diagonal."""
    if not heading:
        return rle
    target = (1, 1) if all(heading) else (1, 0)
    rot = next(r for r in ROTATIONS if r(*heading) == target)
    return to_rle({rot(x, y) for x, y in parse_rle(rle)})

# Glossary patterns follow the same convention. These are the later entries that don't already travel that way
# (checked by simulating every glossary pattern); the 2009 and wiki patterns already do.
GLOSSARY_HEADING = {"buffalo ship": (0, 1), "fox ship": (0, 1), "hippo ship": (0, 1), "horned ship": (0, 1),
                    "horned rake": (0, 1), "flicker rake": (0, 1)}
for e in entries:
    h = GLOSSARY_HEADING.get(e["name"])
    if h:
        e["rle"] = orient(e["rle"], h)
        if e.get("rles"):
            e["rles"] = [orient(r, h) for r in e["rles"]]
assert {e["name"] for e in entries} >= set(GLOSSARY_HEADING)

# The wiki's superscripts were lost in extraction: “4 × 2n - 4” is 4 × 2ⁿ − 4.
def powers(t):
    t = re.sub(r"\b2n == \+- 1\b", "2ⁿ ≡ ±1", t)
    return re.sub(r"\b2n\b", "2ⁿ", t) if t else t
for e in entries:
    e["desc"] = powers(e["desc"])
    if e.get("paras"):
        e["paras"] = [powers(q) for q in e["paras"]]

news = []
for f in FORUM:
    who = NAMES.get(f["by"], f["by"])
    news.append({"date": f["date"], "source": "forum",
                 "paras": [f'<strong>{f["title"]}</strong> by {who}. {f["note"]} '
                           f'<a href="{post_url(f["post"])}">Forum post</a>.'],
                 "rle": orient(f["rle"], HEADING.get(f["title"]))})
news += [
    {"date": "2012-07-21", "source": "forum", "paras": [
        f'Josh Ball (velcrorex) posts the first c/4 orthogonal spaceship, later named the beachcomber ship, to the '
        f'<a href="{THREAD}">Live Free or Die thread</a> on the ConwayLife forums (started in 2011). A week later he asks whether the '
        "Verizon site was saved anywhere, and Paul Tooke points to its March 2008 Wayback Machine snapshot. "
        f'<a href="{post_url("p6835")}">Forum post</a>; <a href="{post_url("p6862")}">reply</a>.']},
    {"date": "2013-10-11", "source": "forum", "paras": [
        "Luke, pointed to the thread by Andrew Trevorrow, announces <em>lfod.wikispaces.com</em>, built over the previous week or two. "
        f'Its pattern collection is dated October 14, 2013. <a href="{post_url("p9373")}">Forum post</a>.']},
    {"date": "2014-12-29", "source": "private messages", "paras": [
        "Luke and Nora Brown sort Nora’s collection of 122 c/2 spaceships by front end. The rows become the "
        "<a href=\"glossary.html#horned-ship\">horned</a>, <a href=\"glossary.html#unicorn-ship\">unicorn</a>, "
        "<a href=\"glossary.html#hippo-ship\">hippo</a> and <a href=\"glossary.html#buffalo-ship\">buffalo</a> ships, and the odd one out "
        "the <a href=\"glossary.html#fox-ship\">fox ship</a>. Luke plans an updated collection “so that the set of known spaceships can be "
        "found in a single place”."]},
    {"date": "2014-10-19", "source": "private messages", "paras": [
        "Luke names Michael Simkin’s c/3 ship the wasp ship. Simkin asks for WinLifeSearch to share the credit, and offers to put his "
        "prize money toward a challenge of his own."]},
    {"date": "2014-09-29", "source": "email", "paras": [
        "Full HTML and PDF exports of the wiki are made (lfod_20140922 and lfod_20140929). Their download links have since died."]},
    {"date": "2018-03-25", "source": "Wayback", "paras": [
        "The last Wayback Machine capture of the wiki. Wikispaces shut down later in 2018."]},
    {"date": "2020-10-20", "source": "forum", "paras": [
        "FWKnightship builds a Rule 110 unit cell in Live Free or Die, posting it in the forum’s thread on Turing-complete Life-like rules: "
        "six unit cells on a torus, swept by fleets of lightspeed ships. "
        f'<a href="{post_url("p107139")}">Forum post</a> · <a href="rule110.html">Run it</a>.']},
    {"date": "2020-11-12", "source": "forum", "paras": [
        "FWKnightship builds the puffer setup LaundryPizza03 asked for, laying a pattern of dots that leads to superlinear growth. "
        f'<a href="{post_url("p110293")}">Forum post</a>.']},
    {"date": "2025-05-26", "source": "forum", "paras": [
        "Game of Life Fun builds the first MMM breeder, after a long series of rakes, puffers and breeders at many new periods. "
        f'<a href="{post_url("p212337")}">Forum post</a>.']},
    {"date": "2025-09-05", "source": "forum", "paras": [
        "LaundryPizza03 adds the archived wiki’s names to the Glider Database, turning up earlier discoverers for some ships. "
        f'<a href="{post_url("p217471")}">Forum post</a>.']},
    {"date": "2026-10-26", "source": "restoration", "paras": [
        f'The site is rebuilt from the 2009 source files, Wayback captures, and the <a href="{THREAD}">forum thread</a>. See <a href="restoration.html">About this restoration</a>.']},
]

contributors = (", and, after 2012, <strong>Paul Tooke</strong>, <strong>Matthias Merzenich</strong>, "
                "<strong>Arie Paap</strong> (wildmyron), <strong>Michael Simkin</strong>, <strong>Nora Brown</strong>, "
                "and many others on the ConwayLife forums, including <strong>Game of Life Fun</strong>, praosylen, AforAmpere, "
                "confocaloid and FWKnightship. The Glider Database credits earlier finds of the key ship to Peter Naszvadi (2001) "
                "and the robot ship to Alex Fink (2000)")

# Later files.
# Readme descriptions that need rewording, e.g. to credit another discoverer up front.
FILE_DESC = {
    "2013 Gun.rle": "Matthias Merzenich’s p4 double-barreled moon gun (the moon laser), the only known gun until Arie Paap’s much smaller p5 moon gun in 2016.",
    "2013 Collection.rle": "Every known oscillator, puffer, and spaceship, excluding flotillas, trailers, tagalongs, and larger iterations of extensible objects.",
}
out = DATA / "later-files"
out.mkdir(exist_ok=True)
files = []
coll = ROOT / "archive/wikispaces/collection-2013/Live Free or Die collection"
readme = (coll / "readme.txt").read_text()
for p in sorted(coll.rglob("*.rle")):
    m = re.search(re.escape(p.name) + r" (.+?)(?:\n|$)", readme)
    desc = m.group(1) if m else ""
    desc = re.sub(r"^(is|has|includes|shows|gives) ", "", desc)
    fname = "2013 " + (f"Flotillas - {p.name}" if p.parent.name == "Flotillas" else p.name)
    shutil.copy(p, out / fname)
    desc = FILE_DESC.get(fname, desc[:1].upper() + desc[1:])
    files.append({"name": fname[5:-4], "file": fname, "desc": desc + " (wiki collection, October 2013)"})
SCRATCH = Path(sys.argv[1]) if len(sys.argv) > 1 else None
for src, name, date in [("att_482", "Nora Brown c/2 collection (first version)", "December 25, 2014"),
                        ("att_485", "Nora Brown c/2 collection", "December 29, 2014")]:
    dest = out / (name.replace("c/2", "c2") + ".rle")
    if SCRATCH and (SCRATCH / src).exists():
        cells = parse_macrocell((SCRATCH / src).read_text())
        dest.write_text("#C " + name + ", posted to the ConwayLife forum " + date + "\n" + to_rle(cells))
    if dest.exists():
        files.append({"name": name, "file": dest.name,
                      "desc": f"Nora Brown’s collection of c/2 spaceships and rakes, posted as a Golly macrocell on {date}; converted to RLE."
                              + (" Grouped by front end: rakes at top; then rows of horned ships and unicorn ships; then four hippo ships and, "
                                 "to their right, the fox ship; and buffalo ships at the bottom." if "first" not in name else "")})

later = {"entries": entries, "news": news, "files": files, "contributors_html": contributors}
(DATA / "later.json").write_text(json.dumps(later, indent=1, ensure_ascii=False))
print(len(entries), "entries,", len(news), "news,", len(files), "files")
