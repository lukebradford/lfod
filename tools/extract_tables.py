"""Extract the tables from the original Word-exported pages into data/tables.json.

Usage: python3 tools/extract_tables.py   (requires beautifulsoup4)
"""
import json, re
from pathlib import Path
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "archive" / "verizon-site"

def clean(t):
    return re.sub(r"\s+", " ", t.replace("\xa0", " ")).strip()

def tables(page):
    soup = BeautifulSoup((SITE / page).read_text(encoding="windows-1252"), "html.parser")
    out = []
    for table in soup.find_all("table"):
        # Nearest preceding non-empty paragraph serves as the caption.
        caption = ""
        for prev in table.find_all_previous("p"):
            caption = clean(prev.get_text())
            if caption:
                break
        rows = []
        for tr in table.find_all("tr"):
            cells = [clean(td.get_text()) for td in tr.find_all(["td", "th"])]
            if any(cells):
                rows.append(cells)
        out.append({"caption": caption, "rows": rows})
    return out

data = {page: tables(page) for page in ["object tables.htm", "period.htm", "tables.htm"]}
(ROOT / "data" / "tables.json").write_text(json.dumps(data, indent=1, ensure_ascii=False))
for page, ts in data.items():
    print(page, [(t["caption"][:30], len(t["rows"])) for t in ts])
