#!/usr/bin/env python3
"""
Enrich the restaurants in xhs_notes.json with real Google Places (New) data →
write data/restaurants.json (the source for tools/google_places.py).

One-time / periodic OFFLINE enrichment (mirrors the XHS offline-batch pattern):
the serving path reads the static restaurants.json — no live Google calls per request.

    python scripts/enrich_google.py            # enrich all
    python scripts/enrich_google.py --limit 3  # test on first 3

Join key: each restaurant is keyed by its xhs_notes.json name (the canonical name the
agent looks up), so Google data and XHS data line up by that exact name.

cuisine_type / name_zh: taken from the mock DB for the original 28 (accurate); for
expansion restaurants, name_zh is the leading CJK run of the key and cuisine_type is a
keyword heuristic. Refine in restaurants.json by hand if needed.
"""

import json
import re
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

_BACKEND = Path(__file__).parent.parent
sys.path.insert(0, str(_BACKEND))

from core.config import get_settings
from tools.google_places_mock import _MOCK_PLACES  # for accurate cuisine/name_zh of the 28

_KEY = get_settings().google_api_key
_NOTES = _BACKEND / "data" / "xhs_notes.json"
_OUT = _BACKEND / "data" / "restaurants.json"

# LA bounding box (from project_decisions) — keep results local.
_LA = {"rectangle": {"low": {"latitude": 33.70, "longitude": -118.67},
                     "high": {"latitude": 34.35, "longitude": -117.65}}}
_FIELDS = ("places.id,places.displayName,places.formattedAddress,places.location,"
           "places.rating,places.userRatingCount,places.priceLevel,places.googleMapsUri,"
           "places.internationalPhoneNumber,places.websiteUri,places.photos")

_PRICE = {"PRICE_LEVEL_FREE": "$", "PRICE_LEVEL_INEXPENSIVE": "$", "PRICE_LEVEL_MODERATE": "$$",
          "PRICE_LEVEL_EXPENSIVE": "$$$", "PRICE_LEVEL_VERY_EXPENSIVE": "$$$$"}

# cuisine heuristic for expansion restaurants (first match wins)
_CUISINE_RULES = [
    (("火锅", "hot pot", "shabu", "涮", "haidilao"), "火锅"),
    (("烤肉", "bbq", "baekjeong", "park's"), "韩式烤肉"),
    (("早茶", "dim sum", "海鲜", "seafood", "酒家", "ocean", "harbour", "harbor"), "粤式海鲜"),
    (("小笼", "xiao long", "din tai fung", "鼎泰丰", "南翔", "nanxiang"), "台式点心"),
    (("牛肉面", "noodle", "拉面", "刀削面", "米线", "面", "mian"), "面食"),
    (("川", "sichuan", "szechuan", "麻辣", "重庆", "chuan", "spicy"), "川菜"),
    (("东北", "饺子", "dumpling", "hui tou"), "东北菜"),
    (("台", "taiwan", "lukang", "302", "豆浆"), "台湾菜"),
    (("上海", "shanghai", "本帮", "王家沙", "正兴", "凌家", "ling"), "上海菜"),
    (("云南", "yunnan", "过桥"), "云南菜"),
    (("湘", "hunan", "辣妹子"), "湘菜"),
    (("西安", "陕", "xi'an", "xian", "shaanxi", "shanxi"), "西北菜"),
    (("港式", "茶餐厅", "phoenix inn", "broken mouth", "hi-top", "hk"), "港式茶餐厅"),
    (("甜品", "奶茶", "meet fresh", "鲜芋仙", "85", "bakery", "half and half", "饼"), "甜品饮品"),
    (("越南", "vietnam", "pho", "golden deli"), "越南菜"),
    (("日", "sushi", "ramen", "sugarfish", "izakaya", "tsujita"), "日本料理"),
    # non-Chinese LA favorites
    (("taco", "taqueria", "mariscos", "guisados", "sonoratown", "leo's", "el cholo",
      "oaxac", "guelaguetza", "birria", "mexican"), "墨西哥菜"),
    (("in-n-out", "burger", "father's office", "apple pan", "cassell", "smashburger"), "美式汉堡"),
    (("pizza", "pizzeria", "bestia", "bottega", "felix", "italian", "osteria", "funke"), "意大利菜"),
    (("deli", "langer", "canter", "pastrami", "wexler"), "犹太熟食"),
    (("roscoe", "chicken and waffle", "fried chicken"), "南方炸鸡"),
    (("thai", "night + market", "jitlada", "ruen pair", "pailin"), "泰国菜"),
    (("salt & straw", "ice cream", "gelato", "creamery"), "冰淇淋"),
    (("donut", "doughnut", "sidecar"), "甜甜圈"),
    (("philippe", "french dip", "pink's", "hot dog"), "美式经典"),
    (("republique", "sqirl", "gjelina", "brunch", "bottega louie"), "加州早午餐"),
    (("korean", "bbq", "baekjeong", "park's"), "韩式烤肉"),
]


# Permanently excluded: speculative/closed/no-LA-branch names whose Google match was wrong.
# enrich never re-adds these, so re-running after adding new restaurants stays clean.
DROP_SET = {
    "香天下 Shu Da Xia", "喜满年 Empress Harbor", "江南春 JJ Restaurant",
    "刘一手 Liu Yi Shou", "谭鸭血 Tan Ya Xue", "面 Mian Sichuan", "王家沙 Wang Jia Sha",
    "君华 King Hua", "Hi-Top Restaurant", "New Capital Seafood Restaurant", "Elite Restaurant",
    "鹿港小镇 Lukang", "春水堂 Chun Shui Tang",
    # 以下两家与其他条目重复同一个Google listing，保留更准确的那个
    "紫光园 Beijing Pie",        # 与"京味轩 Beijing Pie House"同一地址（Monterey Park）
    "老四川 Lao Sze Chuan",     # Google返回Sichuan Impression（与川味印象碰撞，且无独立Google条目）
}

# Expansion restaurants → city (the XHS ingestion stripped the city from the key;
# appending it back dramatically improves Google matching). The original 28 get
# their city from the mock DB address instead.
_AREA = {
    # American expansion restaurants (stripped city appended back for better Google match)
    "Gjelina": "Venice Los Angeles", "Felix Trattoria": "Venice Los Angeles",
    "Sidecar Doughnuts": "Santa Monica", "Father's Office": "Santa Monica",
    "Cassell's Hamburgers": "Koreatown Los Angeles", "Guelaguetza": "Koreatown Los Angeles",
    "Philippe the Original": "Chinatown Los Angeles", "Jitlada": "Thai Town Los Angeles",
    "Mariscos Jalisco": "Boyle Heights Los Angeles", "Langer's Deli": "Westlake Los Angeles",
    "Canter's Deli": "Fairfax Los Angeles", "Salt & Straw": "Larchmont Los Angeles",
    "Republique": "Mid-Wilshire Los Angeles", "Sqirl": "Silver Lake Los Angeles",
    "Bestia": "Downtown Los Angeles", "Bottega Louie": "Downtown Los Angeles",
    "Sonoratown": "Downtown Los Angeles", "Guisados": "Downtown Los Angeles",
    "Night + Market": "West Hollywood", "Pizzeria Mozza": "Hollywood Los Angeles",
    "Tsujita LA": "West Los Angeles", "The Apple Pan": "West Los Angeles",
    # original Chinese expansion restaurants
    "京味轩 Beijing Pie House": "San Gabriel", "老妈 Mama Lu's Dumpling House": "Monterey Park",
    "眉州东坡 Meizhou Dongpo": "Arcadia", "老四川 Lao Sze Chuan": "San Gabriel",
    "川味印象 Sichuan Impression": "Alhambra", "大호 Dai Ho Kitchen": "Temple City",
    "江南春 JJ Restaurant": "San Gabriel", "西安美食 Xi'an Tasty": "Rosemead",
    "多春 Luscious Dumplings": "San Gabriel", "锦江 Tasty Garden": "Alhambra",
    "鸿运海鲜 Capital Seafood": "Monterey Park", "沪上 Shanghai No 1 Seafood": "Rosemead",
    "鹿港小镇 Lukang": "San Gabriel", "Class 302 台式": "Rowland Heights",
    "春水堂 Chun Shui Tang": "Arcadia", "老张牛肉面 Lao Zhang": "Rowland Heights",
    "永和豆浆 Yung Ho Soy Milk": "San Gabriel", "沸腾 Boiling Point": "Monterey Park",
    "小肥羊 Little Sheep": "San Gabriel", "大龙燚 Da Long Yi": "San Gabriel",
    "香天下 Shu Da Xia": "Arcadia", "刘一手 Liu Yi Shou": "Rowland Heights",
    "谭鸭血 Tan Ya Xue": "San Gabriel", "面 Mian Sichuan": "Alhambra",
    "重庆小面 Chong Qing Noodles": "San Gabriel", "川王府 Chuan Wang Fu": "San Gabriel",
    "麻辣诱惑 Spicy City": "Alhambra", "东北人家 Northeast": "Rowland Heights",
    "老陕 Shaanxi Gourmet": "San Gabriel", "山西刀削面 Shanxi Noodle": "San Gabriel",
    "紫光园 Beijing Pie": "Monterey Park", "南翔小笼 Nanxiang": "San Gabriel",
    "王家沙 Wang Jia Sha": "Arcadia", "老正兴 Lao Zheng Xing": "San Gabriel",
    "辣妹子 La Mei Zi Hunan": "San Gabriel", "云海肴 Yunnan Garden": "Rowland Heights",
    "过桥缘 Crossing Bridge Noodle": "Irvine", "鲜芋仙 Meet Fresh": "Arcadia",
    "85度C 85C Bakery Cafe": "San Gabriel", "伴伴堂 Half and Half": "Alhambra",
    "海鲜世界 Ocean Star": "Monterey Park", "名都 NBC Seafood": "Monterey Park",
    "喜满年 Empress Harbor": "Monterey Park", "君华 King Hua": "Alhambra",
    "添好运 Tim Ho Wan": "Arcadia", "帝苑 Mission 261": "San Gabriel",
}


def _city(name: str, mock_place) -> str:
    if mock_place:
        m = re.search(r",\s*([^,]+),\s*CA", mock_place.address)
        if m:
            return m.group(1).strip()
    return _AREA.get(name, "Los Angeles")


def _cuisine_of(name: str) -> str:
    low = name.lower()
    for keys, label in _CUISINE_RULES:
        if any(k in low for k in keys):
            return label
    return "中餐"


def _name_zh(name: str):
    m = re.match(r"^[一-鿿·]+", name.strip())
    return m.group(0) if m else None


def _search(query: str) -> dict | None:
    body = json.dumps({"textQuery": query, "languageCode": "en",
                       "maxResultCount": 1, "locationRestriction": _LA}).encode()
    req = urllib.request.Request(
        "https://places.googleapis.com/v1/places:searchText", data=body, method="POST",
        headers={"Content-Type": "application/json", "X-Goog-Api-Key": _KEY,
                 "X-Goog-FieldMask": _FIELDS})
    for attempt in range(3):
        try:
            r = json.load(urllib.request.urlopen(req, timeout=25))
            return (r.get("places") or [None])[0]
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 503) and attempt < 2:
                time.sleep(2 * (attempt + 1)); continue
            print(f"  ❌ HTTP {e.code} for {query!r}: {e.read().decode()[:200]}")
            return None
        except Exception as e:
            print(f"  ❌ {query!r}: {e}"); return None
    return None


def main() -> None:
    limit = None
    if "--limit" in sys.argv:
        limit = int(sys.argv[sys.argv.index("--limit") + 1])

    refresh = "--refresh" in sys.argv
    mock = {p.name: p for p in _MOCK_PLACES}
    all_names = [n for n in json.loads(_NOTES.read_text(encoding="utf-8")).keys()
                 if n not in DROP_SET]

    # Incremental: keep existing restaurants.json, only fetch names not already in it.
    out: dict[str, dict] = {}
    if _OUT.exists() and not refresh:
        out = json.loads(_OUT.read_text(encoding="utf-8"))
    todo = [n for n in all_names if n not in out]
    if limit:
        todo = todo[:limit]
    print(f"已有 {len(out)} 家 | 待采 {len(todo)} 家 (新增) | DROP_SET {len(DROP_SET)} 家永久排除")

    flagged = []
    for i, name in enumerate(todo, 1):
        m = mock.get(name)
        query = f"{name} {_city(name, m)}"
        p = _search(query)
        time.sleep(0.15)  # be gentle
        if not p or p.get("rating") is None:
            flagged.append((name, "no result / no rating"))
            print(f"[{i}/{len(todo)}] ⚠️  {name}: 无结果或无评分")
            continue

        m = mock.get(name)
        rating = float(p["rating"])
        loc = p.get("location", {})
        google_name = p.get("displayName", {}).get("text", name)
        # low-confidence flag: returned name shares no token with our query
        q_tokens = {t.lower() for t in re.findall(r"[A-Za-z]+|[一-鿿]+", name)}
        n_tokens = {t.lower() for t in re.findall(r"[A-Za-z]+|[一-鿿]+", google_name)}
        if q_tokens and not (q_tokens & n_tokens):
            flagged.append((name, f"maybe wrong match → {google_name}"))

        out[name] = {
            "place_id": p.get("id"),
            "name": name,                                   # canonical = xhs join key
            "google_name": google_name,
            "name_zh": (m.name_zh if m else None) or _name_zh(name),
            "address": p.get("formattedAddress", ""),
            "lat": loc.get("latitude"), "lng": loc.get("longitude"),
            "google_rating": rating,
            "google_score": round(rating * 20, 1),
            "price_level": _PRICE.get(p.get("priceLevel"), (m.price_level.value if m else "$$")),
            "cuisine_type": (m.cuisine_type if m else _cuisine_of(name)),
            "total_ratings": p.get("userRatingCount", 0),
            "google_maps_url": p.get("googleMapsUri", ""),
            "photo_url": (m.photo_url if m else None),       # Google photos need key-in-URL; skip for now
            "phone": p.get("internationalPhoneNumber"),
            "website": p.get("websiteUri"),
        }
        print(f"[{i}/{len(todo)}] ✓ {name}  {rating}★({p.get('userRatingCount')})  {out[name]['cuisine_type']}")

    for n in DROP_SET:        # purge any excluded name that was added before
        out.pop(n, None)
    _OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n→ wrote {_OUT.name}: {len(out)} restaurants")
    if flagged:
        print(f"\n⚠️  {len(flagged)} 家需人工核对:")
        for n, why in flagged:
            print(f"    {n}  —  {why}")


if __name__ == "__main__":
    main()
