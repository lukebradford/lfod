"""Read the July 2008 iteration diagrams (8-pixel cell grids saved as JPEG) into data/iterations.json,
so build.py can redraw them as clean SVG.

Each cell is classified by the average color of its center; a circle is detected by its dark ring,
which overlaps the one-pixel gap around the cell.

Usage: python3 tools/extract_iterations.py   (needs Pillow)
"""
import json
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "archive/images/iterations"

def classify(rgb):
    r, g, b = rgb
    if min(rgb) > 236:
        return None
    if max(rgb) < 80:
        return "black"
    if max(rgb) - min(rgb) < 40:
        return "gray"
    if r > g and r > b:
        return "red"
    if b > r and b >= g:
        return "blue"
    return "green"

def read(path):
    im = Image.open(path).convert("RGB")
    W, H = im.size
    cols, rows = (W - 1) // 8, (H - 1) // 8
    cells = []
    for y in range(rows):
        for x in range(cols):
            px = [im.getpixel((8*x + i, 8*y + j)) for i in range(3, 6) for j in range(3, 6)]
            color = classify(tuple(sum(p[k] for p in px) // 9 for k in range(3)))
            if not color:
                continue
            ring = [im.getpixel(q) for q in ((8*x + 4, 8*y), (8*x + 4, min(8*y + 8, H - 1)),
                                             (8*x, 8*y + 4), (min(8*x + 8, W - 1), 8*y + 4))]
            circle = color != "black" and sum(max(p) < 90 for p in ring) >= 3
            cells.append([x, y, color] + (["circle"] if circle else []))
    return {"cols": cols, "rows": rows, "cells": cells}

out = {p.name: read(p) for p in sorted(SRC.glob("* iterations.jpg"))}
(ROOT / "data/iterations.json").write_text(json.dumps(out, separators=(",", ":")))
print(len(out), "diagrams")
