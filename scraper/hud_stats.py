#!/usr/bin/env python3
"""Личная статистика боёв и дропа из Broken HUD -> local/statistika.html (только на этом компьютере).

    python scraper/hud_stats.py [путь к data.db]

Читает копию базы Broken HUD (оригинал не трогает), названия предметов переводит через основную базу
по польскому имени. Папка local/ в .gitignore — в публичный репозиторий страница не попадает.
"""

import html as H
import json
import shutil
import sqlite3
import sys
import tempfile
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HUD_DB = Path.home() / "AppData" / "Local" / "Programs" / "BrokenHud" / "data.db"
OUT = ROOT / "local" / "statistika.html"


def ru_names():
    """Польское имя -> (русское имя, id записи вики) по собранным данным."""
    names = {}
    for sid in ("items", "equipment", "pets"):
        f = ROOT / "data" / f"{sid}.json"
        if f.exists():
            for e in json.loads(f.read_text("utf-8"))["entries"]:
                if e.get("namePL"):
                    names.setdefault(e["namePL"].strip().lower(), (e["name"], e["id"], sid, e.get("category", "_")))
    return names


def fmt(n):
    return f"{round(n):,}".replace(",", " ")


def main():
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else HUD_DB
    if not src.exists():
        sys.exit(f"Нет базы Broken HUD: {src}")
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "hud.db"
        shutil.copy(src, db_path)  # HUD может держать файл открытым — работаем с копией
        con = sqlite3.connect(db_path)
        fights = con.execute("select Id, Time, PlayerName, Exp, Gold, Psycho, OpponentNames, BossFight from Fights").fetchall()
        items = dict(con.execute("select Code, Name from Items"))
        drops = con.execute("select FightId, Code, Quantity from FightItems").fetchall()
        con.close()

    names = ru_names()
    by_day = defaultdict(lambda: {"fights": 0, "exp": 0, "gold": 0, "psycho": 0, "first": None, "last": None})
    opponents = Counter()
    for fid, t, player, exp, gold, psycho, opp, boss in fights:
        ts = datetime.fromisoformat(t[:26])
        d = by_day[ts.date().isoformat()]
        d["fights"] += 1
        d["exp"] += exp or 0
        d["gold"] += gold or 0
        d["psycho"] += psycho or 0
        d["first"] = min(d["first"] or ts, ts)
        d["last"] = max(d["last"] or ts, ts)
        for o in (opp or "").split(","):
            if o.strip():
                opponents[o.strip()] += 1
    loot = Counter()
    for _, code, qty in drops:
        loot[code] += qty or 1

    def item_cell(code):
        pl = items.get(code, f"#{code}")
        ru = names.get(pl.strip().lower())
        if ru:
            name, eid, sid, cat = ru
            return f'<a href="../index.html#/s/{sid}/{cat}?e={H.escape(eid)}">{H.escape(name)}</a>'
        return H.escape(pl)

    rows_day = ""
    for day, d in sorted(by_day.items(), reverse=True):
        hours = max((d["last"] - d["first"]).total_seconds() / 3600, 1 / 60)
        rows_day += (f"<tr><td>{day}</td><td>{d['fights']}</td><td>{fmt(d['exp'])}</td><td>{fmt(d['gold'])}</td>"
                     f"<td>{fmt(d['exp'] / hours)}</td><td>{fmt(d['gold'] / hours)}</td></tr>")
    rows_loot = "".join(f"<tr><td>{item_cell(c)}</td><td>{q}</td></tr>" for c, q in loot.most_common())
    rows_opp = "".join(f"<tr><td>{H.escape(o)}</td><td>{n}</td></tr>" for o, n in opponents.most_common(30))
    total_exp = sum(f[3] or 0 for f in fights)
    total_gold = sum(f[4] or 0 for f in fights)
    page = f"""<!doctype html><html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Моя статистика — Broken Ranks</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Alegreya:wght@500;700&family=Alegreya+Sans:wght@400;500;700&display=swap">
<link rel="stylesheet" href="../assets/style.css"></head>
<body class="static"><main class="static-page">
<h1>Моя статистика</h1>
<p class="muted">Из Broken HUD: боёв {len(fights)}, опыт {fmt(total_exp)}, золото {fmt(total_gold)}.
Обновлено {datetime.now():%d.%m.%Y %H:%M}. Страница только на этом компьютере.</p>
<section class="block"><h2>По дням</h2><div class="tscroll"><table class="art">
<tr><th>День</th><th>Боёв</th><th>Опыт</th><th>Золото</th><th>Опыт в час</th><th>Золото в час</th></tr>{rows_day}</table></div>
<p class="muted small">«В час» — от первого до последнего боя дня.</p></section>
<section class="block"><h2>Дроп</h2><div class="tscroll"><table class="art"><tr><th>Предмет</th><th>Штук</th></tr>
{rows_loot or '<tr><td colspan="2">Пока пусто</td></tr>'}</table></div></section>
<section class="block"><h2>Противники</h2><div class="tscroll"><table class="art"><tr><th>Противник</th><th>Боёв</th></tr>
{rows_opp or '<tr><td colspan="2">Пока пусто</td></tr>'}</table></div></section>
</main></body></html>"""
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(page, "utf-8")
    print(f"Боёв: {len(fights)}, предметов в дропе: {sum(loot.values())} -> {OUT}")


if __name__ == "__main__":
    main()
