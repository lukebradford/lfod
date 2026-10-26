"""Parse the 2009 Word-exported glossary.htm into structured JSON entries."""
import json, re, sys
from bs4 import BeautifulSoup

src, out = sys.argv[1], sys.argv[2]
html = open(src, encoding="windows-1252").read()
# Word wraps images in conditional comments; expose the VML imagedata tags.
html = html.replace("<![if !vml]>", "").replace("<![endif]>", "")
soup = BeautifulSoup(html, "html.parser")

def clean(t):
    t = t.replace("\xa0", " ").replace("\r", " ").replace("\n", " ")
    return re.sub(r"\s+", " ", t).strip()

entries, cur = [], None
for p in soup.find_all("p"):
    text = clean(p.get_text())
    imgs = []
    for tag in p.find_all(["v:imagedata", "img"]):
        s = tag.get("src")
        title = tag.get("o:title")
        if s and s not in [i["src"] for i in imgs]:
            imgs.append({"src": s, "title": title})
    m = re.match(r"^(.+?) [–-] ?(.+)$", text)
    if m and len(m.group(1)) < 40 and not text.startswith("x ="):
        cur = {"name": m.group(1).strip(), "desc": m.group(2).strip(), "rle": "", "images": imgs}
        entries.append(cur)
        continue
    if cur is None:
        continue
    if text.startswith("x ="):
        cur["rle"] = text
    elif cur["rle"] and re.fullmatch(r"[0-9bo$!]+", text.replace(" ", "")):
        cur["rle"] += "\n" + text
    elif imgs:
        cur["images"] += [i for i in imgs if i not in cur["images"]]

# Normalise RLE: header on first line, body joined.
for e in entries:
    if e["rle"]:
        raw = e["rle"]
        m = re.match(r"(x\s*=\s*\d+,\s*y\s*=\s*\d+(?:,\s*rule\s*=\s*[A-Za-z0-9/]+)?)\s*(.*)", raw, re.S)
        e["rle"] = m.group(1) + "\n" + re.sub(r"\s+", "", m.group(2))
    m = re.search(r"Discovered by ([A-Z][a-z]+ [A-Z][a-z]+)", e["desc"])
    e["credit"] = m.group(1) if m else ("Jason Summers' Seeds collection" if "Jason Summers" in e["desc"] else "")

# Drop duplicate entries (the glossary repeats 'anchor stack').
seen, uniq = set(), []
for e in entries:
    if e["name"] in seen:
        continue
    seen.add(e["name"]); uniq.append(e)
json.dump(uniq, open(out, "w"), indent=1, ensure_ascii=False)
print(len(uniq), "entries;", sum(1 for e in uniq if e["rle"]), "with RLE")
for e in uniq:
    if not e["rle"]:
        print("  no RLE:", e["name"], [i["title"] for i in e["images"]])
