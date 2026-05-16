"""
XHSSentimentTool — Mock implementation.

Interface contract (swap this file for a real scraper later):
  get_xhs_sentiment(restaurant_name: str) -> XHSSentimentResult | None

Scores are computed by the real xhs_scorer.compute_xhs_score() algorithm at
module load — NOT hardcoded — so they reflect the same logic that would be
applied to real scrape data.

Score design:
  Volume   (0–40): log1p(post_count) × 6.5,  capped at 40  (≥500 posts → 40)
  Engagement(0–40): log1p(saves×3+likes+cmts×0.5) × 5.5, capped at 40
  Sentiment (0–20): max(0, min(20, 10 + net_keyword_weight × 0.8))

Quadrant strategy:
  华人必打卡  — high volume, high saves (people bookmark for future visits),
                strong positive keywords          → XHS 85–95
  隐藏宝藏   — moderate volume, high saves & positive keywords (community
                loves it even if Google doesn't)  → XHS 78–92
  网红店慎入 — low "authentic community" post_count, LOW saves (disappointed
                visitors don't save for later), heavy negative keywords → XHS 50–65
  普通推荐   — low volume, low engagement, neutral/mildly negative texts → XHS 48–65
"""

import asyncio
from dataclasses import dataclass
from typing import Optional

from tools.xhs_scorer import compute_xhs_score


@dataclass
class XHSSentimentResult:
    restaurant_name: str
    xhs_score: float          # 0-100, computed by algorithm
    post_count: int
    avg_rating: float         # 1-5 stars on XHS
    top_keywords: list[str]   # curated positive tags for display
    warning_keywords: list[str]   # curated negative tags for display
    sample_comment: str       # representative comment for LLM prompt


# ── Raw mock data ─────────────────────────────────────────────────────────────
# interactions: list of representative posts with likes/saves/comments.
# texts: natural-language strings fed to the scorer; designed to trigger the
#        correct POSITIVE_KEYWORDS / NEGATIVE_KEYWORDS matches.
# top_keywords / warning_keywords: curated display labels (≠ scorer keywords).

_RAW: dict[str, dict] = {

    # ── SGV / Alhambra ────────────────────────────────────────────────────────

    # 华人必打卡 — XHS ~92, Google 88
    "101 Noodle Express": {
        "post_count": 847,
        "avg_rating": 4.7,
        "interactions": [{"likes": 150, "saves": 65, "comments": 30}] * 10,
        "texts": [
            "来SGV必吃！牛肉卷饼正宗好吃，必打卡强烈推荐，量大实惠不踩雷，值得排队好评。",
            "北方面食正宗地道，下次还来，推荐给所有人，满意好评。",
        ],
        "top_keywords": ["牛肉卷饼一绝", "排队值得", "正宗北方味", "量大实惠"],
        "warning_keywords": [],
        "sample_comment": "来SGV必吃！牛肉卷饼皮薄馅足，老板娘说是家传秘方，每次来都要等位但绝对值得。",
    },

    # 华人必打卡 — XHS ~90, Google 86
    "Lunasia Dim Sum House": {
        "post_count": 1203,
        "avg_rating": 4.5,
        "interactions": [{"likes": 140, "saves": 55, "comments": 28}] * 10,
        "texts": [
            "阿罕布拉最正宗粤式早茶，虾饺好吃推荐，值得来，好评满意。",
            "粤式早茶正宗，推荐必吃，好评。周末等位久一般需预约。",
        ],
        "top_keywords": ["虾饺皮薄", "推车服务", "粤式正宗", "适合家庭聚餐"],
        "warning_keywords": ["周末等位久"],
        "sample_comment": "阿罕布拉最正宗的粤式早茶！虾饺晶莹剔透，肠粉滑嫩，推车阿姨很热情，价格比香港还便宜。",
    },

    # 隐藏宝藏 — XHS ~92, Google 72
    "Chengdu Taste": {
        "post_count": 562,
        "avg_rating": 4.6,
        "interactions": [{"likes": 140, "saves": 60, "comments": 28}] * 10,
        "texts": [
            "不要被外表骗了！正宗成都菜必打卡，麻辣鲜香地道，强烈推荐不踩雷，好吃值得，好评。",
            "华人圈口碑极好，正宗地道好吃，推荐必吃，下次还来满意。",
        ],
        "top_keywords": ["麻辣鲜香", "正宗成都味", "华人圈口碑炸裂", "不踩雷"],
        "warning_keywords": ["装修简陋", "停车难"],
        "sample_comment": "不要被外表骗了！破破烂烂的店面里藏着洛杉矶最正宗的成都菜，夫妻肺片麻辣鲜香，钟水饺一口一个停不下来，国内朋友来必带！",
    },

    # 网红店慎入 — XHS ~60, Google 90
    # 低saves（失望的人不收藏），高负面关键词
    "Din Tai Fung Arcadia": {
        "post_count": 150,
        "avg_rating": 3.8,
        "interactions": [{"likes": 120, "saves": 5, "comments": 35}] * 10,
        "texts": [
            "踩雷了，商业化严重，给外国人吃的，太贵不值得，失望不推荐，网红店一般。",
            "比台湾本店差很多，不推荐，太贵，不值得排队，失望。",
        ],
        "top_keywords": ["小笼包皮薄", "服务标准", "适合接待"],
        "warning_keywords": ["价格偏高", "排队两小时", "和台湾本店差距大", "比较商业化"],
        "sample_comment": "说实话有点失望，小笼包的皮和馅料比台湾本店差很多，价格还更贵。更像是给老外体验中餐的地方，本地华人不太推荐专程来。",
    },

    # 普通推荐 — XHS ~57, Google 74
    "Golden Deli Vietnamese Restaurant": {
        "post_count": 60,
        "avg_rating": 3.5,
        "interactions": [{"likes": 20, "saves": 8, "comments": 5}] * 10,
        "texts": [
            "越南菜还不错，春卷好吃，汤底一般，整体中规中矩。",
        ],
        "top_keywords": ["春卷酥脆", "汤底清甜"],
        "warning_keywords": ["服务一般", "环境嘈杂"],
        "sample_comment": "越南菜做得还可以，春卷是亮点，但整体中规中矩，SGV有太多更好的选择，不用专程来。",
    },

    # ── SGV / Rosemead / Monterey Park / Temple City ──────────────────────────

    # 华人必打卡 — XHS ~94, Google 92
    "Sea Harbour Seafood Restaurant": {
        "post_count": 2187,
        "avg_rating": 4.8,
        "interactions": [{"likes": 220, "saves": 85, "comments": 42}] * 10,
        "texts": [
            "LA最强早茶！虾饺正宗好吃必打卡，流沙包强烈推荐不踩雷，新鲜食材值得来，好评满意下次还来。",
            "粤式早茶正宗地道，必吃推荐好评，新鲜食材不踩雷，值得专程来满意。",
        ],
        "top_keywords": ["LA最强早茶", "虾饺无敌", "必点流沙包", "新鲜海鲜", "正宗粤味"],
        "warning_keywords": ["周末需提前订位", "停车场有限"],
        "sample_comment": "毫无疑问洛杉矶最好吃的粤式早茶！虾饺皮薄馅大弹牙，流沙包一咬爆浆，海鲜每天新鲜到货。每次从OC专程开车来都值得，已经来了十几次。",
    },

    # 华人必打卡 — XHS ~91, Google 86
    "Elite Restaurant": {
        "post_count": 1456,
        "avg_rating": 4.4,
        "interactions": [{"likes": 130, "saves": 50, "comments": 26}] * 10,
        "texts": [
            "满福楼粤式早茶正宗好吃，推荐值得来，好评满意，干净环境。",
            "正宗粤菜推荐，好吃不踩雷，值得好评。",
        ],
        "top_keywords": ["正宗粤式", "环境雅致", "适合宴请", "早茶推荐"],
        "warning_keywords": ["价格偏高", "停车不便"],
        "sample_comment": "满福楼是蒙特利公园的老字号，粤菜做得非常正宗，适合请家人朋友吃饭。早茶的虾饺和叉烧包都是水准之作，服务也很周到。",
    },

    # 华人必打卡 — XHS ~93, Google 80
    "Bistro Na's": {
        "post_count": 892,
        "avg_rating": 4.6,
        "interactions": [{"likes": 160, "saves": 62, "comments": 32}] * 10,
        "texts": [
            "那家小馆北京菜正宗好吃必打卡！北京烤鸭强烈推荐不踩雷，值得，好评满意下次还来。",
            "正宗北京味道地道，必吃推荐，好吃值得好评。",
        ],
        "top_keywords": ["北京烤鸭必点", "宫廷菜正宗", "华人必打卡", "比北京还正宗"],
        "warning_keywords": ["价格不低", "需要提前订位"],
        "sample_comment": "在LA吃到了魂牵梦绕的北京味道！烤鸭皮脆肉嫩，要趁热蘸甜面酱卷饼吃，麻豆腐和炒肝都让我想起小时候在北京的味道。SGV隐藏宝藏。",
    },

    # 网红店慎入 — XHS ~62, Google 88
    "Haidilao Hot Pot Arcadia": {
        "post_count": 200,
        "avg_rating": 3.6,
        "interactions": [{"likes": 100, "saves": 6, "comments": 40}] * 10,
        "texts": [
            "踩雷！太贵不值得，商业化，失望不推荐，一般，等位久，服务差无功无过。",
            "国内水平高多了，太贵不推荐，失望，一般般。",
        ],
        "top_keywords": ["服务超好", "等位体验", "免费小食"],
        "warning_keywords": ["价格太贵", "食材一般", "国内水平高多了", "不值这个价"],
        "sample_comment": "服务真的很好，等位有免费小食和擦鞋服务，但食材质量比国内差很多，价格反而贵两三倍。在美国吃海底捞是在为服务买单，不是为食材。",
    },

    # 隐藏宝藏 — XHS ~88, Google 72
    "New Capital Seafood Restaurant": {
        "post_count": 423,
        "avg_rating": 4.4,
        "interactions": [{"likes": 65, "saves": 30, "comments": 14}] * 10,
        "texts": [
            "新京都老字号正宗粤菜，好吃推荐，实惠不踩雷，值得去好评。",
            "正宗海鲜好吃，推荐值得，实惠好评，不踩雷。",
        ],
        "top_keywords": ["老字号正宗", "价格实惠", "华人街坊最爱", "不踩雷"],
        "warning_keywords": ["装修老旧", "停车难"],
        "sample_comment": "这家是SGV本地华人老字坊，Google评分不高但真的被严重低估了！生猛海鲜价格公道，蒸鱼火候刚好，清蒸龙虾鲜甜无比，强烈推荐不爱拍照的实在派。",
    },

    # 华人必打卡 — XHS ~86, Google 84
    "Huge Tree Pastry": {
        "post_count": 634,
        "avg_rating": 4.3,
        "interactions": [{"likes": 90, "saves": 35, "comments": 18}] * 10,
        "texts": [
            "台式早餐正宗好吃，推荐实惠，值得来好评，不错干净。",
            "台湾早餐好吃推荐，实惠不错，满意好评。",
        ],
        "top_keywords": ["台式早餐地道", "皮蛋瘦肉粥必点", "奶茶超香", "价格亲民"],
        "warning_keywords": ["排队时间长", "座位有限"],
        "sample_comment": "蒙特利公园最正宗的台湾早餐！皮蛋瘦肉粥滑嫩顺口，油条酥脆，搭配招牌奶茶完美。价格超亲民，早上来排队的全是街坊老华人，就知道靠谱。",
    },

    # ── DTLA / Chinatown / Little Tokyo ───────────────────────────────────────

    # 网红店慎入 — XHS ~58, Google 78
    "Yang Chow Restaurant": {
        "post_count": 130,
        "avg_rating": 3.2,
        "interactions": [{"likes": 85, "saves": 5, "comments": 25}] * 10,
        "texts": [
            "踩雷！商业化严重，给外国人吃的，一般不推荐，太贵，不值得，网红店。",
            "美式化中餐，不推荐，一般，失望，网红店。",
        ],
        "top_keywords": ["唐人街地标", "滑溜虾有名", "适合老外"],
        "warning_keywords": ["口味美式化", "正宗度低", "本地华人不推荐", "游客店"],
        "sample_comment": "唐人街历史地标，但食物已经完全美式化了。滑溜虾是招牌但甜腻不正宗，更适合第一次来唐人街的游客，本地华人基本不来，不踩雷就好。",
    },

    # 网红店慎入 — XHS ~55, Google 88
    "Howlin' Ray's": {
        "post_count": 100,
        "avg_rating": 3.4,
        "interactions": [{"likes": 80, "saves": 3, "comments": 25}] * 10,
        "texts": [
            "不推荐不值得，太贵，等位久，踩雷，咸，坑，失望，一般。",
            "不适合华人口味，踩雷，不推荐，太贵，等位久，一般。",
        ],
        "top_keywords": ["辣鸡翅有味道", "本地人气高"],
        "warning_keywords": ["排队1-2小时", "不值得等", "不适合中国人口味", "太咸太腻"],
        "sample_comment": "来DTLA排了一个半小时的队，口味对华人来说偏咸偏腻，辣度是美式辣不是中式辣，感觉这家更适合本地老外。如果只是想尝个鲜可以，但真的不值得那么长的队。",
    },

    # 华人必打卡 — XHS ~91, Google 90
    "Sushi Gen": {
        "post_count": 934,
        "avg_rating": 4.5,
        "interactions": [{"likes": 130, "saves": 50, "comments": 26}] * 10,
        "texts": [
            "LA日料性价比之王！刺身新鲜好吃，推荐值得，不踩雷，好评满意，性价比高。",
            "刺身新鲜，性价比高，推荐值得，好吃不踩雷，满意好评。",
        ],
        "top_keywords": ["刺身超新鲜", "CP值极高", "必点刺身拼盘", "日料中的隐藏宝藏"],
        "warning_keywords": ["等位1小时以上", "现金only", "不接受预订"],
        "sample_comment": "LA最物超所值的日料！刺身新鲜度堪比日本，价格却是高档日料馆的一半。午饭刺身拼盘$28包含十几种鱼，每一片都新鲜弹牙。一定要早点来排队，等位很正常但值得。",
    },

    # 隐藏宝藏 — XHS ~88, Google 74
    "Full House Seafood Restaurant": {
        "post_count": 518,
        "avg_rating": 4.4,
        "interactions": [{"likes": 60, "saves": 28, "comments": 12}] * 10,
        "texts": [
            "唐人街正宗粤菜好吃推荐！实惠不踩雷，值得去好评，不错满意。",
            "正宗粤菜好吃，推荐实惠不踩雷，值得好评。",
        ],
        "top_keywords": ["唐人街隐藏宝藏", "海鲜够新鲜", "价格实惠", "正宗粤味"],
        "warning_keywords": ["装修简陋", "停车难"],
        "sample_comment": "来DTLA唐人街不要只知道排网红队！这家满堂红才是本地粤语老街坊的心头好。清蒸石斑鱼新鲜弹牙，避风塘炒蟹香辣入味，价格比SGV还实惠，强烈推荐！",
    },

    # ── Koreatown ─────────────────────────────────────────────────────────────

    # 华人必打卡 — XHS ~93, Google 92
    "Park's BBQ": {
        "post_count": 1632,
        "avg_rating": 4.7,
        "interactions": [{"likes": 180, "saves": 70, "comments": 36}] * 10,
        "texts": [
            "LA最强韩烤必打卡！好吃正宗强烈推荐不踩雷，值得去，好评满意，下次还来。",
            "韩式烤肉正宗好吃，必打卡推荐，值得不踩雷，好评。",
        ],
        "top_keywords": ["LA最强韩烤", "和牛入口即化", "必点五花肉", "华人韩料首选"],
        "warning_keywords": ["价格偏高", "需要预订"],
        "sample_comment": "来洛杉矶没吃Park's BBQ等于没来过！和牛五花肉在炭火上滋滋作响，配上泡菜和包肉生菜，简直是人生中最好吃的烤肉。华人朋友聚餐必选，每次都约不停。",
    },

    # 网红店慎入 — XHS ~57, Google 86
    "Kang Ho-dong Baekjeong": {
        "post_count": 120,
        "avg_rating": 3.5,
        "interactions": [{"likes": 90, "saves": 4, "comments": 30}] * 10,
        "texts": [
            "踩雷！不推荐，失望，太贵，一般，名过其实，网红店，不值得，等位久。",
            "不推荐，踩雷，失望，太贵，一般，坑。",
        ],
        "top_keywords": ["明星开的", "环境不错", "网红打卡"],
        "warning_keywords": ["踩雷", "肉质一般", "价格虚高", "不如Park's BBQ", "名过其实"],
        "sample_comment": "冲着韩国摔跤明星去的，结果大踩雷。肉质比Park's BBQ差很多，价格却差不多，感觉在为明星效应买单。Koreatown有很多比这家好的选择，不推荐特意来。",
    },

    # ── USC / University Park ──────────────────────────────────────────────────

    # 网红店慎入 — XHS ~53, Google 86
    "Dave's Hot Chicken": {
        "post_count": 80,
        "avg_rating": 3.3,
        "interactions": [{"likes": 60, "saves": 2, "comments": 20}] * 10,
        "texts": [
            "不推荐，太贵，不值得，等位久，一般，咸，不适合华人口味。",
            "一般，太贵，不推荐，等位久，咸。",
        ],
        "top_keywords": ["辣鸡排有名气", "学生打卡"],
        "warning_keywords": ["口味重偏腻", "不适合华人口味", "太咸", "排队很久"],
        "sample_comment": "USC学生爱去的网红炸鸡，美式辣不是中式辣，对华人来说偏咸偏腻。如果好奇可以去尝鲜，但真的不值得特意排队，附近有更好的选择。",
    },

    # 华人必打卡 — XHS ~91, Google 84
    "Broken Mouth": {
        "post_count": 712,
        "avg_rating": 4.5,
        "interactions": [{"likes": 110, "saves": 45, "comments": 22}] * 10,
        "texts": [
            "港式早餐正宗好吃！推荐必吃，值得不踩雷，好评满意，干净实惠。",
            "港式早餐好吃正宗，推荐值得，好评不错。",
        ],
        "top_keywords": ["港式早餐正宗", "菠萝油必点", "奶茶香滑", "USC留学生心头好"],
        "warning_keywords": ["座位有限", "早高峰排队"],
        "sample_comment": "USC留学生的秘密基地！菠萝油外酥内软，配上丝袜奶茶绝了。蛋治三明治也是一绝，价格超亲民。每天早上都有大批华人学生来，在USC附近能吃到这么正宗的港式早餐真的很幸运。",
    },

    # ── Rowland Heights ───────────────────────────────────────────────────────

    # 隐藏宝藏 — XHS ~88, Google 70
    "Earthen": {
        "post_count": 389,
        "avg_rating": 4.6,
        "interactions": [{"likes": 80, "saves": 40, "comments": 18}] * 10,
        "texts": [
            "客家菜正宗好吃必打卡！推荐不踩雷，值得，地道好评，满意下次还来。",
            "正宗客家菜好吃，推荐值得，不踩雷地道好评。",
        ],
        "top_keywords": ["客家菜正宗", "梅菜扣肉绝了", "华人圈口耳相传", "不踩雷"],
        "warning_keywords": ["地方偏僻", "装修简朴", "Google评分虚低"],
        "sample_comment": "罗兰岗最被低估的宝藏！这家客家菜完全靠老华人口耳相传，梅菜扣肉肥而不腻，盐焗鸡皮脆肉嫩，仙人粄Q弹爽滑，全是在国内都难找到的家常味道。强烈推荐！",
    },

    # 隐藏宝藏 — XHS ~89, Google 72
    "Hui Tou Xiang": {
        "post_count": 476,
        "avg_rating": 4.5,
        "interactions": [{"likes": 75, "saves": 38, "comments": 15}] * 10,
        "texts": [
            "东北饺子正宗好吃必打卡！皮薄馅大，推荐量大实惠，不踩雷值得，好评满意。",
            "正宗东北饺子好吃，推荐值得，量大实惠不踩雷，好评。",
        ],
        "top_keywords": ["东北饺子正宗", "皮薄馅大", "汤包鲜美", "量大实惠"],
        "warning_keywords": ["环境简陋", "等位时间长"],
        "sample_comment": "罗兰岗最正宗的东北饺子馆！猪肉韭菜饺子皮薄馅大，一口下去汁水四溢，让我想起东北老家的味道。东北人开的店，饺子皮现擀现包，价格实惠量大，华人圈极力推荐。",
    },

    # 普通推荐 — XHS ~55, Google 68
    "Yi Mei Deli": {
        "post_count": 50,
        "avg_rating": 3.7,
        "interactions": [{"likes": 18, "saves": 7, "comments": 4}] * 10,
        "texts": [
            "台湾小吃还行，卤肉饭一般，口味偏淡，不错但没有惊喜。",
        ],
        "top_keywords": ["卤肉饭还可以", "台湾小吃"],
        "warning_keywords": ["口味偏淡", "分量小", "性价比一般"],
        "sample_comment": "罗兰岗台湾小吃，卤肉饭味道中规中矩，卤味偏甜，没有很惊艳。如果在附近可以吃，不用特意来，罗兰岗有更好的台湾菜选择。",
    },

    # 网红店慎入 — XHS ~64, Google 76
    "Hi-Top Restaurant": {
        "post_count": 100,
        "avg_rating": 3.9,
        "interactions": [{"likes": 30, "saves": 12, "comments": 8}] * 10,
        "texts": [
            "港式茶餐厅还行，奶茶不错，食物一般，性价比还可以，推荐奶茶。",
        ],
        "top_keywords": ["港式奶茶不错", "茶餐厅氛围", "价格实惠"],
        "warning_keywords": ["食物一般", "服务慢", "不够正宗"],
        "sample_comment": "罗兰岗的港式茶餐厅，价格实惠，奶茶还不错，但食物水准只能说中规中矩。比不上正宗香港茶餐厅，但在罗兰岗这个价位也算过得去，解个馋还行。",
    },

    # ── Irvine / 尔湾 ────────────────────────────────────────────────────────

    # 华人必打卡 — XHS ~88, Google 82
    "Shabu Zone": {
        "post_count": 876,
        "avg_rating": 4.4,
        "interactions": [{"likes": 110, "saves": 40, "comments": 20}] * 10,
        "texts": [
            "尔湾日式火锅好吃推荐！食材新鲜，值得不踩雷，好评满意，推荐必吃。",
            "新鲜食材好吃推荐，不踩雷值得，好评满意。",
        ],
        "top_keywords": ["食材新鲜", "汤底鲜美", "尔湾华人聚餐首选", "性价比高"],
        "warning_keywords": ["周末需预约", "停车麻烦"],
        "sample_comment": "尔湾华人聚餐必备！食材新鲜，汤底可以选昆布柴鱼或辣味，海鲜拼盘大虾弹牙，肉卷薄而均匀。价格比SGV略贵但尔湾能吃到这水平很满意，已经去了五六次。",
    },

    # 华人必打卡 — XHS ~91, Google 78
    "Tasty Noodle House": {
        "post_count": 621,
        "avg_rating": 4.6,
        "interactions": [{"likes": 120, "saves": 45, "comments": 24}] * 10,
        "texts": [
            "台湾牛肉面正宗好吃必打卡！汤头浓郁强烈推荐，值得不踩雷，好评满意下次还来。",
            "正宗台湾牛肉面好吃，推荐不踩雷，值得好评。",
        ],
        "top_keywords": ["台湾牛肉面正宗", "汤头浓郁", "尔湾必吃", "红烧牛腩入口即化"],
        "warning_keywords": ["等位较长", "停车有限"],
        "sample_comment": "在尔湾找到了最正宗的台湾牛肉面！红烧汤头浓郁鲜美，牛腩炖得酥软入味，面条劲道有嚼劲。老板是台湾人，配方正宗，比洛杉矶很多台湾面馆都强，尔湾华人圈必打卡。",
    },

    # 隐藏宝藏 — XHS ~85, Google 72
    "Ling's Garden": {
        "post_count": 342,
        "avg_rating": 4.3,
        "interactions": [{"likes": 55, "saves": 26, "comments": 11}] * 10,
        "texts": [
            "上海本帮菜正宗好吃！推荐不踩雷，值得，好评满意，实惠推荐。",
            "正宗上海菜好吃，推荐值得，不踩雷好评。",
        ],
        "top_keywords": ["上海菜正宗", "小笼包皮薄", "尔湾隐藏宝藏", "红烧肉入口即化"],
        "warning_keywords": ["Google知名度低", "位置偏僻"],
        "sample_comment": "尔湾被严重低估的上海菜馆！小笼包皮薄汤多，一口下去要小心烫，红烧肉肥而不腻，葱油拌面简单却好吃。在OC区域能吃到这么地道的本帮菜真的很难得，强力推荐。",
    },

    # 网红店慎入 — XHS ~57, Google 92
    "Din Tai Fung South Coast Plaza": {
        "post_count": 80,
        "avg_rating": 3.6,
        "interactions": [{"likes": 120, "saves": 5, "comments": 45}] * 10,
        "texts": [
            "踩雷，商业化严重，太贵不值得，失望不推荐，给外国人吃的，一般，网红店。",
            "不推荐，踩雷，太贵，失望，商业化，不值得，一般。",
        ],
        "top_keywords": ["环境高档", "适合接待", "位置方便"],
        "warning_keywords": ["价格虚高", "水准不稳定", "商业化严重", "排队噩梦", "比台湾差很多"],
        "sample_comment": "南海岸商场里的鼎泰丰，位置高档，装修漂亮，但食物水准真的让人失望。小笼包皮厚汤少，价格比台湾本店贵一倍多，更像是给购物客和游客准备的。真正想吃小笼包的华人都去别处了。",
    },

    # 华人必打卡 — XHS ~93, Google 86
    "Newport Seafood Restaurant": {
        "post_count": 1134,
        "avg_rating": 4.6,
        "interactions": [{"likes": 170, "saves": 68, "comments": 34}] * 10,
        "texts": [
            "尔湾最强海鲜！正宗粤菜好吃必打卡，龙虾新鲜强烈推荐不踩雷，值得，好评满意。",
            "粤式海鲜正宗好吃，必打卡推荐不踩雷，新鲜值得好评满意。",
        ],
        "top_keywords": ["尔湾最强海鲜", "龙虾必点", "粤式正宗", "新鲜程度高"],
        "warning_keywords": ["价格偏高", "需提前预订"],
        "sample_comment": "OC区域最好的粤式海鲜！每天空运活龙虾和石斑鱼，蒸鱼火候完美保留鲜味，生炒龙虾姜葱味十足。价格不便宜但完全值得，尔湾华人请客吃饭首选，已经成为我们家的保留节目。",
    },
}


# ── Build scored DB at module load ────────────────────────────────────────────

def _build_db() -> dict[str, XHSSentimentResult]:
    db = {}
    for name, raw in _RAW.items():
        score = compute_xhs_score(
            raw["post_count"],
            raw["interactions"],
            raw["texts"],
        )
        db[name] = XHSSentimentResult(
            restaurant_name=name,
            xhs_score=score,
            post_count=raw["post_count"],
            avg_rating=raw["avg_rating"],
            top_keywords=raw["top_keywords"],
            warning_keywords=raw["warning_keywords"],
            sample_comment=raw["sample_comment"],
        )
    return db


_MOCK_DB: dict[str, XHSSentimentResult] = _build_db()

# Alias support — partial name matching for robustness
_ALIASES: dict[str, str] = {
    # SGV
    "101面馆": "101 Noodle Express",
    "101牛肉卷饼": "101 Noodle Express",
    "皇朝": "Lunasia Dim Sum House",
    "luna": "Lunasia Dim Sum House",
    "成都": "Chengdu Taste",
    "成都味道": "Chengdu Taste",
    "鼎泰丰arcadia": "Din Tai Fung Arcadia",
    "鼎泰丰阿凯迪亚": "Din Tai Fung Arcadia",
    "海港": "Sea Harbour Seafood Restaurant",
    "海港海鲜": "Sea Harbour Seafood Restaurant",
    "满福楼": "Elite Restaurant",
    "那家小馆": "Bistro Na's",
    "bistro na": "Bistro Na's",
    "海底捞": "Haidilao Hot Pot Arcadia",
    "haidilao": "Haidilao Hot Pot Arcadia",
    "新京都": "New Capital Seafood Restaurant",
    "大树饼": "Huge Tree Pastry",
    "huge tree": "Huge Tree Pastry",
    # DTLA / Chinatown
    "扬州": "Yang Chow Restaurant",
    "yang chow": "Yang Chow Restaurant",
    "howlin ray": "Howlin' Ray's",
    "howlin": "Howlin' Ray's",
    "满堂红": "Full House Seafood Restaurant",
    # Koreatown
    "朴家": "Park's BBQ",
    "park bbq": "Park's BBQ",
    "姜虎东": "Kang Ho-dong Baekjeong",
    "kang hodong": "Kang Ho-dong Baekjeong",
    # USC
    "broken mouth": "Broken Mouth",
    "港式早餐": "Broken Mouth",
    "dave hot chicken": "Dave's Hot Chicken",
    # Rowland Heights
    "earthen": "Earthen",
    "土": "Earthen",
    "回头香": "Hui Tou Xiang",
    "益美": "Yi Mei Deli",
    "喜多": "Hi-Top Restaurant",
    # Irvine
    "涮涮锅": "Shabu Zone",
    "shabu": "Shabu Zone",
    "好味牛肉面": "Tasty Noodle House",
    "凌家": "Ling's Garden",
    "ling garden": "Ling's Garden",
    "鼎泰丰南海岸": "Din Tai Fung South Coast Plaza",
    "din tai fung south": "Din Tai Fung South Coast Plaza",
    "新港": "Newport Seafood Restaurant",
    "newport seafood": "Newport Seafood Restaurant",
    # Generic (more specific alias first to avoid wrong match)
    "din tai fung": "Din Tai Fung Arcadia",
    "鼎泰丰": "Din Tai Fung Arcadia",
}


async def get_xhs_sentiment(restaurant_name: str) -> Optional[XHSSentimentResult]:
    """
    Fetch XHS sentiment for a restaurant. Simulates ~0.5s network latency.
    Returns None if restaurant not found (Agent should handle gracefully).
    """
    await asyncio.sleep(0.5)

    if restaurant_name in _MOCK_DB:
        return _MOCK_DB[restaurant_name]

    name_lower = restaurant_name.lower()
    for alias, canonical in _ALIASES.items():
        if alias.lower() in name_lower:
            return _MOCK_DB[canonical]

    for canonical in _MOCK_DB:
        if name_lower in canonical.lower() or canonical.lower() in name_lower:
            return _MOCK_DB[canonical]

    return None


async def get_all_restaurants_xhs() -> list[XHSSentimentResult]:
    """Return all mock XHS data — used for bulk queries."""
    await asyncio.sleep(0.3)
    return list(_MOCK_DB.values())
