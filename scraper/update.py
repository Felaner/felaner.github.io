#!/usr/bin/env python3
"""Полное обновление данных из всех источников — вручную или по расписанию (.github/workflows/update.yml).

    python scraper/update.py

1. База anteiku (JSON), Brokenpedia (API), вторая вики (mirror_api.py — без браузера).
2. build.py, докачка недостающих картинок (крупные PNG ужимаются, если есть Pillow), повторная сборка.
3. check_sources.py и отчёт scraper/source/update_report.md: версии, новые/изменённые/удалённые записи,
   непереведённое, расхождения источников, новые записи в официальных новостях (патчноуты).
"""

import hashlib
import json
import re
import shutil
import subprocess
import sys
import urllib.request
from datetime import date
from pathlib import Path
from urllib.parse import unquote

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SRC = HERE / "source"
DATA = ROOT / "data"
ANTEIKU = "https://anteikutaern.at.ua"
WIKI = "https://www.wikibr.pl"
NEWS = "https://brokenranks.com/en/news/"
UA = {"User-Agent": "Mozilla/5.0 (compatible; br-wiki-update)"}
SECTIONS = ["equipment", "pets", "mobs", "items", "npc", "skills", "guild", "quests", "guides"]


def fetch(url, timeout=60):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
        return r.read()


def run(*cmd):
    print("$", " ".join(cmd), flush=True)
    subprocess.run([sys.executable, "-X", "utf8", *cmd], cwd=ROOT, check=True)


def snapshot():
    """id -> хеш содержимого записи по разделам (чтобы найти изменения после сборки)."""
    snap = {}
    for sid in SECTIONS:
        f = DATA / f"{sid}.json"
        if f.exists():
            for e in json.loads(f.read_text("utf-8"))["entries"]:
                snap[(sid, e["id"])] = (e["name"], hashlib.sha1(json.dumps(
                    [e.get("fields"), e.get("blocks")], ensure_ascii=False, sort_keys=True).encode()).hexdigest())
    return snap


def download_images():
    """Докачивает картинки из needed_images.txt (anteiku) и needed_wikibr.txt (вторая вики). Возвращает число новых."""
    got = 0
    for listing, base, prefix in (("needed_images.txt", ANTEIKU, DATA), ("needed_wikibr.txt", WIKI, DATA / "wiki")):
        f = SRC / listing
        if not f.exists():
            continue
        for path in [x.strip() for x in f.read_text("utf-8").splitlines() if x.strip()]:
            dst = prefix / unquote(path).lstrip("/")
            if dst.exists():
                continue
            try:
                body = fetch(base + path, timeout=30)
            except Exception:
                continue
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(body)
            got += 1
            shrink(dst)
    return got


def shrink(f):
    """Крупный PNG: сторона ≤ 2000 px, палитра 256 цветов (без Pillow — пропуск)."""
    if f.suffix.lower() != ".png" or f.stat().st_size < 150_000:
        return
    try:
        from PIL import Image
    except ImportError:
        return
    im = Image.open(f)
    im.load()
    if max(im.size) > 2000:
        k = 2000 / max(im.size)
        im = im.resize((round(im.width * k), round(im.height * k)), Image.LANCZOS)
    if im.mode not in ("RGB", "RGBA"):
        im = im.convert("RGBA")
    q = im.quantize(256, method=Image.Quantize.FASTOCTREE if im.mode == "RGBA" else Image.Quantize.MEDIANCUT)
    tmp = f.with_suffix(".tmp.png")
    q.save(tmp, optimize=True)
    if tmp.stat().st_size < f.stat().st_size * 0.8:
        tmp.replace(f)
    else:
        tmp.unlink()


def news_titles():
    """Свежие заголовки официальных новостей (патчноуты). Сайт иногда недоступен — тогда пусто."""
    try:
        html = fetch(NEWS, timeout=30).decode("utf-8", "replace")
    except Exception as e:
        print(f"новости недоступны: {e}")
        return []
    items = re.findall(r'href="(https://brokenranks\.com/en/news/[^"#?]+)"[^>]*>\s*(?:<[^>]+>\s*)*([^<]{4,140})', html)
    seen, out = set(), []
    for url, title in items:
        title = re.sub(r"\s+", " ", title).strip()
        if url not in seen and not url.rstrip("/").endswith("/news"):
            seen.add(url)
            out.append((title, url))
    return out[:15]


def main():
    old_version = json.loads((SRC / "anteikuDBversion.json").read_text("utf-8")) if (SRC / "anteikuDBversion.json").exists() else {}
    before = snapshot()

    for name in ("anteikuDB.json", "all_map_elements.json", "anteikuDBversion.json"):
        (SRC / name).write_bytes(fetch(f"{ANTEIKU}/raresImg/{name}"))
    new_version = json.loads((SRC / "anteikuDBversion.json").read_text("utf-8"))
    run("scraper/fetch_brokenpedia.py")

    mirror = HERE / "mirror" / "wikibr.pl"
    fresh = HERE / "mirror" / "wikibr.pl.new"
    shutil.rmtree(fresh, ignore_errors=True)
    run("scraper/mirror_api.py", "--out", str(fresh))
    shutil.rmtree(mirror, ignore_errors=True)
    fresh.rename(mirror)

    run("scraper/build.py")
    if download_images():
        run("scraper/build.py")
    run("scraper/check_sources.py")

    after = snapshot()
    added = [after[k][0] + f" ({k[0]})" for k in after.keys() - before.keys()]
    removed = [before[k][0] + f" ({k[0]})" for k in before.keys() - after.keys()]
    changed = [after[k][0] + f" ({k[0]})" for k in after.keys() & before.keys() if after[k][1] != before[k][1]]
    todo = json.loads((SRC / "translate_todo.json").read_text("utf-8")) if (SRC / "translate_todo.json").exists() else []
    conflicts = (SRC / "conflicts.txt").read_text("utf-8").count("\n") if (SRC / "conflicts.txt").exists() else 0
    stats = (SRC / "conflicts_stats.txt").read_text("utf-8").count("\n") if (SRC / "conflicts_stats.txt").exists() else 0

    seen_file = SRC / "news_seen.json"
    seen = set(json.loads(seen_file.read_text("utf-8"))) if seen_file.exists() else set()
    news = news_titles()
    fresh_news = [(t, u) for t, u in news if u not in seen]
    if news:
        seen_file.write_text(json.dumps(sorted(seen | {u for _, u in news}), ensure_ascii=False, indent=1), "utf-8")

    lines = [f"# Обновление данных {date.today():%d.%m.%Y}", "",
             f"- База anteiku: {old_version.get('version', '?')} → {new_version.get('version', '?')}",
             f"- Новых записей: {len(added)}, изменённых: {len(changed)}, удалённых: {len(removed)}",
             f"- Непереведённых фрагментов второй вики: {len(todo)} (`scraper/source/translate_todo.json`)",
             f"- Расхождений источников: дроп/рецепты {conflicts}, статы {stats}", ""]
    for title, items in (("Новые записи", added), ("Изменённые записи", changed), ("Удалённые записи", removed)):
        if items:
            lines += [f"## {title}", ""] + [f"- {x}" for x in sorted(items)[:200]] + [""]
    if fresh_news:
        lines += ["## Новое в официальных новостях", "",
                  "Проверьте патчноуты: то, чего ещё нет в базах, — в `scraper/source/patch_overrides.json`.", ""]
        lines += [f"- [{t}]({u})" for t, u in fresh_news] + [""]
    (SRC / "update_report.md").write_text("\n".join(lines), "utf-8")
    print("\n".join(lines[:8]))


if __name__ == "__main__":
    main()
