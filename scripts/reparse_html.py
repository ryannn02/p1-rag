"""把已入库但正文为空的 HTML 条目重新解析：抓取内嵌 PDF/Word 附件并升级该行。

信息公开站很多条目的正文是 pdfsrc 播放器内嵌的 PDF，采集时只看 <a> 会漏掉，
于是存成空壳 HTML。这个脚本把这些条目升级成真正的文件。
"""

import csv
import sys
from pathlib import Path

sys.path.insert(0, ".")
from scripts.probe import (FIELDS, META, RAW, UA, attachments, get,  # noqa: E402
                           guess_year, is_rule, safe_name, sniff_pdf)

import requests  # noqa: E402

MIN_TEXT = 200


def body_len(path):
    from bs4 import BeautifulSoup

    if not Path(path).exists():
        return 0
    soup = BeautifulSoup(Path(path).read_text(encoding="utf-8", errors="ignore"), "html.parser")
    return max([len(d.get_text(strip=True)) for d in soup.find_all("div")] or [0])


def main():
    session = requests.Session()
    session.headers["User-Agent"] = UA
    rows = list(csv.DictReader(META.open(encoding="utf-8")))
    todo = [r for r in rows if r["format"] == "html" and body_len(r["local_path"]) < MIN_TEXT]
    print(f"正文为空的 HTML 条目 {len(todo)} 条，开始重新解析")

    fixed = failed = 0
    for r in todo:
        page = get(session, r["page_url"] or r["source_url"])
        if page is None:
            failed += 1
            continue
        atts = attachments(page.text, page.url)
        if not atts:
            print(f"  仍无附件，保持原样：{r['title'][:36]}")
            failed += 1
            continue
        att = atts[0]
        data = get(session, att["url"], binary=True)
        if data is None:
            failed += 1
            continue
        if not is_rule(att["title"]) and is_rule(r["title"]):
            att["title"] = r["title"]
        year = guess_year(r["page_url"], att["title"]) 
        target = RAW / r["dept"] / year / safe_name(r["dept"], att["title"], year, att["ext"])
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data.content)
        scanned, pages = sniff_pdf(target) if att["ext"] == "pdf" else ("", "")

        r.update({"source_url": att["url"], "format": att["ext"], "year": year,
                  "is_scanned": "" if scanned == "" else str(scanned).lower(),
                  "pages": pages, "local_path": str(target)})
        print(f"  升级为 {att['ext']}：{target.name[:60]}")
        fixed += 1

    with META.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    print(f"\n升级 {fixed} 条，未升级 {failed} 条")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
