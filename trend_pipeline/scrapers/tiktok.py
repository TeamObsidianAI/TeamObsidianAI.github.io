"""
TikTok trending product scraper.

Primary source: TikTok Creative Center public API (no auth needed for basic data).
  https://ads.tiktok.com/creative_radar_api/v1/popular_trend/list

Fallback: Parses TikTok hashtag search pages to infer trending product categories
from high-engagement shopping-related hashtags.

If TikTok blocks both approaches (they do rotate protections), the pipeline still
runs successfully — this scraper returns an empty list rather than crashing.
"""

import json
import logging
from .base import BaseScraper
from config import REQUEST_DELAY

logger = logging.getLogger(__name__)

_CREATIVE_CENTER_URL = (
    "https://ads.tiktok.com/creative_radar_api/v1/popular_trend/list"
    "?period=7&page=1&limit=50&country_code=US&language=en"
)

_HASHTAG_SEARCH_URL = "https://www.tiktok.com/api/search/hashtag/preview/?keyword={keyword}&count=20"

# Shopping-intent hashtags most associated with product discovery / impulse buying
SHOPPING_HASHTAGS = [
    "tiktokmademebuyit",
    "tiktokshop",
    "amazonfinds",
    "productreview",
    "unboxing",
    "musthave",
    "dealoftheday",
    "smallbusiness",
]

_CC_HEADERS = {
    "Referer": "https://ads.tiktok.com/creative-center/trends/popular-hashtag/pc/en",
    "Origin": "https://ads.tiktok.com",
    "Accept": "application/json, text/plain, */*",
}


class TikTokScraper(BaseScraper):
    def __init__(self, delay: float = REQUEST_DELAY):
        super().__init__(delay)

    # ── Creative Center API ──────────────────────────────────────────────────

    def _fetch_creative_center(self) -> list[dict]:
        try:
            self.session.headers.update(_CC_HEADERS)
            resp = self._get(_CREATIVE_CENTER_URL)
            data = resp.json()
            trends = data.get("data", {}).get("list", [])
            products = []
            for item in trends:
                hashtag = item.get("hashtag_name", "")
                view_count = item.get("video_views", 0)
                products.append(
                    {
                        "name": f"#{hashtag}",
                        "hashtag": hashtag,
                        "view_count": view_count,
                        "publish_count": item.get("publish_cnt", 0),
                        "category": _infer_category(hashtag),
                        "list_type": "tiktok_trending_hashtag",
                        "platform": "tiktok",
                    }
                )
            logger.info("TikTok Creative Center: %d trending hashtags", len(products))
            return products
        except Exception as e:
            logger.warning("TikTok Creative Center failed: %s", e)
            return []

    # ── Hashtag metadata fallback ────────────────────────────────────────────

    def _fetch_hashtag_meta(self, hashtag: str) -> dict | None:
        url = _HASHTAG_SEARCH_URL.format(keyword=hashtag)
        try:
            resp = self._get(url)
            data = resp.json()
            items = data.get("hashtag_list", [])
            if not items:
                return None
            top = items[0]
            return {
                "name": f"#{hashtag}",
                "hashtag": hashtag,
                "view_count": top.get("view_count", 0),
                "video_count": top.get("video_count", 0),
                "category": _infer_category(hashtag),
                "list_type": "tiktok_shopping_hashtag",
                "platform": "tiktok",
            }
        except Exception as e:
            logger.debug("TikTok hashtag fetch failed for #%s: %s", hashtag, e)
            return None

    # ── Public entry point ───────────────────────────────────────────────────

    def get_trending(self) -> list[dict]:
        results = self._fetch_creative_center()

        # If Creative Center gave us nothing useful, fall back to hashtag search
        if not results:
            logger.info("TikTok: falling back to hashtag search")
            for tag in SHOPPING_HASHTAGS:
                meta = self._fetch_hashtag_meta(tag)
                if meta:
                    results.append(meta)

        logger.info("TikTok total: %d items collected", len(results))
        return results


_CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "Electronics": ["tech", "gadget", "phone", "laptop", "earbuds", "camera", "smart", "usb", "wireless"],
    "Beauty & Personal Care": ["skincare", "makeup", "beauty", "glow", "serum", "hair", "nails", "lips", "foundation"],
    "Home & Kitchen": ["home", "kitchen", "cleaning", "organiz", "decor", "bedroom", "storage", "cook"],
    "Toys & Games": ["toy", "game", "kids", "children", "lego", "puzzle", "play", "anime"],
    "Sports & Outdoors": ["fitness", "gym", "yoga", "sport", "outdoor", "hiking", "running", "workout"],
    "Pet Supplies": ["pet", "dog", "cat", "puppy", "kitten"],
    "Fashion": ["fashion", "style", "outfit", "clothing", "shirt", "dress", "shoes", "bag", "accessories"],
    "Health & Wellness": ["health", "wellness", "supplement", "vitamin", "protein", "organic", "natural"],
}


def _infer_category(hashtag: str) -> str:
    ht = hashtag.lower()
    for category, keywords in _CATEGORY_KEYWORDS.items():
        if any(kw in ht for kw in keywords):
            return category
    return "General"
