"""Pull selected, credited patterns from the ConwayLife 'Live Free or Die' thread (t=649).

Usage: python3 tools/extract_forum.py <t649_clean.txt>
The cleaned thread text is not kept in this repo; only the selected patterns are,
with poster, date and post link. Block numbers count [CODE] blocks from the top of the thread.
"""
import json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from lfod import parse_rle, classify, to_rle, normalize

SELECT = [
    # (block, title, note)
    (6, "c/4 diagonal ship", "A c/4 diagonal spaceship, posted while the forum was trying to recover the Verizon site."),
    (9, "p10 c/5 ship (decade ship)", "The first p10 object in the rule; named the decade ship on the wiki."),
    (10, "p4 moon gun (moon laser)", "The first gun in Live Free or Die, a double-barreled p4 moon gun. Named the moon laser on the wiki."),
    (11, "Two growing spaceships", "Spaceships that grow as they travel."),
    (16, "p12 anchor track flotillas", "Two p12 ships built from anchor tracks; the second contains several p252 oscillators."),
    (18, "p8 c/2 ship", "A new p8 c/2 spaceship that deletes its trails of dots like the dust mite ship."),
    (20, "c/2 p4 spaceship and backrake", "Only the second known rake or puffer slower than c. Catalogued on the wiki (probably as the hippo rake)."),
    (21, "c p4 side rake", "The smallest-period side rake, and the first sideways rake that isn’t a flotilla."),
    (24, "c p2 backrake", "Luke: “the first known rake or puffer at p2.”"),
    (25, "c p6 side rake", "A p6 side rake with a cleanup flotilla (probably the hex rake on the wiki)."),
    (27, "New p4 oscillators and a big six shooter stack", "Includes the oscillators catalogued as shortwave and longwave, and a new way to connect big six shooters."),
    (29, "Buffalo ships", "A family of p4 c/2 ships with even bilateral symmetry, found with gfind and WLS. Catalogued as the buffalo ships."),
    (31, "Buffalo rake and ship", "A p4 c/2 back rake; catalogued as the buffalo rake, then the smallest known c/2 puffer or rake."),
    (32, "Buffalo bird", "A tagalong that can hop onto most known c/2 ships; it only needs two diagonally adjacent cells in its third generation."),
    (33, "p3 puffers (bent tricycle puffer)", "A variation of the tricycle puffer and a single dot puffer."),
    (38, "Wave-riding ship", "A p6 ship carrying an infinitely growing wave, found with WinLifeSearch using “don’t care” cells."),
    (42, "c/3 ship (wasp ship)", "The first c/3 spaceship, which won one of Luke’s cash prizes. Named the wasp ship."),
    (50, "Extended wasp ships", "The wasp ship is extensible."),
    (54, "c/2 backrake", "A c/2 backrake."),
    (55, "c/2 backrake stabilized into a ship", "The backrake with a component that eats the moons."),
    (56, "Sawtooth", "A sawtooth: a c/2 ship adds a moon eater to a stream of moons, which a pair of monsters then destroys."),
    (57, "p5 oscillator (crossroads)", "The second p5 oscillator after the starfish. Named crossroads."),
    (63, "Short free ship rake (freedom collider)", "A p8 backward short free ship rake: apart from flotillas, the first rake that emits anything other than moons."),
    (65, "Anchored freedom collider", "The freedom collider can be anchored."),
    (67, "Tiny c/2 ships (fruit fly ship)", "The one on the left, with a minimum population of 36, tied the dust mite ship as the smallest c/2 ship. Named the fruit fly ship."),
    (68, "Small c/2 ships", "Small c/2 ships."),
    (80, "p9 dot puffer", "The only known p9 object other than the arrow puffer."),
    (84, "p10 puffers", "The first p10 puffers, and the only p10 craft that travel at c."),
    (87, "MMS breeder", "The first breeder in Live Free or Die."),
    (88, "p5 c spaceship", "A p5 c spaceship."),
    (90, "p2 rake (flicker rake)", "The first p2 rake, catalogued as the flicker rake."),
    (115, "p2 wick puffer, stabilized", "A p2 puffer whose wick is stabilized at the end."),
    (138, "p5 moon gun", "A surprisingly small p5 moon gun: the second gun ever, at a new period."),
    (140, "Bow tie", "A p5 oscillator."),
    (147, "Short-necked giraffe", "A smaller relative of the c/4 diagonal giraffe ship."),
    (151, "5-dot seed for infinite growth", "A five-dot seed for infinite growth."),
    (173, "Completed almost-rake", "Luke’s old near-rake, completed four years later."),
    (230, "p9 puffer", "A p9 puffer."),
    (277, "Small periodic MMS breeder", "A much smaller periodic breeder, part of a large 2025 survey of rakes and breeders."),
    (281, "Tiny p12 and p24 free ship rakes", "Very small free ship rakes, from the same series."),
    (258, "c/5 spaceship collection", "Three p5 c/5 ships that together exhibit all 102 isotropic neighborhood conditions."),
]

POST = re.compile(r"^#(\d+)\s+post (p\d+)\s+by (.+?)\s+at (\d{4}-\d\d-\d\d)", re.M)
text = open(sys.argv[1]).read()
posts = [(m.start(), m.group(2), m.group(3), m.group(4)) for m in POST.finditer(text)]
blocks = []
for m in re.finditer(r"\[CODE\](.*?)\[/CODE\]", text, re.S):
    owner = max((p for p in posts if p[0] < m.start()), key=lambda p: p[0])
    blocks.append((m.group(1), owner))

out = []
for n, title, note in SELECT:
    body, (_, pid, who, date) = blocks[n - 1]
    lines = [l.strip() for l in body.strip().splitlines() if l.strip() and not l.startswith("#")]
    cells = parse_rle("\n".join(lines))
    kind, per, d, _ = classify(cells, 300) if len(cells) < 3000 else ("other", None, None, None)
    out.append({"title": title, "by": who, "date": date, "post": pid, "note": note,
                "rle": to_rle(cells), "pop": len(cells), "kind": kind, "period": per,
                "disp": list(d) if d else None})
    print(f"{n:4} {date} {who:12} {title[:40]:40} pop={len(cells):6} {kind} p={per} d={d}")
(ROOT / "data/forum_patterns.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
