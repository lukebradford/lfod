"""Extract the dated entries of the 2009 News page into data/news.json."""
import json, re, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from lfod import superscript  # noqa: E402

# Exponents (96*2<sup>n</sup>) would lose their superscript in plain text.
src = (ROOT / "archive/verizon-site/news.htm").read_text(encoding="windows-1252")
src = re.sub(r"<sup[^>]*>(.*?)</sup>", lambda m: superscript(re.sub(r"<[^>]*>", "", m.group(1))), src, flags=re.S | re.I)
src = re.sub(r"charset=windows-1252", "charset=utf-8", src, flags=re.I)
text = subprocess.run(["textutil", "-convert", "txt", "-format", "html", "-inputencoding", "UTF-8", "-stdin", "-stdout"],
                      input=src.encode("utf-8"), capture_output=True).stdout.decode("utf-8")
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
