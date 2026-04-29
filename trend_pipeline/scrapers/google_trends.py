"""
Google Trends scraper via pytrends (no API key required).

Pulls two signals:
1. Rising shopping queries per category (Google Shopping / Froogle)
2. Today's trending searches (general commerce filter applied post-hoc)

These help identify products people are actively searching to BUY, which
complements the "what's listed" data from Amazon and TikTok.
"""

import time
import logging
from pytrends.request import TrendReq

logger = logging.getLogger(__name__)

# Category keyword seeds → maps to broad product verticals
_CATEGORY_SEEDS: list[tuple[str, str]] = [
    ("Electronics", "electronics gadgets"),
    ("Home & Kitchen", "home decor kitchen"),
    ("Beauty", "skincare makeup beauty"),
    ("Toys", "toys kids games"),
    ("Sports", "fitness gym workout"),
    ("Pet Supplies", "dog cat pet supplies"),
    ("Fashion", "clothing shoes fashion"),
]

# Google Trends timeframes
_TIMEFRAME_WEEK = "now 7-d"
_TIMEFRAME_MONTH = "today 1-m"


def _make_pytrends() -> TrendReq:
    return TrendReq(hl="en-US", tz=300, timeout=(10, 25), retries=2, backoff_factor=0.5)


def _safe_rising(pytrends: TrendReq, keyword: str, timeframe: str, gprop: str = "") -> list[dict]:
    """Return rising related queries for a keyword. Returns [] on any failure."""
    try:
        pytrends.build_payload([keyword], timeframe=timeframe, geo="US", gprop=gprop)
        time.sleep(2)
        related = pytrends.related_queries()
        rising_df = related.get(keyword, {}).get("rising")
        if rising_df is None or rising_df.empty:
            return []
        return rising_df.head(10).to_dict("records")
    except Exception as e:
        logger.debug("pytrends rising query failed for '%s': %s", keyword, e)
        return []


class GoogleTrendsScraper:
    def get_trending(self) -> list[dict]:
        results = []
        pytrends = _make_pytrends()

        # 1. Rising shopping searches per category
        for category_name, seed_kw in _CATEGORY_SEEDS:
            # gprop='froogle' = Google Shopping
            rising = _safe_rising(pytrends, seed_kw, _TIMEFRAME_WEEK, gprop="froogle")
            for row in rising:
                query = str(row.get("query", "")).strip()
                value = row.get("value", 0)
                if not query:
                    continue
                results.append(
                    {
                        "name": query,
                        "trend_value": value,  # "Breakout" or % increase
                        "category": category_name,
                        "list_type": "google_shopping_rising",
                        "platform": "google_trends",
                        "timeframe": "7d",
                    }
                )
            time.sleep(1.5)

        # 2. Rising general consumer interest (past month, broader signal)
        for category_name, seed_kw in _CATEGORY_SEEDS[:4]:
            rising = _safe_rising(pytrends, seed_kw, _TIMEFRAME_MONTH)
            for row in rising:
                query = str(row.get("query", "")).strip()
                if not query:
                    continue
                results.append(
                    {
                        "name": query,
                        "trend_value": row.get("value", 0),
                        "category": category_name,
                        "list_type": "google_web_rising",
                        "platform": "google_trends",
                        "timeframe": "30d",
                    }
                )
            time.sleep(1.5)

        logger.info("Google Trends: %d rising queries collected", len(results))
        return results
