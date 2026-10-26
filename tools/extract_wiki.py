"""Turn recovered lfod.wikispaces.com page texts into data/wiki.json.

The page texts in archive/wikispaces/pages-text were extracted from Wayback
Machine captures (2015-04-22, 2016-10-14, 2018-03-25). Links appear as
'text [->target]' and images as '[IMG ...]'. The newest capture of each page wins.
"""
import json, re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "archive/wikispaces/pages-text"

pages = {}
for f in sorted(SRC.glob("*.txt")):
    if "__" not in f.stem:
        continue
    stamp, name = f.stem.split("__", 1)
    text = f.read_text()
    m = re.search(r"^TITLE: Live Free or Die Wiki - (.+)$", text, re.M)
    if not m:
        continue
    title = m.group(1).strip()
    pages[title] = (stamp, text)  # sorted by timestamp, so later captures overwrite

def strip_links(s):
    s = re.sub(r"\s*\[->[^\]]*\]", "", s)
    return re.sub(r"\s+", " ", s).strip()

out = []
for title, (stamp, text) in sorted(pages.items()):
    body = text.split("\n", 3)[-1]
    paras, rles, in_rle = [], [], False
    for block in re.split(r"\n\s*\n", body):
        b = block.strip()
        if not b or b.startswith("[IMG") or b.startswith("SOURCE FILE"):
            continue
        if re.match(r"x\s*=\s*\d+", b):
            in_rle = True
            head, _, rest = b.partition("\n")
            rles.append([head, rest.replace("\n", "")])
            continue
        if in_rle and re.fullmatch(r"[0-9bo$!\s]+", b):
            rles[-1][1] += b.replace("\n", "")
            continue
        in_rle = False
        paras.append(strip_links(b))
    rles = [h + "\n" + body for h, body in rles]
    rle = rles[0] if rles else ""
    desc = " ".join(paras)
    credit = ""
    m = re.search(r"Discovered by ([A-Za-z][\w.]*(?: [A-Z][\w.]*)*?)(?: \(|[.,;]| in | and )", desc)
    if m:
        credit = m.group(1).rstrip(".")
    out.append({"name": title, "captured": f"{stamp[:4]}-{stamp[4:6]}-{stamp[6:8]}", "paras": paras,
                "desc": desc, "rle": rle, "extra_rles": rles[1:], "credit": credit})
(ROOT / "data/wiki.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
print(len(out), "wiki pages;", sum(1 for e in out if e["rle"]), "with RLE")
for e in out:
    print(f'{e["name"][:26]:26} {e["captured"]} rle={"y" if e["rle"] else "-"} credit={e["credit"]!r}')
