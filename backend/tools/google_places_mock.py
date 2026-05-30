"""
GooglePlacesTool — Mock implementation.

Interface contract (swap this file for real Google Places API later):
  search_restaurants(query, location, budget, cuisine) -> list[PlaceResult]
  get_place_detail(place_id: str) -> PlaceResult | None
"""

import asyncio
from dataclasses import dataclass, field
from typing import Optional
from schemas.models import PriceLevel


@dataclass
class PlaceResult:
    place_id: str
    name: str
    name_zh: Optional[str]
    address: str
    lat: float
    lng: float
    google_rating: float     # 1.0 - 5.0
    google_score: float      # normalized to 0-100
    price_level: PriceLevel
    cuisine_type: str
    total_ratings: int
    google_maps_url: str
    photo_url: Optional[str] = None
    is_open_now: bool = True
    phone: Optional[str] = None
    website: Optional[str] = None
    keywords: list[str] = field(default_factory=list)


# ── Mock DB ───────────────────────────────────────────────────────────────────
# Covers SGV, DTLA/Chinatown, Koreatown/USC, Rowland Heights, Irvine.
# keywords list includes area tags so location queries ("DTLA", "尔湾", etc.) resolve correctly.

_MOCK_PLACES: list[PlaceResult] = [

    # ── SGV / Alhambra ────────────────────────────────────────────────────────
    PlaceResult(
        place_id="mock_101_noodle",
        name="101 Noodle Express",
        name_zh="101面馆",
        address="1408 E Valley Blvd, Alhambra, CA 91801",
        lat=34.0953, lng=-118.1347,
        google_rating=4.4, google_score=88.0,
        price_level=PriceLevel.budget,
        cuisine_type="北方面食",
        total_ratings=2847,
        google_maps_url="https://maps.google.com/?q=101+Noodle+Express+Alhambra",
        photo_url="https://images.unsplash.com/photo-1569050467447-ce54b3bbc37d?w=600&h=300&fit=crop&auto=format",
        keywords=["noodles", "beef roll", "northern chinese", "sgv", "alhambra", "华人区"],
    ),
    PlaceResult(
        place_id="mock_lunasia",
        name="Lunasia Dim Sum House",
        name_zh="皇朝茶餐厅",
        address="500 W Main St, Alhambra, CA 91801",
        lat=34.0941, lng=-118.1356,
        google_rating=4.3, google_score=86.0,
        price_level=PriceLevel.moderate,
        cuisine_type="粤式早茶",
        total_ratings=4123,
        google_maps_url="https://maps.google.com/?q=Lunasia+Dim+Sum+Alhambra",
        photo_url="https://images.unsplash.com/photo-1563245372-f21724e3856d?w=600&h=300&fit=crop&auto=format",
        keywords=["dim sum", "cantonese", "har gow", "siu mai", "sgv", "alhambra", "华人区"],
    ),
    PlaceResult(
        place_id="mock_chengdu_taste",
        name="Chengdu Taste",
        name_zh="成都味道",
        address="828 W Valley Blvd #118, Alhambra, CA 91803",
        lat=34.0889, lng=-118.1521,
        google_rating=3.6, google_score=72.0,
        price_level=PriceLevel.moderate,
        cuisine_type="川菜",
        total_ratings=891,
        google_maps_url="https://maps.google.com/?q=Chengdu+Taste+Alhambra",
        photo_url="https://images.unsplash.com/photo-1581299894007-aaa50297cf16?w=600&h=300&fit=crop&auto=format",
        keywords=["sichuan", "spicy", "mala", "dan dan noodles", "sgv", "alhambra", "华人区"],
    ),
    PlaceResult(
        place_id="mock_dtf_arcadia",
        name="Din Tai Fung Arcadia",
        name_zh="鼎泰丰（阿凯迪亚店）",
        address="400 S Baldwin Ave, Arcadia, CA 91007",
        lat=34.1302, lng=-118.0385,
        google_rating=4.5, google_score=90.0,
        price_level=PriceLevel.expensive,
        cuisine_type="台式点心",
        total_ratings=8934,
        google_maps_url="https://maps.google.com/?q=Din+Tai+Fung+Arcadia",
        photo_url="https://images.unsplash.com/photo-1548943487-a2e4e43b4853?w=600&h=300&fit=crop&auto=format",
        keywords=["xiao long bao", "soup dumplings", "taiwanese", "sgv", "arcadia", "华人区"],
    ),
    PlaceResult(
        place_id="mock_golden_deli",
        name="Golden Deli Vietnamese Restaurant",
        name_zh=None,
        address="815 W Las Tunas Dr, San Gabriel, CA 91776",
        lat=34.0952, lng=-118.1058,
        google_rating=3.8, google_score=74.0,
        price_level=PriceLevel.budget,
        cuisine_type="越南菜",
        total_ratings=1205,
        google_maps_url="https://maps.google.com/?q=Golden+Deli+San+Gabriel",
        photo_url="https://images.unsplash.com/photo-1511910849309-0dffb8785146?w=600&h=300&fit=crop&auto=format",
        keywords=["pho", "spring rolls", "vietnamese", "sgv", "san gabriel", "华人区"],
    ),

    # ── SGV / Rosemead / Monterey Park / Temple City ──────────────────────────
    PlaceResult(
        place_id="mock_sea_harbour",
        name="Sea Harbour Seafood Restaurant",
        name_zh="海港海鲜酒家",
        address="3939 Rosemead Blvd, Rosemead, CA 91770",
        lat=34.0730, lng=-118.0789,
        google_rating=4.6, google_score=92.0,
        price_level=PriceLevel.moderate,
        cuisine_type="粤式早茶",
        total_ratings=6842,
        google_maps_url="https://maps.google.com/?q=Sea+Harbour+Seafood+Rosemead",
        photo_url="https://images.unsplash.com/photo-1563245372-f21724e3856d?w=600&h=300&fit=crop&auto=format",
        keywords=["dim sum", "cantonese", "seafood", "sgv", "rosemead", "华人区", "早茶"],
    ),
    PlaceResult(
        place_id="mock_elite",
        name="Elite Restaurant",
        name_zh="满福楼",
        address="700 S Atlantic Blvd, Monterey Park, CA 91754",
        lat=34.0421, lng=-118.1494,
        google_rating=4.3, google_score=86.0,
        price_level=PriceLevel.moderate,
        cuisine_type="粤式早茶",
        total_ratings=3917,
        google_maps_url="https://maps.google.com/?q=Elite+Restaurant+Monterey+Park",
        photo_url="https://images.unsplash.com/photo-1563245372-f21724e3856d?w=600&h=300&fit=crop&auto=format",
        keywords=["dim sum", "cantonese", "sgv", "monterey park", "华人区", "早茶"],
    ),
    PlaceResult(
        place_id="mock_bistro_nas",
        name="Bistro Na's",
        name_zh="那家小馆",
        address="9055 Las Tunas Dr, Temple City, CA 91780",
        lat=34.1023, lng=-118.0550,
        google_rating=4.0, google_score=80.0,
        price_level=PriceLevel.moderate,
        cuisine_type="北京菜",
        total_ratings=1532,
        google_maps_url="https://maps.google.com/?q=Bistro+Nas+Temple+City",
        photo_url="https://images.unsplash.com/photo-1555126634-323283e090fa?w=600&h=300&fit=crop&auto=format",
        keywords=["beijing", "northern chinese", "peking duck", "sgv", "temple city", "华人区"],
    ),
    PlaceResult(
        place_id="mock_haidilao_arcadia",
        name="Haidilao Hot Pot Arcadia",
        name_zh="海底捞（阿凯迪亚）",
        address="400 S Baldwin Ave #2850, Arcadia, CA 91007",
        lat=34.1298, lng=-118.0388,
        google_rating=4.4, google_score=88.0,
        price_level=PriceLevel.expensive,
        cuisine_type="火锅",
        total_ratings=4201,
        google_maps_url="https://maps.google.com/?q=Haidilao+Arcadia",
        photo_url="https://images.unsplash.com/photo-1585032226651-759b368d7246?w=600&h=300&fit=crop&auto=format",
        keywords=["hotpot", "hot pot", "sichuan", "sgv", "arcadia", "华人区", "火锅"],
    ),
    PlaceResult(
        place_id="mock_new_capital",
        name="New Capital Seafood Restaurant",
        name_zh="新京都海鲜酒家",
        address="755 W Las Tunas Dr, San Gabriel, CA 91776",
        lat=34.1002, lng=-118.1066,
        google_rating=3.6, google_score=72.0,
        price_level=PriceLevel.moderate,
        cuisine_type="粤式海鲜",
        total_ratings=987,
        google_maps_url="https://maps.google.com/?q=New+Capital+Seafood+San+Gabriel",
        photo_url="https://images.unsplash.com/photo-1559847844-5315695dadae?w=600&h=300&fit=crop&auto=format",
        keywords=["seafood", "cantonese", "dim sum", "sgv", "san gabriel", "华人区"],
    ),
    PlaceResult(
        place_id="mock_huge_tree",
        name="Huge Tree Pastry",
        name_zh="大树饼屋",
        address="423 N Atlantic Blvd, Monterey Park, CA 91754",
        lat=34.0648, lng=-118.1330,
        google_rating=4.2, google_score=84.0,
        price_level=PriceLevel.budget,
        cuisine_type="台湾早餐",
        total_ratings=2103,
        google_maps_url="https://maps.google.com/?q=Huge+Tree+Pastry+Monterey+Park",
        photo_url="https://images.unsplash.com/photo-1551782450-a2132b4ba21d?w=600&h=300&fit=crop&auto=format",
        keywords=["taiwanese", "breakfast", "pastry", "congee", "sgv", "monterey park", "华人区", "早餐"],
    ),

    # ── DTLA / Chinatown / Little Tokyo ───────────────────────────────────────
    PlaceResult(
        place_id="mock_yang_chow",
        name="Yang Chow Restaurant",
        name_zh="扬州餐厅",
        address="819 N Broadway, Los Angeles, CA 90012",
        lat=34.0621, lng=-118.2395,
        google_rating=3.9, google_score=78.0,
        price_level=PriceLevel.moderate,
        cuisine_type="中式美式",
        total_ratings=3241,
        google_maps_url="https://maps.google.com/?q=Yang+Chow+Restaurant+Los+Angeles",
        photo_url="https://images.unsplash.com/photo-1617196034476-16067842f1e5?w=600&h=300&fit=crop&auto=format",
        keywords=["chinese american", "slippery shrimp", "chinatown", "dtla", "downtown", "洛杉矶"],
    ),
    PlaceResult(
        place_id="mock_howlin_rays",
        name="Howlin' Ray's",
        name_zh=None,
        address="727 N Broadway #128, Los Angeles, CA 90012",
        lat=34.0601, lng=-118.2398,
        google_rating=4.4, google_score=88.0,
        price_level=PriceLevel.budget,
        cuisine_type="炸鸡",
        total_ratings=5820,
        google_maps_url="https://maps.google.com/?q=Howlin+Rays+Los+Angeles",
        photo_url="https://images.unsplash.com/photo-1626645738196-c2a7c87a8f58?w=600&h=300&fit=crop&auto=format",
        keywords=["nashville hot chicken", "fried chicken", "chinatown", "dtla", "downtown", "洛杉矶", "网红"],
    ),
    PlaceResult(
        place_id="mock_sushi_gen",
        name="Sushi Gen",
        name_zh=None,
        address="422 E 2nd St, Los Angeles, CA 90012",
        lat=34.0481, lng=-118.2390,
        google_rating=4.5, google_score=90.0,
        price_level=PriceLevel.moderate,
        cuisine_type="日本料理",
        total_ratings=4477,
        google_maps_url="https://maps.google.com/?q=Sushi+Gen+Los+Angeles",
        photo_url="https://images.unsplash.com/photo-1553621042-f6e147245754?w=600&h=300&fit=crop&auto=format",
        keywords=["sushi", "japanese", "little tokyo", "dtla", "downtown", "洛杉矶", "日料"],
    ),
    PlaceResult(
        place_id="mock_full_house",
        name="Full House Seafood Restaurant",
        name_zh="满堂红海鲜酒家",
        address="963 N Hill St, Los Angeles, CA 90012",
        lat=34.0638, lng=-118.2358,
        google_rating=3.7, google_score=74.0,
        price_level=PriceLevel.moderate,
        cuisine_type="粤式海鲜",
        total_ratings=1893,
        google_maps_url="https://maps.google.com/?q=Full+House+Seafood+Los+Angeles",
        photo_url="https://images.unsplash.com/photo-1559847844-5315695dadae?w=600&h=300&fit=crop&auto=format",
        keywords=["cantonese", "seafood", "dim sum", "chinatown", "dtla", "downtown", "洛杉矶"],
    ),

    # ── Koreatown ─────────────────────────────────────────────────────────────
    PlaceResult(
        place_id="mock_parks_bbq",
        name="Park's BBQ",
        name_zh="朴家烤肉",
        address="955 S Vermont Ave, Los Angeles, CA 90006",
        lat=34.0574, lng=-118.2917,
        google_rating=4.6, google_score=92.0,
        price_level=PriceLevel.expensive,
        cuisine_type="韩式烤肉",
        total_ratings=7103,
        google_maps_url="https://maps.google.com/?q=Parks+BBQ+Los+Angeles",
        photo_url="https://images.unsplash.com/photo-1567188040759-fb8a883dc6d8?w=600&h=300&fit=crop&auto=format",
        keywords=["korean bbq", "galbi", "wagyu", "koreatown", "ktown", "usc", "洛杉矶"],
    ),
    PlaceResult(
        place_id="mock_kang_hodong",
        name="Kang Ho-dong Baekjeong",
        name_zh="姜虎东白丁烤肉",
        address="3465 W 6th St, Los Angeles, CA 90020",
        lat=34.0608, lng=-118.2952,
        google_rating=4.3, google_score=86.0,
        price_level=PriceLevel.expensive,
        cuisine_type="韩式烤肉",
        total_ratings=5234,
        google_maps_url="https://maps.google.com/?q=Kang+Ho+Dong+Baekjeong+Los+Angeles",
        photo_url="https://images.unsplash.com/photo-1567188040759-fb8a883dc6d8?w=600&h=300&fit=crop&auto=format",
        keywords=["korean bbq", "celebrity", "koreatown", "ktown", "usc", "洛杉矶", "网红"],
    ),

    # ── USC / University Park ──────────────────────────────────────────────────
    PlaceResult(
        place_id="mock_daves_hot_chicken",
        name="Dave's Hot Chicken",
        name_zh=None,
        address="3606 S Figueroa St, Los Angeles, CA 90007",
        lat=34.0168, lng=-118.2826,
        google_rating=4.3, google_score=86.0,
        price_level=PriceLevel.budget,
        cuisine_type="炸鸡",
        total_ratings=3892,
        google_maps_url="https://maps.google.com/?q=Daves+Hot+Chicken+USC",
        photo_url="https://images.unsplash.com/photo-1626645738196-c2a7c87a8f58?w=600&h=300&fit=crop&auto=format",
        keywords=["hot chicken", "fried chicken", "usc", "university park", "student", "洛杉矶"],
    ),
    PlaceResult(
        place_id="mock_broken_mouth",
        name="Broken Mouth",
        name_zh="港式早餐",
        address="3561 Figueroa St, Los Angeles, CA 90007",
        lat=34.0175, lng=-118.2839,
        google_rating=4.2, google_score=84.0,
        price_level=PriceLevel.budget,
        cuisine_type="港式茶餐厅",
        total_ratings=1648,
        google_maps_url="https://maps.google.com/?q=Broken+Mouth+Los+Angeles",
        photo_url="https://images.unsplash.com/photo-1550547660-d9450f859349?w=600&h=300&fit=crop&auto=format",
        keywords=["hong kong", "hk", "breakfast", "egg tart", "usc", "university park", "茶餐厅", "洛杉矶"],
    ),

    # ── Rowland Heights ───────────────────────────────────────────────────────
    PlaceResult(
        place_id="mock_earthen",
        name="Earthen",
        name_zh="土",
        address="1015 S Nogales St #128, Rowland Heights, CA 91748",
        lat=33.9839, lng=-117.8699,
        google_rating=3.5, google_score=70.0,
        price_level=PriceLevel.moderate,
        cuisine_type="客家菜",
        total_ratings=612,
        google_maps_url="https://maps.google.com/?q=Earthen+Rowland+Heights",
        photo_url="https://images.unsplash.com/photo-1563245372-f21724e3856d?w=600&h=300&fit=crop&auto=format",
        keywords=["hakka", "fujian", "regional chinese", "rowland heights", "华人区", "罗兰岗"],
    ),
    PlaceResult(
        place_id="mock_hui_tou_xiang",
        name="Hui Tou Xiang",
        name_zh="回头香",
        address="1015 S Nogales St #D, Rowland Heights, CA 91748",
        lat=33.9841, lng=-117.8701,
        google_rating=3.6, google_score=72.0,
        price_level=PriceLevel.budget,
        cuisine_type="东北饺子",
        total_ratings=834,
        google_maps_url="https://maps.google.com/?q=Hui+Tou+Xiang+Rowland+Heights",
        photo_url="https://images.unsplash.com/photo-1606787364406-a3cdf06c6d0c?w=600&h=300&fit=crop&auto=format",
        keywords=["dumplings", "northeast chinese", "dongbei", "rowland heights", "华人区", "罗兰岗"],
    ),
    PlaceResult(
        place_id="mock_yi_mei_deli",
        name="Yi Mei Deli",
        name_zh="益美台湾卤肉饭",
        address="18406 Colima Rd, Rowland Heights, CA 91748",
        lat=33.9853, lng=-117.8712,
        google_rating=3.4, google_score=68.0,
        price_level=PriceLevel.budget,
        cuisine_type="台湾小吃",
        total_ratings=421,
        google_maps_url="https://maps.google.com/?q=Yi+Mei+Deli+Rowland+Heights",
        photo_url="https://images.unsplash.com/photo-1551782450-a2132b4ba21d?w=600&h=300&fit=crop&auto=format",
        keywords=["taiwanese", "braised pork rice", "lu rou fan", "rowland heights", "华人区", "罗兰岗"],
    ),
    PlaceResult(
        place_id="mock_hi_top",
        name="Hi-Top Restaurant",
        name_zh="喜多港式茶餐厅",
        address="18459 Colima Rd, Rowland Heights, CA 91748",
        lat=33.9857, lng=-117.8720,
        google_rating=3.8, google_score=76.0,
        price_level=PriceLevel.budget,
        cuisine_type="港式茶餐厅",
        total_ratings=1102,
        google_maps_url="https://maps.google.com/?q=Hi-Top+Restaurant+Rowland+Heights",
        photo_url="https://images.unsplash.com/photo-1550547660-d9450f859349?w=600&h=300&fit=crop&auto=format",
        keywords=["hong kong", "cha chaan teng", "milk tea", "rowland heights", "华人区", "罗兰岗", "茶餐厅"],
    ),

    # ── Irvine / 尔湾 ────────────────────────────────────────────────────────
    PlaceResult(
        place_id="mock_shabu_zone",
        name="Shabu Zone",
        name_zh="涮涮锅",
        address="2610 Alton Pkwy #125, Irvine, CA 92606",
        lat=33.6773, lng=-117.7964,
        google_rating=4.1, google_score=82.0,
        price_level=PriceLevel.moderate,
        cuisine_type="日式火锅",
        total_ratings=2341,
        google_maps_url="https://maps.google.com/?q=Shabu+Zone+Irvine",
        photo_url="https://images.unsplash.com/photo-1585032226651-759b368d7246?w=600&h=300&fit=crop&auto=format",
        keywords=["shabu shabu", "hotpot", "japanese", "irvine", "diamond jamboree", "尔湾", "华人区"],
    ),
    PlaceResult(
        place_id="mock_tasty_noodle_irvine",
        name="Tasty Noodle House",
        name_zh="好味牛肉面",
        address="14 Creek Rd #120, Irvine, CA 92604",
        lat=33.6673, lng=-117.7785,
        google_rating=3.9, google_score=78.0,
        price_level=PriceLevel.budget,
        cuisine_type="台湾牛肉面",
        total_ratings=1187,
        google_maps_url="https://maps.google.com/?q=Tasty+Noodle+House+Irvine",
        photo_url="https://images.unsplash.com/photo-1569050467447-ce54b3bbc37d?w=600&h=300&fit=crop&auto=format",
        keywords=["taiwanese", "beef noodle soup", "noodles", "irvine", "尔湾", "华人区"],
    ),
    PlaceResult(
        place_id="mock_lings_garden",
        name="Ling's Garden",
        name_zh="凌家花园上海菜",
        address="4160 Barranca Pkwy, Irvine, CA 92604",
        lat=33.6882, lng=-117.7782,
        google_rating=3.6, google_score=72.0,
        price_level=PriceLevel.moderate,
        cuisine_type="上海菜",
        total_ratings=743,
        google_maps_url="https://maps.google.com/?q=Lings+Garden+Irvine",
        photo_url="https://images.unsplash.com/photo-1548943487-a2e4e43b4853?w=600&h=300&fit=crop&auto=format",
        keywords=["shanghai", "soup dumpling", "xiaolongbao", "irvine", "尔湾", "华人区"],
    ),
    PlaceResult(
        place_id="mock_dtf_south_coast",
        name="Din Tai Fung South Coast Plaza",
        name_zh="鼎泰丰（南海岸店）",
        address="3333 Bristol St, Costa Mesa, CA 92626",
        lat=33.6891, lng=-117.8879,
        google_rating=4.6, google_score=92.0,
        price_level=PriceLevel.expensive,
        cuisine_type="台式点心",
        total_ratings=10234,
        google_maps_url="https://maps.google.com/?q=Din+Tai+Fung+South+Coast+Plaza",
        photo_url="https://images.unsplash.com/photo-1548943487-a2e4e43b4853?w=600&h=300&fit=crop&auto=format",
        keywords=["xiao long bao", "soup dumplings", "taiwanese", "irvine", "costa mesa", "south coast", "尔湾", "network red"],
    ),
    PlaceResult(
        place_id="mock_newport_seafood_irvine",
        name="Newport Seafood Restaurant",
        name_zh="新港海鲜酒楼",
        address="4176 Campus Dr, Irvine, CA 92612",
        lat=33.6742, lng=-117.8304,
        google_rating=4.3, google_score=86.0,
        price_level=PriceLevel.moderate,
        cuisine_type="粤式海鲜",
        total_ratings=2876,
        google_maps_url="https://maps.google.com/?q=Newport+Seafood+Irvine",
        photo_url="https://images.unsplash.com/photo-1559847844-5315695dadae?w=600&h=300&fit=crop&auto=format",
        keywords=["seafood", "cantonese", "lobster", "irvine", "尔湾", "华人区"],
    ),
]


def _matches_budget(place: PlaceResult, budget: Optional[PriceLevel]) -> bool:
    if budget is None:
        return True
    levels = [PriceLevel.budget, PriceLevel.moderate, PriceLevel.expensive, PriceLevel.luxury]
    return levels.index(place.price_level) <= levels.index(budget)


def _matches_cuisine(place: PlaceResult, cuisine: Optional[str]) -> bool:
    if not cuisine:
        return True
    q = cuisine.lower().strip()
    ct = place.cuisine_type.lower()
    if q in ct or ct in q:
        return True
    # CJK: check only the FIRST CJK character of the query (the classifier).
    # Checking all chars causes false matches — e.g. 菜 appears in both 粤菜 and 川菜.
    for ch in q:
        if ord(ch) > 0x4E00:
            return ch in ct
    return any(q in kw.lower() or kw.lower() in q for kw in place.keywords)


# Area groups → constituent city/neighborhood substrings (matched against address + keywords).
# Lets a fuzzy "SGV" / "华人区" query resolve to the right cities.
_AREA_ALIASES = {
    "sgv": ["alhambra", "san gabriel", "monterey park", "arcadia", "rosemead",
            "temple city", "el monte", "san marino"],
    "san gabriel valley": ["alhambra", "san gabriel", "monterey park", "arcadia",
                           "rosemead", "temple city", "el monte", "san marino"],
    "华人区": ["alhambra", "san gabriel", "monterey park", "arcadia", "rosemead",
              "temple city", "rowland heights", "irvine"],
    "dtla": ["downtown", "los angeles"],
    "downtown": ["downtown", "los angeles"],
    "ktown": ["koreatown", "los angeles"],
}


def _matches_area(place: PlaceResult, area: Optional[str]) -> bool:
    if not area:
        return True
    a = area.lower().strip()
    terms = _AREA_ALIASES.get(a, [a])  # known group → its cities, else the area itself
    haystack = place.address.lower() + " " + " ".join(k.lower() for k in place.keywords)
    return any(t in haystack for t in terms)


async def search_restaurants(
    query: str = "",
    budget: Optional[PriceLevel] = None,
    cuisine: Optional[str] = None,
    area: Optional[str] = None,
    limit: int = 5,
) -> list[PlaceResult]:
    """Search mock restaurant DB. Simulates ~0.8s Google Places latency."""
    await asyncio.sleep(0.8)

    results = [
        p for p in _MOCK_PLACES
        if _matches_budget(p, budget) and _matches_cuisine(p, cuisine)
    ]

    # Area is a soft filter: apply it, but if it would empty the results, relax it
    # (incomplete area data shouldn't hide otherwise-matching restaurants).
    if area:
        narrowed = [p for p in results if _matches_area(p, area)]
        if narrowed:
            results = narrowed

    if query:
        q = query.lower()
        scored = []
        for p in results:
            score = 0
            if q in p.name.lower():
                score += 3
            if p.name_zh and q in p.name_zh:
                score += 3
            # keyword match: check both directions so area tags ("dtla" in "dtla好吃的") resolve
            if any(q in kw.lower() or kw.lower() in q for kw in p.keywords):
                score += 2
            if q in p.cuisine_type.lower() or p.cuisine_type.lower() in q:
                score += 2
            if q in p.address.lower():
                score += 1
            scored.append((score, p))
        scored.sort(key=lambda x: -x[0])
        results = [p for _, p in scored if _ >= 0]

    return results[:limit]


async def get_place_detail(place_id: str) -> Optional[PlaceResult]:
    """Fetch a single restaurant by place_id."""
    await asyncio.sleep(0.3)
    for place in _MOCK_PLACES:
        if place.place_id == place_id:
            return place
    return None
