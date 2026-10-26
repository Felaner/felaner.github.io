#!/usr/bin/env python3
"""Копия второй вики (MediaWiki) только через API, без браузера — для автообновления на сервере.

    python scraper/mirror_api.py [адрес] [--out папка]

Пишет то же, что mirror.py в режиме API (его читает wikibr.py):
    mediawiki/siteinfo.json, allpages.json, wikitext.jsonl.gz, files.json
    pages/<hash>.html.gz и pages.tsv (url, файл, статус, заголовок)
"""

import argparse
import gzip
import hashlib
import json
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import quote, urljoin, urlparse

UA = {"User-Agent": "Mozilla/5.0 (compatible; br-wiki-mirror)"}


def get(url, tries=3):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                return r.status, r.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return 404, None
        except Exception:
            pass
        time.sleep(2 * (i + 1))
    return 0, None


def h(s):
    return hashlib.sha1(s.encode()).hexdigest()[:16]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("start", nargs="?", default="https://www.wikibr.pl/")
    ap.add_argument("--out", help="папка копии (по умолчанию scraper/mirror/<host>)")
    ap.add_argument("--delay", type=float, default=0.2)
    args = ap.parse_args()
    host = urlparse(args.start).netloc.lower().removeprefix("www.")
    out = Path(args.out) if args.out else Path(__file__).resolve().parent / "mirror" / host
    (out / "pages").mkdir(parents=True, exist_ok=True)
    mw = out / "mediawiki"
    mw.mkdir(exist_ok=True)
    api = urljoin(args.start, "/api.php")

    _, info = get(api + "?action=query&meta=siteinfo&siprop=general|namespaces&format=json")
    if not info:
        raise SystemExit(f"API недоступно: {api}")
    (mw / "siteinfo.json").write_text(info, "utf-8")

    pages = []
    for ns in (0, 6, 14):
        cont = ""
        while True:
            _, txt = get(f"{api}?action=query&list=allpages&apnamespace={ns}&aplimit=500&format=json{cont}")
            if not txt:
                break
            d = json.loads(txt)
            pages += [dict(x, ns=ns) for x in d.get("query", {}).get("allpages", [])]
            c = d.get("continue", {}).get("apcontinue")
            if not c:
                break
            cont = "&apcontinue=" + quote(c)
    (mw / "allpages.json").write_text(json.dumps(pages, ensure_ascii=False, indent=1), "utf-8")
    articles = [x for x in pages if x["ns"] in (0, 14)]
    files = [x for x in pages if x["ns"] == 6]
    print(f"страниц: {len(pages)}, статей: {len(articles)}, файлов: {len(files)}")

    rows = []
    ids = [x["pageid"] for x in articles]
    for i in range(0, len(ids), 50):
        _, txt = get(f"{api}?action=query&prop=revisions|categories|pageimages&rvprop=content&rvslots=main"
                     f"&cllimit=max&piprop=original&format=json&pageids={'|'.join(map(str, ids[i:i + 50]))}")
        for pg in (json.loads(txt).get("query", {}).get("pages", {}).values() if txt else []):
            rev = (pg.get("revisions") or [{}])[0]
            rows.append({"pageid": pg.get("pageid"), "ns": pg.get("ns"), "title": pg.get("title"),
                         "categories": [c["title"] for c in pg.get("categories", [])],
                         "image": pg.get("original", {}).get("source"),
                         "wikitext": rev.get("slots", {}).get("main", {}).get("*", rev.get("*", ""))})
    (mw / "wikitext.jsonl.gz").write_bytes(gzip.compress("\n".join(json.dumps(r, ensure_ascii=False) for r in rows).encode()))
    print(f"wikitext: {len(rows)}")

    info_rows = []
    for i in range(0, len(files), 50):
        titles = "|".join(x["title"] for x in files[i:i + 50])
        _, txt = get(f"{api}?action=query&prop=imageinfo&iiprop=url|size|mime&format=json&titles={quote(titles)}")
        for pg in (json.loads(txt).get("query", {}).get("pages", {}).values() if txt else []):
            ii = (pg.get("imageinfo") or [{}])[0]
            info_rows.append({"title": pg.get("title"), "url": ii.get("url"), "size": ii.get("size"),
                              "width": ii.get("width"), "height": ii.get("height")})
    (mw / "files.json").write_text(json.dumps(info_rows, ensure_ascii=False, indent=1), "utf-8")

    origin = f"{urlparse(args.start).scheme}://{urlparse(args.start).netloc}"
    path_tpl = urlparse(json.loads(info)["query"]["general"].get("articlepath", "/wiki/$1")).path
    lines, failed = [], 0
    for n, a in enumerate(articles, 1):
        url = origin + path_tpl.replace("$1", quote(a["title"].replace(" ", "_")))
        status, html = get(url)
        if not html:
            failed += 1
            continue
        name = h(url)
        (out / "pages" / f"{name}.html.gz").write_bytes(gzip.compress(html.encode("utf-8")))
        lines.append(f"{url}\t{name}\t{status}\t{a['title']}")
        if n % 50 == 0:
            print(f"статьи: {n}/{len(articles)}")
        time.sleep(args.delay)
    (out / "pages.tsv").write_text("\n".join(lines) + "\n", "utf-8")
    print(f"статей сохранено: {len(lines)}, не скачалось: {failed}")


if __name__ == "__main__":
    main()
