#!/usr/bin/env python3
"""
Ingest a 八爪鱼 (Octoparse) XHS export → normalized backend/data/xhs_notes.json.

Pipeline:
  Windows 八爪鱼 desktop client (keyword search, 小号 QR login)
    → export CSV / Excel / JSON  → drop into backend/data/
    → run this script  → backend/data/xhs_notes.json
    → tools/xhs_bazhuayu.py serves it (reuses xhs_scorer)

Usage:
    python scripts/ingest_xhs_export.py data/your_export.csv
    python scripts/ingest_xhs_export.py data/your_export.json
    python scripts/ingest_xhs_export.py data/export1.csv data/export2.csv   # merge several

⚠️  BEFORE FIRST USE: fill in COLUMN_MAP below with the ACTUAL column headers
    from your export. Run the script once with --inspect to print the headers:
        python scripts/ingest_xhs_export.py data/your_export.csv --inspect
"""

import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

_BACKEND = Path(__file__).parent.parent
_OUT_FILE = _BACKEND / "data" / "xhs_notes.json"

# ─────────────────────────────────────────────────────────────────────────────
# TODO(fill after first export): map 八爪鱼 export column headers → our fields.
# The KEYS are whatever the template actually names its columns (Chinese is fine);
# the VALUES are our normalized field names and must stay as-is.
#
# Run with --inspect to see the real headers, then edit these:
COLUMN_MAP = {
    # export column name        → normalized field
    "搜索词": "restaurant",     # which keyword/restaurant this note belongs to
    "标题": "title",            # note title (2996 has no 正文/desc — search-list only)
    "点赞数": "likes",          # like count
    "帖子详情页链接": "url",     # kept for stage-2 enrichment (saves/comments/正文 via 2997)
    # NOTE: template 2996 (search list) does NOT export saves/comments/body.
    #   saves    → would be "收藏数"    (missing — needs detail-page template 2997)
    #   comments → would be "评论数"    (missing — needs 2997)
    #   desc     → would be "正文"/"内容" (missing — needs 2997)
    # xhs_bazhuayu.py defaults the missing fields to 0/'' so scoring still runs.
}

# Column whose value tells us which restaurant a note belongs to.
# (Must map to "restaurant" in COLUMN_MAP above.)
RESTAURANT_FIELD = "restaurant"

# If your keyword was "101 Noodle Express 洛杉矶", strip these location suffixes
# so the cache key is the clean restaurant name the agent will look up.
# NOTE: do not add "Costa Mesa"/"South Coast Plaza" here — the DTF South Coast entry
# uses its full English name as the keyword and must NOT collapse to "鼎泰丰".
LOCATION_SUFFIXES = ["洛杉矶", "阿凯迪亚", "阿罕布拉", "SGV", "Arcadia", "Alhambra",
                     "Rosemead", "Monterey Park", "蒙特利", "Temple City", "San Gabriel",
                     "Koreatown", "USC", "Little Tokyo", "Irvine", "尔湾",
                     "Rowland Heights", "罗兰岗", "Costa Mesa",
                     # wider LA areas (for non-SGV / American-local restaurants)
                     "Hollywood", "West Hollywood", "Venice", "Santa Monica", "Pasadena",
                     "Glendale", "Beverly Hills", "Silver Lake", "Echo Park", "Highland Park",
                     "Westwood", "Downtown", "DTLA", "Mid City", "Westlake", "Culver City",
                     "Thai Town", "Boyle Heights", "Chinatown", "Fairfax", "Larchmont",
                     "Los Angeles", "West LA", "LA", "CA"]

# After stripping location, map the (often Chinese) search term → the canonical
# English restaurant name the agent looks up (same keys as the mock Google DB).
# Covers all 28 mock restaurants. Extend as you add restaurants to the Google source.
RESTAURANT_ALIASES = {
    # SGV / Alhambra / Arcadia
    "101面馆": "101 Noodle Express",
    "皇朝茶餐厅": "Lunasia Dim Sum House", "皇朝": "Lunasia Dim Sum House",
    "成都味道": "Chengdu Taste",
    "鼎泰丰": "Din Tai Fung Arcadia",            # bare 鼎泰丰 → Arcadia branch
    "Golden Deli": "Golden Deli Vietnamese Restaurant",
    "海港海鲜": "Sea Harbour Seafood Restaurant", "海港": "Sea Harbour Seafood Restaurant",
    "满福楼": "Elite Restaurant",
    "那家小馆": "Bistro Na's",
    "海底捞": "Haidilao Hot Pot Arcadia",
    "新京都海鲜": "New Capital Seafood Restaurant", "新京都": "New Capital Seafood Restaurant",
    "大树饼屋": "Huge Tree Pastry",
    # DTLA / Chinatown / Little Tokyo
    "扬州餐厅": "Yang Chow Restaurant", "扬州": "Yang Chow Restaurant",
    "满堂红海鲜": "Full House Seafood Restaurant", "满堂红": "Full House Seafood Restaurant",
    # Koreatown
    "朴家烤肉": "Park's BBQ", "朴家": "Park's BBQ",
    "姜虎东烤肉": "Kang Ho-dong Baekjeong", "姜虎东": "Kang Ho-dong Baekjeong",
    # Rowland Heights
    "回头香": "Hui Tou Xiang",
    "益美": "Yi Mei Deli",
    "喜多港式茶餐厅": "Hi-Top Restaurant", "喜多": "Hi-Top Restaurant",
    # Irvine / Costa Mesa
    "好味牛肉面": "Tasty Noodle House",
    "凌家花园": "Ling's Garden", "凌家": "Ling's Garden",
    "新港海鲜": "Newport Seafood Restaurant",
    # English-name keywords (generic/ambiguous Chinese names) resolve by exact match,
    # so no alias entry is needed: Howlin' Ray's, Sushi Gen, Dave's Hot Chicken,
    # Broken Mouth, Earthen, Shabu Zone, Din Tai Fung South Coast Plaza.
    # Expansion American restaurants — "West LA" and "LA" both stripped from "Tsujita LA West LA"
    "Tsujita": "Tsujita LA",
}
# ─────────────────────────────────────────────────────────────────────────────


def _parse_count(v) -> int:
    """'1.2万'→12000, '3千'→3000, '500'→500, ''→0  (mirrors xhs_scorer.parse_count)."""
    from tools.xhs_scorer import parse_count
    return parse_count(str(v or "").strip())


def _clean_restaurant(raw: str) -> str:
    name = (raw or "").strip()
    for suffix in LOCATION_SUFFIXES:
        name = name.replace(suffix, "")
    name = " ".join(name.split())  # collapse whitespace
    return RESTAURANT_ALIASES.get(name, name)  # map to canonical English name if known


def _load_rows(path: Path) -> list[dict]:
    """Read CSV or JSON export into a list of row dicts."""
    if path.suffix.lower() == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        # 八爪鱼 JSON exports are usually a top-level list of row objects.
        if isinstance(data, dict):
            for key in ("data", "rows", "items", "result"):
                if isinstance(data.get(key), list):
                    return data[key]
            return [data]
        return data
    # CSV (also covers tab-delimited if needed)
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _inspect(paths: list[Path]) -> None:
    for path in paths:
        rows = _load_rows(path)
        print(f"\n=== {path.name}: {len(rows)} rows ===")
        if rows:
            print("Columns:", list(rows[0].keys()))
            print("First row:", json.dumps(rows[0], ensure_ascii=False, indent=2)[:800])


def ingest(paths: list[Path]) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    count_fields = {"likes", "saves", "comments"}

    for path in paths:
        for row in _load_rows(path):
            note: dict = {}
            restaurant = ""
            for col, field in COLUMN_MAP.items():
                val = row.get(col)
                if field == RESTAURANT_FIELD:
                    restaurant = _clean_restaurant(val)
                elif field in count_fields:
                    note[field] = _parse_count(val)
                else:
                    note[field] = (val or "").strip() if isinstance(val, str) else val
            if not restaurant:
                continue
            grouped[restaurant].append(note)

    return dict(grouped)


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = {a for a in sys.argv[1:] if a.startswith("--")}

    if not args:
        print(__doc__)
        sys.exit(1)

    # Allow running from anywhere; make tools.* importable.
    sys.path.insert(0, str(_BACKEND))

    paths = [Path(a) if Path(a).is_absolute() else _BACKEND / a for a in args]
    missing = [p for p in paths if not p.exists()]
    if missing:
        print("File(s) not found:", *[str(p) for p in missing], sep="\n  ")
        sys.exit(1)

    if "--inspect" in flags:
        _inspect(paths)
        return

    notes = ingest(paths)
    _OUT_FILE.write_text(
        json.dumps(notes, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    total = sum(len(v) for v in notes.values())
    print(f"✓ Wrote {_OUT_FILE.relative_to(_BACKEND)}")
    print(f"  {len(notes)} restaurants, {total} notes")
    for name, ns in sorted(notes.items(), key=lambda kv: -len(kv[1]))[:10]:
        print(f"    {len(ns):4d}  {name}")


if __name__ == "__main__":
    main()
