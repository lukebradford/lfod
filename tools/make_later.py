"""Assemble data/later.json: what happened after the 2009 site, from the archived wiki
(data/wiki.json) and selected forum patterns (data/forum_patterns.json).

Usage: python3 tools/make_later.py
"""
import json, re, shutil, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
sys.path.insert(0, str(ROOT / "tools"))
from lfod import parse_macrocell, parse_life105, to_rle

WIKI = json.loads((DATA / "wiki.json").read_text())
GLOSSARY = {e["name"].lower(): e for e in json.loads((DATA / "glossary.json").read_text())}
FORUM = json.loads((DATA / "forum_patterns.json").read_text())
THREAD = "https://conwaylife.com/forums/viewtopic.php?t=649"
NAMES = {"Sokwe": "Matthias Merzenich (Sokwe)", "wildmyron": "Arie Paap (wildmyron)",
         "simsim314": "Michael Simkin (simsim314)", "glider_rider": "Nico Brown (glider_rider)",
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
     "A p4 c/2 clean backward moon rake, the smallest known c/2 puffer or rake (initial population 88 on the wiki). "
     "Can be converted to a spaceship with a trailer. Shown with the spaceship it was posted with."),
    ("buffalo bird", "Buffalo bird",
     "A small c/2 tagalong for a majority of the known c/2 spaceships and rakes. Shown riding a ship."),
    ("flicker rake", "p2 rake (flicker rake)", "A p2 rake, probably the pattern catalogued under this name in March 2015. It was hailed as the first p2 rake, but Josh Ball’s c p2 backrake from July 2014 is earlier."),
]:
    f = BY_TITLE[title]
    entries.append({"name": name, "desc": desc, "rle": f["rle"], "credit": NAMES.get(f["by"], f["by"]),
                    "source": "forum", "url": post_url(f["post"]), "captured": f["date"]})

# Families in Nico Brown's organized c/2 collection (forum, 2014-12-29), named in private messages
# between Luke and Nico that week: rows of horned, unicorn, hippo and buffalo ships, and the fox ship.
C2 = json.loads((DATA / "c2_families.json").read_text())
C2_POST = post_url("p15361")
for name, key, desc, credit in [
    ("horned ship", "horned",
     "Any of a family of p4 and p8 c/2 spaceships sharing the front end of the horned rake. Nico Brown’s 2014 collection has {count}; "
     "the smallest, shown below, has a minimum population of {minpop} cells.", "Nico Brown (glider_rider)"),
    ("hippo ship", "hippo",
     "Any of a family of p4 c/2 spaceships with the same front-end mechanism. Nico Brown’s 2014 collection has {count}; "
     "the smallest, shown below, has a minimum population of {minpop} cells. The original hippo ship page is lost, and no surviving source records who found the first one.", "discoverer not recorded"),
    ("buffalo ship", "buffalo",
     "Any of a family of p4 and p8 c/2 spaceships with even bilateral symmetry, found by Arie Paap with gfind and WinLifeSearch in August 2014. "
     "Nico Brown’s 2014 collection has {count} with the buffalo front end; the smallest, shown below, has a minimum population of {minpop} cells.",
     "Arie Paap (wildmyron)"),
    ("fox ship", "fox",
     "The following p4 c/2 spaceship with a minimum population of {minpop} cells, the one ship in Nico Brown’s 2014 collection that fit no family. "
     "Named by its discoverer because all four phases resemble canines.", "Nico Brown (glider_rider)"),
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

news = []
for f in FORUM:
    who = NAMES.get(f["by"], f["by"])
    news.append({"date": f["date"], "source": "forum",
                 "paras": [f'<strong>{f["title"]}</strong> by {who}. {f["note"]} '
                           f'<a href="{post_url(f["post"])}">Forum post</a>.'],
                 "rle": f["rle"]})
news += [
    {"date": "2012-07-22", "source": "forum", "paras": [
        f'Josh Ball (velcrorex) posts the first c/4 orthogonal spaceship, later named the beachcomber ship, to the '
        f'<a href="{THREAD}">Live Free or Die thread</a> on the ConwayLife forums (started in 2011). A week later he asks whether the '
        "Verizon site was saved anywhere, and Paul Tooke points to its March 2008 Wayback Machine snapshot."]},
    {"date": "2013-10-12", "source": "forum", "paras": [
        "Luke, pointed to the thread by Andrew Trevorrow, announces <em>lfod.wikispaces.com</em>, built over the previous week or two. "
        "Its pattern collection is dated October 14, 2013."]},
    {"date": "2014-07-04", "source": "forum", "paras": [
        "Luke offers cash prizes: $25 for a spaceship of a new speed, $25 for a moon reflector, $50 for a stable moon reflector."]},
    {"date": "2014-12-29", "source": "private messages", "paras": [
        "Luke and Nico Brown sort Nico’s collection of 122 c/2 spaceships by front end. The rows become the "
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
    {"date": "2020-10-21", "source": "forum", "paras": [
        "Peter Naszvadi bumps the thread for a new result on LifeWiki: a W110 unit cell, which emulates the one-dimensional "
        "Rule 110 cellular automaton (itself known to be universal) in Live Free or Die."]},
    {"date": "2020-11-12", "source": "forum", "paras": [
        "FWKnightship builds the puffer setup LaundryPizza03 asked for, laying a pattern of dots that leads to superlinear growth."]},
    {"date": "2022-01-09", "source": "forum", "paras": [
        "Luke returns to the thread, having found that Wikispaces shut down without his noticing."]},
    {"date": "2025-05-26", "source": "forum", "paras": [
        "Game of Life Fun builds the first MMM breeder, after a long series of rakes, puffers and breeders at many new periods."]},
    {"date": "2025-09-06", "source": "forum", "paras": [
        "LaundryPizza03 adds the archived wiki’s names to the Glider Database, turning up earlier discoverers for some ships."]},
    {"date": "2026-10-26", "source": "restoration", "paras": [
        'The site is rebuilt from the 2009 source files, Wayback captures, and the forum. See <a href="restoration.html">About this restoration</a>.']},
]

challenges = f"""
<p>The 2013 wiki kept this page going, adding cash prizes in July 2014: $25 for a spaceship of a new speed, $25 for any
moon reflector, and $50 for a stable moon reflector. Several of the 2008 challenges have since been answered:</p>
<ul>
<li><strong>A gun</strong>: the p4 <a href="glossary.html#moon-laser">moon laser</a>, by Matthias Merzenich (August 2012). A much smaller p5 moon gun followed from Arie Paap in August 2016.</li>
<li><strong>c/3 and c/4 orthogonal spaceships</strong>: the <a href="glossary.html#wasp-ship">wasp ship</a> (Michael Simkin, October 2014, which won a prize) and the <a href="glossary.html#beachcomber-ship">beachcomber ship</a> (Josh Ball, July 2012).</li>
<li><strong>Period 10</strong>: the <a href="glossary.html#decade-ship">decade ship</a> (Paul Tooke, 2012), then p10 puffers (Arie Paap, 2015).</li>
<li><strong>p2 rakes and puffers</strong>: Josh Ball’s c p2 backrake (July 2014) and the <a href="glossary.html#flicker-rake">flicker rake</a> (Nico Brown, 2015).</li>
<li><strong>c/2 rakes</strong>: Josh Ball’s c/2 backrake (July 2014), then the <a href="glossary.html#buffalo-rake">buffalo rake</a>, <a href="glossary.html#horned-rake">horned rake</a> and hippo rake (by 2015).</li>
<li><strong>Breeders</strong>: the first, an MMS breeder, by Arie Paap (March 2015). Game of Life Fun built the first MMM breeder in May 2025.</li>
<li><strong>Universality</strong>: a W110 unit cell, emulating Rule 110 (2020, on LifeWiki).</li>
</ul>
<p>As of the wiki’s Challenges page in April 2015, no moon reflector, knightship, spacefiller or replicator was known, and there were no objects at period 11, 13, 14 or 15.</p>
"""

contributors = (", and, after 2012, <strong>Paul Tooke</strong>, <strong>Matthias Merzenich</strong>, "
                "<strong>Arie Paap</strong> (wildmyron), <strong>Michael Simkin</strong>, <strong>Nico Brown</strong> (glider_rider), "
                "and many others on the ConwayLife forums, including <strong>Game of Life Fun</strong>, praosylen, AforAmpere, "
                "confocaloid and FWKnightship. The Glider Database credits earlier finds of the key ship to Peter Naszvadi (2001) "
                "and the robot ship to Alex Fink (2000)")

# Later files.
out = DATA / "later-files"
out.mkdir(exist_ok=True)
files = []
coll = ROOT / "archive/wikispaces/collection-2013/Live Free or Die collection"
readme = (coll / "readme.txt").read_text()
for p in sorted(coll.rglob("*.rle")):
    m = re.search(re.escape(p.name) + r" (.+?)\n", readme)
    desc = m.group(1) if m else ""
    desc = re.sub(r"^(is|has|includes|shows|gives) ", "", desc)
    fname = "2013 " + (f"Flotillas - {p.name}" if p.parent.name == "Flotillas" else p.name)
    shutil.copy(p, out / fname)
    files.append({"name": fname[5:-4], "file": fname, "desc": (desc[:1].upper() + desc[1:]) + " (wiki collection, October 2013)"})
SCRATCH = Path(sys.argv[1]) if len(sys.argv) > 1 else None
for src, name, date in [("att_482", "Nico Brown c/2 collection (first version)", "December 25, 2014"),
                        ("att_485", "Nico Brown c/2 collection", "December 29, 2014")]:
    dest = out / (name.replace("c/2", "c2") + ".rle")
    if SCRATCH and (SCRATCH / src).exists():
        cells = parse_macrocell((SCRATCH / src).read_text())
        dest.write_text("#C " + name + ", posted to the ConwayLife forum " + date + "\n" + to_rle(cells))
    if dest.exists():
        files.append({"name": name, "file": dest.name,
                      "desc": f"Nico Brown’s (glider_rider) collection of c/2 spaceships and rakes, posted as a Golly macrocell on {date}; converted to RLE."
                              + (" Grouped by front end: rakes at top; then rows of horned ships and unicorn ships; then four hippo ships and, "
                                 "to their right, the fox ship; and buffalo ships at the bottom." if "first" not in name else "")})

later = {"entries": entries, "news": news, "files": files, "challenges_html": challenges,
         "contributors_html": contributors,
         "periods_note": "Since 2009, the first p10 objects (the decade ship and p10 puffers) have been found, along with new p3, p5 and p9 objects "
                         "and many high-period rakes and breeders. See the <a href=\"news.html\">News</a> page."}
(DATA / "later.json").write_text(json.dumps(later, indent=1, ensure_ascii=False))
print(len(entries), "entries,", len(news), "news,", len(files), "files")
