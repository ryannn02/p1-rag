"""试采脚本：探测一个列表页，找出制度类条目，下载并写入登记表。

    python -m scripts.probe <列表页URL> --dept 教务处 --limit 5 --dry-run

两个站点结构不同，脚本都认：
- 教务处一类：列表页服务端渲染，条目是 c<栏目>a<文章>/page.htm 正文页，附件挂在正文里
- 信息公开一类：栏目本身就是一篇正文，列表为空
"""

import argparse
import csv
import hashlib
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

DOC_EXT = (".pdf", ".doc", ".docx")
PAGE_RE = re.compile(r"/c\d+a\d+/page\.htm$", re.I)
RULE_WORDS = ("办法", "规定", "细则", "规程", "制度", "手册", "条例", "实施意见", "汇编")
UA = "Mozilla/5.0 (compatible; SSpU-coursework-bot/0.1)"
DELAY = 1.5
META = Path("meta/documents.csv")
COLUMNS = Path("meta/columns.csv")
COLUMN_FIELDS = ["dept", "column_id", "title", "url", "rule_count", "checked_at"]
RAW = Path("data/raw")
FIELDS = META.read_text(encoding="utf-8").strip().split(",")


def get(session, url, binary=False):
    for attempt in range(3):
        try:
            r = session.get(url, timeout=20, allow_redirects=True)
            r.raise_for_status()
            if not binary:
                r.encoding = r.apparent_encoding or r.encoding
            return r
        except requests.RequestException as exc:
            if attempt == 2:
                print(f"  请求失败：{url} ({exc})", file=sys.stderr)
                return None
            time.sleep(2 * (attempt + 1))


def discover_columns(session, url, dept, count):
    """扫一个页面上的所有 /<数字>/list.htm 链接，即栏目入口。"""
    resp = get(session, url)
    if resp is None:
        return []
    host = urlparse(resp.url).netloc
    soup = BeautifulSoup(resp.text, "html.parser")
    rows = {}
    for a in soup.find_all("a", href=True):
        full = urljoin(resp.url, a["href"].strip())
        parts = urlparse(full)
        if parts.netloc != host:
            continue
        m = re.fullmatch(r"/([A-Za-z0-9_]+)/list\d*\.htm", parts.path)
        if not m:
            continue
        cid = m.group(1)
        rows.setdefault(cid, {
            "dept": dept, "column_id": cid,
            "title": a.get_text(strip=True) or f"栏目{cid}",
            "url": f"{parts.scheme}://{host}/{cid}/list.htm",
            "rule_count": "", "checked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        })

    weak = lambda s: bool(
        re.fullmatch(r"更多[+>»]*|栏目\d+|\d+|>|", (s or "").strip()) or len((s or "").strip()) < 2
    )
    for cid, row in rows.items():
        need_title = weak(row["title"])
        if not (count or need_title):
            continue
        time.sleep(DELAY)
        page = get(session, row["url"])
        if page is None:
            continue
        if need_title:
            soup2 = BeautifulSoup(page.text, "html.parser")
            node = soup2.select_one(".col_title h2") or soup2.select_one("h2")
            name = node.get_text(strip=True) if node else ""
            if not name:
                m = re.search(r"<title>(.*?)(?:[-_|]|</title>)", page.text, re.S | re.I)
                name = m.group(1).strip() if m else ""
            if name:
                row["title"] = name
        if count:
            found = find_candidates(page.text, page.url, include_pages=True)
            row["rule_count"] = sum(1 for c in found if any(w in c["title"] for w in RULE_WORDS))
            print(f"  栏目 {cid:<5} {row['title'][:18]:<20} 候选 {len(found):>3} 条，含制度关键词 {row['rule_count']:>3} 条")
    return list(rows.values())


def save_columns(rows):
    """栏目清单是可重算的快照，按 (dept, column_id) 覆盖更新，不追加历史。"""
    merged = {}
    if COLUMNS.exists():
        with COLUMNS.open(newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                merged[(r["dept"], r["column_id"])] = r
    for r in rows:
        merged[(r["dept"], r["column_id"])] = r
    with COLUMNS.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMN_FIELDS)
        w.writeheader()
        for key in sorted(merged):
            w.writerow(merged[key])


def find_candidates(html, base_url, include_pages):
    soup = BeautifulSoup(html, "html.parser")
    found, seen = [], set()
    for a in soup.find_all("a", href=True):
        url = urljoin(base_url, a["href"].strip())
        if urlparse(url).scheme not in ("http", "https"):
            continue
        path = unquote(urlparse(url).path)
        title = a.get_text(strip=True) or Path(path).stem
        if path.lower().endswith(DOC_EXT):
            kind = "file"
        elif include_pages and PAGE_RE.search(path):
            kind = "page"
        else:
            continue
        if url in seen:
            continue
        seen.add(url)
        found.append({"title": title, "url": url, "kind": kind,
                      "ext": path.rsplit(".", 1)[-1].lower() if kind == "file" else None})
    return found


def attachments(html, base_url):
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for a in soup.find_all("a", href=True):
        url = urljoin(base_url, a["href"].strip())
        path = unquote(urlparse(url).path)
        if path.lower().endswith(DOC_EXT):
            out.append({"title": a.get_text(strip=True) or Path(path).stem,
                        "url": url, "kind": "file", "ext": path.rsplit(".", 1)[-1].lower()})
    return out


def guess_year(*texts):
    """只认 WCM 的 /YYYY/MMDD/ 路径和标题里的年份。

    不要退化成「URL 里任意 20xx」——附件的 UUID 里就有这种数字，会解析出 2058 这种假年份。
    """
    for text in texts:
        text = text or ""
        m = (
            re.search(r"/(20\d{2})/\d{4}/", text)
            or re.search(r"(20\d{2})\s*年", text)
            or re.search(r"[（(](20\d{2})[)）]", text)
        )
        if m:
            return m.group(1)
    return "unknown"


def safe_name(dept, title, year, ext):
    title = re.sub(r'[\\/:*?"<>|\s]+', "_", title).strip("_")[:80] or "untitled"
    return f"{dept}_{title}_{year}.{ext}"


def sniff_pdf(path):
    try:
        import pypdf

        reader = pypdf.PdfReader(str(path))
        pages = len(reader.pages)
        text = "".join((reader.pages[i].extract_text() or "") for i in range(min(3, pages)))
        return len(text.strip()) < 50, pages
    except Exception as exc:
        print(f"  PDF 解析失败：{exc}", file=sys.stderr)
        return "", ""


def page_urls(url, pages):
    """WCM 分页规律：list.htm -> list2.htm -> list3.htm ..."""
    m = re.search(r"list\d*\.htm$", url)
    if not m or pages <= 1:
        return [url]
    base = url[: m.start()]
    return [url] + [f"{base}list{i}.htm" for i in range(2, pages + 1)]


def load_known():
    if not META.exists():
        return set()
    with META.open(newline="", encoding="utf-8") as f:
        return {row["source_url"] for row in csv.DictReader(f)}


def save(dept, title, url, page_url, ext, scanned, pages, local_path):
    with META.open("a", newline="", encoding="utf-8") as f:
        csv.DictWriter(f, fieldnames=FIELDS).writerow({
            "doc_id": hashlib.sha1(url.encode()).hexdigest()[:12],
            "dept": dept, "title": title, "doc_no": "",
            "year": guess_year(page_url, title), "publish_date": "",
            "source_url": url, "page_url": page_url or "", "format": ext,
            "is_scanned": "" if scanned == "" else str(scanned).lower(),
            "pages": pages, "status": "effective",
            "local_path": str(local_path),
            "fetched_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        })


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("url", help="列表页或栏目页地址")
    ap.add_argument("--dept", required=True)
    ap.add_argument("--limit", type=int, default=5)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--only-docs", action="store_true", help="只收 PDF/Word，跳过 page.htm 正文")
    ap.add_argument("--discover", action="store_true", help="扫描该页面上的栏目 ID，只写入 meta/columns.csv")
    ap.add_argument("--count", action="store_true", help="配合 --discover：逐个栏目统计制度条数（慢）")
    ap.add_argument("--pages", type=int, default=1, help="顺着 list2.htm 往后翻几页，默认 1")
    args = ap.parse_args()

    session = requests.Session()
    session.headers["User-Agent"] = UA

    if args.discover:
        rows = discover_columns(session, args.url, args.dept, args.count)
        print(f"\n发现 {len(rows)} 个栏目：")
        for r in rows:
            print(f"  {r['column_id']:<8} {r['title'][:24]:<26} {r['url']}")
        save_columns(rows)
        print(f"已写入 {COLUMNS}")
        return 0

    candidates, seen = [], set()
    for i, page_url in enumerate(page_urls(args.url, args.pages)):
        if i:
            time.sleep(DELAY)
        resp = get(session, page_url)
        if resp is None:
            continue
        found = find_candidates(resp.text, resp.url, not args.only_docs)
        print(f"  第 {i + 1} 页 {resp.url} -> {len(found)} 条")
        if not found and i:
            break
        for c in found:
            if c["url"] not in seen:
                seen.add(c["url"])
                candidates.append(c)
    resp = None
    print(f"候选 {len(candidates)} 条：")
    for c in candidates[:40]:
        print(f"  [{c['kind']}] {c['title'][:52]}")
    if args.dry_run or not candidates:
        return 0

    known = load_known()
    done = 0
    for c in candidates:
        if done >= args.limit:
            break
        if c["url"] in known:
            print(f"跳过（已登记）：{c['title'][:46]}")
            continue

        time.sleep(DELAY)
        if c["kind"] == "page":
            page = get(session, c["url"])
            if page is None:
                continue
            atts = attachments(page.text, page.url)
            if atts:
                print(f"  正文内发现 {len(atts)} 个附件，改取附件")
                att = atts[0]
                att["page_url"] = c["url"]
                if len(att["title"]) < 8:
                    att["title"] = c["title"]
                c = att
                time.sleep(DELAY)
            else:
                year = guess_year(c["url"], c["title"])
                target = RAW / args.dept / year / safe_name(args.dept, c["title"], year, "htm")
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(page.text, encoding="utf-8")
                save(args.dept, c["title"], c["url"], c["url"], "html", False, "", target)
                print(f"已保存正文页：{target}")
                done += 1
                continue

        data = get(session, c["url"], binary=True)
        if data is None:
            continue
        page_url = c.get("page_url", "")
        year = guess_year(page_url, c["title"])
        target = RAW / args.dept / year / safe_name(args.dept, c["title"], year, c["ext"])
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data.content)
        scanned, pages = sniff_pdf(target) if c["ext"] == "pdf" else ("", "")
        save(args.dept, c["title"], c["url"], page_url, c["ext"], scanned, pages, target)
        print(f"已保存：{target}  扫描件={scanned} 页数={pages}")
        done += 1

    print(f"本次处理 {done} 条，登记表累计 {len(load_known())} 行")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
