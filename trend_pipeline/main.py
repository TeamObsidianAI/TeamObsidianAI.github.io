#!/usr/bin/env python3
"""
Product Trend Pipeline — main entry point.

Usage:
    python main.py                 # Full run: all scrapers + Claude analysis
    python main.py --skip-amazon   # Skip Amazon (faster for testing)
    python main.py --skip-tiktok   # Skip TikTok
    python main.py --skip-google   # Skip Google Trends
    python main.py --dry-run       # Scrape but skip Claude (no API cost)

Output: ../trend-data.json (readable by the trend-report.html dashboard)
"""

import argparse
import logging
import re
import sys
import os
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout

# Allow sibling imports when running main.py directly
sys.path.insert(0, os.path.dirname(__file__))

from config import ANTHROPIC_API_KEY, AMAZON_CATEGORIES
from scrapers.amazon import AmazonScraper
from scrapers.tiktok import TikTokScraper
from scrapers.google_trends import GoogleTrendsScraper
from analyzers.claude_analyzer import ClaudeAnalyzer
from reporters.generator import write_report

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("pipeline")


def _inject_images(analysis: dict, scraped: list[dict]) -> None:
    """Match Claude recommendations to scraped Amazon products and attach image_url."""
    img_map = {
        re.sub(r'[^\w\s]', ' ', p['name'].lower()): p['image_url']
        for p in scraped
        if p.get('image_url') and p.get('name')
    }
    if not img_map:
        return

    def best_url(product_name: str) -> str | None:
        words = set(re.sub(r'[^\w]', ' ', product_name.lower()).split())
        best, score = None, 1
        for name, url in img_map.items():
            s = len(words & set(name.split()))
            if s > score:
                score, best = s, url
        return best

    for section in ('buy_now', 'rising_fast', 'buy_soon'):
        for item in analysis.get(section, []):
            if not item.get('image_url'):
                url = best_url(item.get('product', ''))
                if url:
                    item['image_url'] = url


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Product Trend Pipeline")
    p.add_argument("--skip-amazon", action="store_true")
    p.add_argument("--skip-tiktok", action="store_true")
    p.add_argument("--skip-google", action="store_true")
    p.add_argument("--dry-run", action="store_true", help="Scrape only, skip Claude analysis")
    return p.parse_args()


def main() -> None:
    args = parse_args()

    if not args.dry_run and not ANTHROPIC_API_KEY:
        logger.error("ANTHROPIC_API_KEY is not set. Copy .env.example → .env and add your key.")
        sys.exit(1)

    all_products: list[dict] = []

    # ── 1. Scrape ────────────────────────────────────────────────────────────

    if not args.skip_amazon:
        logger.info("=== Amazon ===")
        try:
            amazon_products = AmazonScraper(AMAZON_CATEGORIES).get_trending()
            all_products.extend(amazon_products)
            logger.info("Amazon: collected %d products", len(amazon_products))
        except Exception as e:
            logger.error("Amazon scraper crashed: %s", e)

    if not args.skip_tiktok:
        logger.info("=== TikTok ===")
        try:
            tiktok_items = TikTokScraper().get_trending()
            all_products.extend(tiktok_items)
            logger.info("TikTok: collected %d items", len(tiktok_items))
        except Exception as e:
            logger.error("TikTok scraper crashed: %s", e)

    if not args.skip_google:
        logger.info("=== Google Trends ===")
        try:
            with ThreadPoolExecutor(max_workers=1) as ex:
                future = ex.submit(GoogleTrendsScraper().get_trending)
                try:
                    google_items = future.result(timeout=30)
                    all_products.extend(google_items)
                    logger.info("Google Trends: collected %d items", len(google_items))
                except FuturesTimeout:
                    logger.warning("Google Trends timed out after 30s — skipping")
        except Exception as e:
            logger.error("Google Trends scraper crashed: %s", e)

    logger.info("Total data points collected: %d", len(all_products))

    if not all_products:
        logger.warning(
            "No data collected from scrapers (platforms are blocking this IP — "
            "run via run.bat on your Windows machine for live data). "
            "Falling back to Claude general-knowledge analysis."
        )

    # ── 2. Analyze ───────────────────────────────────────────────────────────

    if args.dry_run:
        logger.info("Dry run — skipping Claude analysis")
        analysis = {
            "buy_now": [],
            "buy_soon": [],
            "categories_to_watch": [],
            "avoid": [],
            "market_insights": "Dry run — no analysis performed.",
            "data_quality_note": "Dry run mode.",
        }
    else:
        logger.info("=== Claude Analysis ===")
        analysis = ClaudeAnalyzer().analyze(all_products)

    # ── 3. Write report ──────────────────────────────────────────────────────

    _inject_images(analysis, all_products)
    output_path = write_report(all_products, analysis)
    logger.info("Done! Report saved to: %s", output_path)
    logger.info("Open trend-report.html in your browser to view the dashboard.")


if __name__ == "__main__":
    main()
