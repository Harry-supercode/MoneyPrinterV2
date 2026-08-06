import re


DEFAULT_HASHTAGS = [
    "#Hiemee",
    "#HiemeeGround",
    "#BusinessEcosystem",
    "#CashflowToAssets",
]


KEYWORD_HASHTAGS = {
    "hiemee": "#Hiemee",
    "hie-palace": "#HiePalace",
    "hie palace": "#HiePalace",
    "restaurant": "#Hospitality",
    "hospitality": "#Hospitality",
    "wedding": "#WeddingVenue",
    "event": "#EventBusiness",
    "software": "#HieSoftware",
    "saas": "#SaaS",
    "crm": "#CRM",
    "automation": "#Automation",
    "real estate": "#HieRealty",
    "property": "#RealEstate",
    "asset": "#TichLuyTaiSan",
    "hiefundi": "#hieFundi",
    "fintech": "#FintechVietnam",
    "savings": "#TaiChinhCongDong",
    "hieevplus": "#HieEVPlus",
    "ev": "#EVCharging",
    "green": "#GreenTech",
    "founder": "#FounderJourney",
    "build in public": "#BuildInPublic",
}


def build_caption(title: str, description: str = "", max_hashtags: int = 4) -> str:
    text = f"{title} {description}".lower()

    hashtags = []

    for hashtag in DEFAULT_HASHTAGS:
        hashtags.append(hashtag)

    for keyword, hashtag in KEYWORD_HASHTAGS.items():
        if re.search(rf"\b{re.escape(keyword)}\b", text):
            hashtags.append(hashtag)

    unique_hashtags = []
    for tag in hashtags:
        if tag not in unique_hashtags:
            unique_hashtags.append(tag)

    final_hashtags = unique_hashtags[:max_hashtags]

    return f"{title}\n\n{' '.join(final_hashtags)}"
