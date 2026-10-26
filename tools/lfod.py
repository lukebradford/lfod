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
