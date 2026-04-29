import logging
from bs4 import BeautifulSoup
from .base import BaseScraper
from config import AMAZON_CATEGORIES, AMAZON_PRODUCTS_PER_LIST, REQUEST_DELAY

logger = logging.getLogger(__name__)

_BESTSELLERS_URL = "https://www.amazon.com/gp/bestsellers/{slug}/"
_MOVERS_URL = "https://www.amazon.com/gp/movers-and-shakers/{slug}/"

# Amazon updates their CSS class names often; we try multiple selectors in order.
_NAME_SELECTORS = [
    "._cDEzb_p13n-sc-css-line-clamp-3_g3dy1",
    ".p13n-sc-truncate-desktop-type2",
    ".p13n-sc-truncate",
    "div[class*='line-clamp'] span",
    ".a-link-normal span.a-text-normal",
]
_RANK_SELECTORS = [".zg-bdg-text", "span[class*='badge']"]
_PRICE_SELECTORS = ["span.p13n-sc-price", "span._cDEzb_p13n-sc-price_3mJ9Z", ".a-price .a-offscreen"]
_RATING_SELECTORS = ["span.a-icon-alt"]
_REVIEWS_SELECTORS = ["span.a-size-small.a-link-normal", "span[class*='review']"]


def _first_text(element, selectors: list[str]) -> str | None:
    for sel in selectors:
        el = element.select_one(sel)
        if el:
            return el.get_text(strip=True)
    return None


def _parse_page(html: str, category: str, list_type: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    products = []

    # Grid items on bestseller / movers pages
    items = (
        soup.select("li.zg-item-immersion")
        or soup.select("div.zg-item-immersion")
        or soup.select("#gridItemRoot > div")
        or soup.select("li[data-p13n-asin-metadata]")
    )

    for item in items[:AMAZON_PRODUCTS_PER_LIST]:
        name = _first_text(item, _NAME_SELECTORS)
        if not name or len(name) < 4:
            continue

        rank_raw = _first_text(item, _RANK_SELECTORS)
        try:
            rank = int("".join(filter(str.isdigit, rank_raw))) if rank_raw else None
        except ValueError:
            rank = None

        rating_raw = _first_text(item, _RATING_SELECTORS)
        rating = rating_raw.split(" ")[0] if rating_raw else None

        products.append(
            {
                "name": name,
                "rank": rank,
                "rating": rating,
                "price": _first_text(item, _PRICE_SELECTORS),
                "review_count": _first_text(item, _REVIEWS_SELECTORS),
                "category": category,
                "list_type": list_type,
                "platform": "amazon",
            }
        )

    return products


class AmazonScraper(BaseScraper):
    def __init__(self, categories: list[tuple] = AMAZON_CATEGORIES, delay: float = REQUEST_DELAY):
        super().__init__(delay)
        self.categories = categories

    def _fetch_list(self, url: str, category: str, list_type: str) -> list[dict]:
        try:
            resp = self._get(url)
            products = _parse_page(resp.text, category, list_type)
            logger.info("Amazon %s (%s): %d products", list_type, category, len(products))
            return products
        except Exception as e:
            logger.warning("Amazon %s (%s) failed: %s", list_type, category, e)
            return []

    def get_trending(self) -> list[dict]:
        results = []
        for display_name, slug in self.categories:
            results.extend(self._fetch_list(_BESTSELLERS_URL.format(slug=slug), display_name, "bestseller"))
            results.extend(self._fetch_list(_MOVERS_URL.format(slug=slug), display_name, "movers_shakers"))
        logger.info("Amazon total: %d products collected", len(results))
        return results
