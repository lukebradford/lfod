"""Minimal Live Free or Die (B2/S0) simulator and RLE helpers."""
import re
from collections import Counter

def parse_rle(rle):
    lines = [l for l in rle.strip().splitlines() if not l.startswith("#")]
    body = "".join(l.strip() for l in lines if not re.match(r"\s*x\s*=", l))
    cells, x, y, n = set(), 0, 0, ""
    for ch in body:
        if ch.isdigit():
            n += ch; continue
        k = int(n) if n else 1; n = ""
        if ch in "bB.":
            x += k
        elif ch in "oOA":
            for i in range(k): cells.add((x + i, y))
            x += k
        elif ch == "$":
            y += k; x = 0
        elif ch == "!":
            break
    return cells

def step(cells):
    counts = Counter((x + dx, y + dy) for x, y in cells
                     for dx in (-1, 0, 1) for dy in (-1, 0, 1) if dx or dy)
    born = {c for c, n in counts.items() if n == 2 and c not in cells}
    survive = {c for c in cells if counts.get(c, 0) == 0}
    return born | survive

def normalize(cells):
    if not cells: return frozenset(), (0, 0)
    mx = min(x for x, _ in cells); my = min(y for _, y in cells)
    return frozenset((x - mx, y - my) for x, y in cells), (mx, my)

def bbox(cells):
    xs = [x for x, _ in cells]; ys = [y for _, y in cells]
    return max(xs) - min(xs) + 1, max(ys) - min(ys) + 1

def to_rle(cells, rule="B2/S0"):
    shape, _ = normalize(cells)
    w, h = bbox(shape) if shape else (0, 0)
    rows = []
    for y in range(h):
        row, run, cur = "", 0, None
        line = ["o" if (x, y) in shape else "b" for x in range(w)]
        while line and line[-1] == "b": line.pop()
        for ch in line + [None]:
            if ch == cur: run += 1; continue
            if cur: row += (str(run) if run > 1 else "") + cur
            cur, run = ch, 1
        rows.append(row)
    out, blank = "", 0
    for i, r in enumerate(rows):
        if i: blank += 1
        if r or i == len(rows) - 1:
            if i: out += (str(blank) if blank > 1 else "") + "$"
            out += r; blank = 0
    body = out + "!"
    wrapped = "\n".join(body[i:i + 70] for i in range(0, len(body), 70))
    return f"x = {w}, y = {h}, rule = {rule}\n{wrapped}"

def classify(cells, maxgen=400):
    """Return (kind, period, (dx,dy)) for oscillators/spaceships; puffers etc. -> ('other',...)."""
    start, off0 = normalize(cells)
    cur = set(cells)
    pops = [len(cur)]
    for g in range(1, maxgen + 1):
        cur = step(cur)
        pops.append(len(cur))
        if not cur:
            return ("dies", g, None, pops)
        shape, off = normalize(cur)
        if shape == start:
            d = (off[0] - off0[0], off[1] - off0[1])
            return ("oscillator" if d == (0, 0) else "spaceship", g, d, pops)
        if len(cur) > 20000:
            break
    return ("other", None, None, pops)

def parse_life105(text):
    """Life 1.05 (#P blocks of . and * rows) -> set of cells."""
    cells, ox, oy, row = set(), 0, 0, 0
    for line in text.splitlines():
        line = line.rstrip()
        if line.startswith("#P"):
            _, x, y = line.split()[:3]
            ox, oy, row = int(x), int(y), 0
        elif line.startswith("#") or not line:
            continue
        else:
            for i, ch in enumerate(line):
                if ch in "*O":
                    cells.add((ox + i, oy + row))
            row += 1
    return cells

def load_pattern(text):
    """Return cells from either RLE or Life 1.05 text."""
    if any(l.startswith("#Life 1.05") or l.startswith("#P") for l in text.splitlines()[:5]):
        return parse_life105(text)
    return parse_rle(text)

def parse_macrocell(text):
    """Golly macrocell (.mc) for two-state rules -> set of cells."""
    nodes = [None]  # 1-indexed; 0 means empty
    for line in text.splitlines():
        line = line.strip()
        if not line or line[0] in "#[":
            continue
        if line[0] in ".*$":
            cells, x, y = set(), 0, 0
            for ch in line:
                if ch == "$":
                    x, y = 0, y + 1
                elif ch == "*":
                    cells.add((x, y)); x += 1
                else:
                    x += 1
            nodes.append(("leaf", cells))
        else:
            k, a, b, c, d = map(int, line.split())
            nodes.append((k, a, b, c, d))
    out = set()
    def emit(i, ox, oy):
        if i == 0:
            return
        n = nodes[i]
        if n[0] == "leaf":
            out.update((ox + x, oy + y) for x, y in n[1])
            return
        k, a, b, c, d = n
        h = 1 << (k - 1)
        emit(a, ox, oy); emit(b, ox + h, oy); emit(c, ox, oy + h); emit(d, ox + h, oy + h)
    emit(len(nodes) - 1, 0, 0)
    return out

# ---------------------------------------------------------------- object statistics

_TRANSFORMS = [lambda x, y: (x, y), lambda x, y: (-x, y), lambda x, y: (x, -y), lambda x, y: (-x, -y),
               lambda x, y: (y, x), lambda x, y: (-y, -x), lambda x, y: (-y, x), lambda x, y: (y, -x)]

def _same(cells, f):
    shape = normalize(cells)[0]
    return normalize({f(x, y) for x, y in shape})[0] == shape

def symmetry_code(phases):
    """The 2009 tables' symmetry code for the most symmetric phase, or G for glide symmetry:
    O eight-way, I four-way mirror, / four-way diagonal, R four-way rotational, D diagonal mirror,
    M orthogonal mirror, S two-way rotational."""
    best = max(({i for i, f in enumerate(_TRANSFORMS) if _same(ph, f)} for ph in phases), key=len)
    for code, need in (("O", set(range(8))), ("I", {1, 2}), ("/", {4, 5}), ("R", {6})):
        if need <= best:
            return code
    if best & {4, 5}:
        return "D"
    if best & {1, 2}:
        return "M"
    if 3 in best:
        return "S"
    p = len(phases)
    if p % 2 == 0:
        half = normalize(phases[p // 2])[0]
        start = normalize(phases[0])[0]
        if any(normalize({f(x, y) for x, y in start})[0] == half for f in _TRANSFORMS[1:]):
            return "G"
    return ""

def _speed(d, p):
    from math import gcd
    a, b = sorted((abs(d[0]), abs(d[1])), reverse=True)
    if a == 0:
        return ""
    if b and b != a:
        return f"({a},{b})c/{p}"
    g = gcd(a, p)
    n, m = a // g, p // g
    return ("c" if n == 1 else f"{n}c") + (f"/{m}" if m > 1 else "") + ("d" if b else "")

def object_stats(cells, maxgen=800):
    """Population, period, speed, box and symmetry of an oscillator or spaceship, as in the 2009 tables:
    the box spans the widest and tallest phases, oscillators list the shorter side first and
    spaceships the side along their direction of travel."""
    kind, p, d, _ = classify(cells, maxgen)
    if kind not in ("oscillator", "spaceship"):
        return None
    phases, cur = [], set(cells)
    for _ in range(p):
        phases.append(cur)
        cur = step(cur)
    pops = [len(ph) for ph in phases]
    w = max(bbox(ph)[0] for ph in phases)
    h = max(bbox(ph)[1] for ph in phases)
    if kind == "oscillator":
        w, h = sorted((w, h))
    elif abs(d[1]) > abs(d[0]):
        w, h = h, w
    return dict(kind=kind, min=min(pops), avg=sum(pops) / p, max=max(pops), period=p,
                speed=_speed(d, p), box=(w, h), sym=symmetry_code(phases))

def front_period(cells, gun=False, warmup=240, maxp=60):
    """Period and speed of a puffer or rake, from the leading edge of its evolution;
    for a gun, the period of the region it started in."""
    gens, cur = [set(cells)], set(cells)
    for _ in range(warmup + maxp):
        cur = step(cur)
        gens.append(cur)
    x0 = min(x for x, _ in cells); x1 = max(x for x, _ in cells)
    y0 = min(y for _, y in cells); y1 = max(y for _, y in cells)
    span = max(x1 - x0, y1 - y0) + 2
    def edge(c, axis, sign):
        m = max(q[axis] * sign for q in c)
        return {q for q in c if q[axis] * sign > m - span}, m
    found = []
    for axis in ((0, 1) if not gun else ()):
        for sign in (1, -1):
            f0, m0 = edge(gens[warmup], axis, sign)
            for p in range(1, maxp + 1):
                f1, m1 = edge(gens[warmup + p], axis, sign)
                s = m1 - m0
                if s > 0 and {(x - s * sign, y) if axis == 0 else (x, y - s * sign) for x, y in f1} == f0:
                    found.append((p, s))
                    break
    if found:
        # A rake's leading edge in its exhaust direction is a stream of spaceships, whose period
        # divides the rake's; the engine's edge gives the longest period.
        p, s = max(found)
        return p, _speed((s, 0), p)
    box = lambda c: {q for q in c if x0 <= q[0] <= x1 and y0 <= q[1] <= y1}
    base = box(gens[warmup])
    for p in range(1, maxp + 1):
        if box(gens[warmup + p]) == base:
            return p, ""
    return None, ""
