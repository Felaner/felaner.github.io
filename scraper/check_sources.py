"""Сверяет основную базу со второй вики в собранных data/*.json (фрагменты второй вики — div.src2).

Запуск после build.py:  python scraper/check_sources.py
Отчёт: scraper/source/conflicts.txt — рецепты, цена создания, дроп и отряд, где источники расходятся.
Что расходится — проверять в игре; основная база обычно свежее."""
import json, re, sys
from pathlib import Path
from collections import Counter

R = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent
SECS = ["equipment", "pets", "mobs", "items", "npc", "skills"]
ents = {e["id"]: e for s in SECS for e in json.loads((R / "data" / f"{s}.json").read_text("utf-8"))["entries"]}
names = {e["id"]: e["name"] for e in ents.values()}

def split(html):
    """(основная часть, вторая вики) одного блока."""
    parts = re.findall(r'<div class="src2">(.*?)</div>(?=<hr>|$)', html, re.S)
    main = re.sub(r'<div class="src2">.*?</div>(?=<hr>|$)', "", html, flags=re.S)
    return main, "".join(parts)

def gold(t):
    t = re.sub(r"<[^>]+>", " ", t)
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*k\b", t)
    if m: return round(float(m.group(1).replace(",", ".")) * 1000)
    m = re.search(r"за\s+(\d[\d\s]*\d|\d)\s*(?:зол|шт)", t)
    return int(re.sub(r"\s", "", m.group(1))) if m else None

def ingr_main(t):
    return {i: int(q) for q, i in re.findall(r'(\d+)\s*[xх×]\s*<img[^>]*data-items="([^"]+)"', t)}

def ingr_wb(t):
    out = {}
    for q, i in re.findall(r'(\d+)\s*[x×х]\s*<span data-items="([^"]+)"', t): out[i] = int(q)
    for q, n in re.findall(r'(\d+)\s*[x×х]\s*([^<\n]+?)\s*(?:</li>|<br|$)', re.sub(r'<span data-items="[^"]+">', "", t)):
        pass
    return out

rows = []
stat = Counter()
for e in ents.values():
    blocks = {b["title"]: b["html"] for b in e["blocks"]}
    # 1) Рецепты: «Рецепт» (основная) против «Изготовление»/«Рецепт» из второй вики.
    rec_main = "".join(split(blocks.get("Рецепт", ""))[0] for _ in [0])
    rec_wb = "".join(split(blocks.get(t, ""))[1] for t in ("Изготовление", "Рецепт", "Создание", "Крафт"))
    if rec_main and rec_wb:
        a, b = ingr_main(rec_main), ingr_wb(rec_wb)
        if a and b:
            stat["recipe pairs"] += 1
            if a != b:
                rows.append(("рецепт", e["id"], e["name"],
                             ", ".join(f"{q}×{names.get(i, i)}" for i, q in a.items()),
                             ", ".join(f"{q}×{names.get(i, i)}" for i, q in b.items())))
        ga, gb = gold(rec_main), gold(rec_wb)
        if ga and gb and ga != gb:
            if "Создание" in rec_main: rows.append(("цена создания", e["id"], e["name"], ga, gb))
    # 2) Дроп и отряд: какие записи есть только в одном источнике.
    for t in ("Дроп", "Команда"):
        if t not in blocks: continue
        m, w = split(blocks[t])
        # Сравниваем только конкретные предметы (item…), а не списки-категории вроде «Синергетики».
        real = lambda h: {i for i in re.findall(r'data-items="([^"]+)"', h) if i.startswith("item") or i.startswith("pet")}
        a, b = real(m), real(w)
        if a and b:
            stat[t + " pairs"] += 1
            if a != b:
                stat[t + " differ"] += 1
                rows.append((t.lower(), e["id"], e["name"],
                             "только осн.: " + ", ".join(names.get(i, i) for i in sorted(a - b)),
                             "только 2-я: " + ", ".join(names.get(i, i) for i in sorted(b - a))))
    # 3) Любые повторяющиеся блоки: доля второй вики есть, а основной нет — для статистики.
    for t, h in blocks.items():
        m, w = split(h)
        if w and re.sub(r"<[^>]+>|\s", "", m):
            stat["blocks with both"] += 1
            stat["both:" + t] += 1

# Тот же предмет под id статьи второй вики (wb_…) — не расхождение.
rows = [r for r in rows if not (r[0] == "рецепт" and "wb_" in r[4])]
c = Counter(r[0] for r in rows)
out = R / "scraper" / "source" / "conflicts.txt"
out.write_text("".join(" | ".join(map(str, r)) + "\n" for r in rows), "utf-8")
print(f"Пар для сверки: рецептов {stat['recipe pairs']}, дропа {stat['Дроп pairs']}; расхождений: {dict(c)} ({out.name})")
