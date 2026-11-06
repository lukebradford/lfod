"""Pull selected, credited patterns from the ConwayLife 'Live Free or Die' thread (t=649).

Usage: python3 tools/extract_forum.py <t649_clean.txt>
The cleaned thread text is not kept in this repo; only the selected patterns are,
with poster, date and post link. Block numbers count [CODE] blocks from the top of the thread.
Dates in the cleaned text can run a day late; data/forum_patterns.json was corrected by hand to the
dates the forum displays, so check them again after re-running.
"""
import json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from lfod import parse_rle, classify, to_rle, normalize

SELECT = [
    # (block, title, note)
    (6, "Ram ship posted to the forum", "Josh Ball’s 37-cell p4 c/4 diagonal spaceship, the smallest known diagonal spaceship, which this site catalogued as the ram ship in "
        '<a href="news.html#d2008-12-09">December 2008</a>. Paul Tooke posted it in reply to Josh Ball’s c/4 orthogonal ship, '
        "an hour after pointing to the Wayback snapshot of the Verizon site."),
    (9, "p10 c/5 ship (decade ship)", "The first p10 object in the rule; named the decade ship on the wiki."),
    (10, "p4 moon gun (moon laser)", "The first gun in Live Free or Die, a double-barreled p4 moon gun. Named the moon laser on the wiki."),
    (11, "Two growing spaceships", "Two craft whose fronts travel at c while their back ends travel at c/5 and c/3, so they grow longer as they go."),
    (16, "p12 anchor track flotillas", "Two p12 ships built from anchor tracks; the second contains several p252 oscillators."),
    (18, "p8 c/2 ship", "A new p8 c/2 spaceship that deletes its trails of dots like the dust mite ship."),
    (20, "c/2 p4 spaceship and backrake", "Luke: “only the second known rake/puffer slower than c”, after Josh Ball’s c/5 backrake."),
    (21, "c p4 side rake", "The smallest-period side rake, and the first sideways rake that isn’t a flotilla."),
    (24, "c p2 backrake", "Luke: “the first known rake or puffer at p2.” Checked by simulation: the front end repeats every 2 generations."),
    (25, "c p6 side rake", "A p6 side rake; the basic mechanism leaves debris, so a flotilla cleans it up."),
    (27, "New p4 oscillators and a big six shooter stack", "Includes the oscillators catalogued as shortwave and longwave, and a new way to connect big six shooters."),
    (29, "Buffalo ships", "A family of p4 c/2 ships with even bilateral symmetry, found with gfind and WLS. Catalogued as the buffalo ships."),
    (31, "Buffalo rake and ship", "A p4 c/2 back rake; catalogued as the buffalo rake, then the smallest known c/2 puffer or rake."),
    (32, "Buffalo bird", "A tagalong that can hop onto most known c/2 ships; it only needs two diagonally adjacent cells in its third generation."),
    (33, "p3 puffers (bent tricycle puffer)", "A variation of the tricycle puffer and a single dot puffer."),
    (38, "Wave-riding ship", "A p6 ship carrying an infinitely growing wave, found with WinLifeSearch using “don’t care” cells."),
    (42, "c/3 ship (wasp ship)", "The first c/3 spaceship, which won one of Luke’s cash prizes. Named the wasp ship."),
    (50, "Extended wasp ships", "Luke found that the wasp ship can be made longer: this one trails two long diagonal arms."),
    (54, "c/2 backrake", "A p4 c/2 backward moon rake, which Nora Brown named the horned rake."),
    (55, "c/2 backrake stabilized into a ship", "The backrake with a component that eats the moons."),
    (56, "Sawtooth", "A sawtooth: a c/2 ship adds a moon eater to a stream of moons, which a pair of monsters then destroys."),
    (57, "p5 oscillator (crossroads)", "The second p5 oscillator after the starfish. Named crossroads."),
    (63, "Short free ship rake (freedom collider)", "A p8 backward short free ship rake: apart from flotillas, the first rake that emits anything other than moons."),
    (65, "Anchored freedom collider", "Luke’s anchored version of the freedom collider, posted the same day, with an initial population of 34 cells."),
    (67, "Tiny c/2 ships (fruit fly ship)", "The one at the bottom, with a minimum population of 36, tied the dust mite ship as the smallest c/2 ship. Named the fruit fly ship."),
    (68, "Small c/2 ships", "Three p4 c/2 ships, with minimum populations of 46, 89 and 96 cells; Luke noted that the 96-cell one was a known unicorn ship."),
    (80, "p9 dot puffer", "The first p9 object other than the arrow puffers."),
    (84, "p10 puffers", "The first p10 puffers, and the only p10 craft that travel at c."),
    (87, "MMS breeder", "The first breeder in Live Free or Die."),
    (88, "p5 c spaceship", "A p5 c spaceship with a minimum population of 250 cells; the smallest p5 c ship, the nickel ship, has 98."),
    (90, "p2 rake (flicker rake)", "A p2 rake, the second after Josh Ball’s July 2014 backrake (Luke hailed it as the first, but the earlier one is also p2). Luke named it the flicker rake on March 24, 2015."),
    (115, "p2 wick puffer, stabilized", "A p2 puffer whose wick is stabilized at the end."),
    (138, "p5 moon gun", "A surprisingly small p5 moon gun, the second known working gun."),
    (140, "Bow tie", "A p5 oscillator suggested by the stabilization of the p5 moon gun, and the fourth known p5 oscillator."),
    (147, "Short-necked giraffe", "A smaller relative of the c/4 diagonal giraffe ship."),
    (151, "5-dot seed for infinite growth", "A moon hitting five dots sets off a reaction that grows forever, its population rising linearly. In 2020 LaundryPizza03 asked for puffers that lay this pattern again and again, which FWKnightship built."),
    (173, "Completed almost-rake", "Luke’s old near-rake, completed four years later."),
    (230, "p9 puffer", "A p9 c puffer with an initial population of 268 cells, the first new p9 object in the thread since Arie Paap’s p9 puffers of 2015."),
    (277, "Small periodic MMS breeder", "A much smaller periodic breeder, part of a large 2025 survey of rakes and breeders."),
    (281, "Tiny p12 and p24 free ship rakes", "Very small free ship rakes, from the same series."),
    (258, "c/5 spaceship collection", "Three p5 c/5 ships, at least two already known, in whose evolution all 102 isotropic neighborhood conditions occur."),
    # Later additions, chosen from a full read of the thread in November 2026. An optional crop (x0, y0, x1, y1) keeps one object of a block.
    (134, "p12 sideways free ship rake", "A 65-cell p12 flotilla of three p6 ships, a p6 puffer and a p4 ship, which fires free ships to both sides. "
          "It uses no anchor tracks: until then, every known free ship rake was an anchor track flotilla."),
    (359, "Plus ship rake", "A p48 sideways rake that fires plus ships. Every earlier rake fired moons, free ships or short free ships, so this was the first rake "
          "for a p4 spaceship. Added on June 2 to a post first made on May 28."),
    (89, "p5 oscillator with four starfish", "A p5 oscillator in which four starfish hassle some junk, with a minimum population of 328 cells. "
         "It was the third known p5 oscillator, after the starfish and crossroads; the bow tie (2016) was the fourth."),
    (150, "Extensible c/4 diagonal ship", "A c/4 diagonal spaceship with a minimum population of 409 cells, which praosylen posted as an "
          "“extensible c/4 diagonal pseudo-pushalong”. A ram ship is part of it."),
    (41, "Ship with a cut-off wave", "Luke had wondered whether the wave carried by the wave-riding ship could be cut off so that it stops growing. "
         "Josh Ball replied with this p6 c spaceship, which carries a finite wave and has a minimum population of 823 cells."),
    (98, "Dual lever wick", "From Arie Paap’s survey of p2 patterns: the lever wick, a p2 wick made of one phase of the lever, doubled, ended by two different "
         "p4 terminations and turned by a p2 mirror in the middle. Both patterns are p4 oscillators."),
    (108, "Pond agar oscillator", "From the same survey: a p2 oscillator with a 9 × 9 grid of ponds (3 × 3 boxes) at its center. "
          "The ponds form an agar, a periodic pattern that fills the plane, and Arie Paap was looking for a way to stabilize its edges."),
    (111, "p2 c spaceship", "From the same survey: a p2 c spaceship with a minimum population of 98 cells. "
          "Until then, the flicker ship and flutter ship were the only known p2 spaceships."),
    (116, "Smaller trilogy", "A p3 oscillator with a minimum population of 52 cells, which Arie Paap described as a smaller variation of the trilogy "
          "(whose smallest form has 62). It comes from his collection of small p3 oscillators.", (54, 49, 74, 69)),
    (86, "Anchor track puffer", "A p8 puffer that lays anchor tracks, with a trailer that cleans up the puffer’s stray dots. It can be extended to lay "
         "tracks of any length, so there are puffers whose trails have any period an anchor track can have, 4 × 2ⁿ − 4."),
    (389, "18-cell moon rake", "A p4 c backward moon rake with an initial population of 18 cells, the smallest known rake. The pocket rake, "
          "the smallest known before it, has 32. It is the first of three p4 moon backrakes in a long post of new rakes and puffers, "
          "which also holds the first rakes for p12 freedom fighter ships and p6 hex ships.", (0, 0, 17, 5)),
]

POST = re.compile(r"^#(\d+)\s+post (p\d+)\s+by (.+?)\s+at (\d{4}-\d\d-\d\d)", re.M)
text = open(sys.argv[1]).read()
posts = [(m.start(), m.group(2), m.group(3), m.group(4)) for m in POST.finditer(text)]
blocks = []
for m in re.finditer(r"\[CODE\](.*?)\[/CODE\]", text, re.S):
    owner = max((p for p in posts if p[0] < m.start()), key=lambda p: p[0])
    blocks.append((m.group(1), owner))

out = []
for n, title, note, *crop in SELECT:
    body, (_, pid, who, date) = blocks[n - 1]
    lines = [l.strip() for l in body.strip().splitlines() if l.strip() and not l.startswith("#")]
    cells = parse_rle("\n".join(lines))
    if crop:
        x0, y0, x1, y1 = crop[0]
        cells = {(x, y) for x, y in cells if x0 <= x <= x1 and y0 <= y <= y1}
    kind, per, d, _ = classify(cells, 300) if len(cells) < 3000 else ("other", None, None, None)
    out.append({"title": title, "by": who, "date": date, "post": pid, "note": note,
                "rle": to_rle(cells), "pop": len(cells), "kind": kind, "period": per,
                "disp": list(d) if d else None})
    print(f"{n:4} {date} {who:12} {title[:40]:40} pop={len(cells):6} {kind} p={per} d={d}")
(ROOT / "data/forum_patterns.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
