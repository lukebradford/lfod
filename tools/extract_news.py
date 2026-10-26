"""Extract the dated entries of the 2009 News page into data/news.json."""
import json, re, subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
text = subprocess.run(["textutil", "-convert", "txt", "-stdout", str(ROOT / "archive/verizon-site/news.htm")],
                      capture_output=True, text=True).stdout
items, cur = [], None
for line in (l.strip() for l in text.splitlines()):
    if not line or line.startswith("Live Free or Die"):
        continue
    m = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{2})", line)
    if m:
        mo, d, y = map(int, m.groups())
        cur = {"date": f"20{y:02d}-{mo:02d}-{d:02d}", "paras": []}
        items.append(cur)
    elif cur and not re.fullmatch(r"(x = .*|[0-9bo$!]+)", line):
        cur["paras"].append(line)
(ROOT / "data/news.json").write_text(json.dumps(items, indent=1, ensure_ascii=False))
print(len(items), "news items", items[-1]["date"], "to", items[0]["date"])
