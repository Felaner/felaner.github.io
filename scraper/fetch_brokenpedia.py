#!/usr/bin/env python3
"""Скачивает открытые данные Brokenpedia (brokenpedia.com/api) в scraper/source/brokenpedia/.

    python scraper/fetch_brokenpedia.py

Легендарные предметы (базовые статы, вес, вместимость дрифов), сеты с бонусами, дрифы, орбы,
словарь игрового сленга. Названия польские — сопоставляются с основной базой по titlePL (build.py).
"""

import json
import urllib.request
from pathlib import Path

BASE = "https://brokenpedia.com/api/"
OUT = Path(__file__).resolve().parent / "source" / "brokenpedia"
ENDPOINTS = {
    "legendary": "items/legendary",
    "sets": "items/set",
    "epics_mods": "items/legendary/epics-mods",
    "drifs": "drifs",
    "orbs": "orbs",
    "dictionary": "dictionary",
}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for name, ep in ENDPOINTS.items():
        req = urllib.request.Request(BASE + ep, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
        data = json.loads(urllib.request.urlopen(req, timeout=60).read())
        (OUT / f"{name}.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), "utf-8")
        print(f"{name}: {len(data)}")


if __name__ == "__main__":
    main()
