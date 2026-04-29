"""
Claude-powered product trend analysis.

Takes raw product/trend data from all scrapers and produces structured
actionable recommendations for the dropshipper:
  - buy_now:           products to source immediately (high confidence)
  - buy_soon:          products predicted to trend in 2-6 weeks
  - categories_to_watch: broader category momentum
  - market_insights:   narrative summary of what's happening
  - avoid:             oversaturated or declining products to skip
"""

import json
import logging
from datetime import date

import anthropic
from config import ANTHROPIC_API_KEY, MAX_PRODUCTS_FOR_ANALYSIS

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """You are an expert e-commerce product trend analyst specializing in dropshipping.
You have deep knowledge of product life cycles, seasonal demand, platform dynamics (Amazon, TikTok),
and what makes a product ideal for a dropshipper to resell at margin.

You will receive raw trend data scraped from Amazon, TikTok, and Google Trends.
Your job: turn that raw data into specific, profitable, actionable guidance.

Key principles for dropshipping product selection:
- Sweet spot: proven demand (reviews/views exist) but not yet saturated (big brands haven't dominated)
- "Movers & Shakers" on Amazon = rank rising fast = early signal, act quickly
- Products trending on BOTH Amazon AND TikTok = extremely strong buy signal
- Google Shopping rising queries = active purchase intent, not just curiosity
- Avoid: heavily branded items (can't dropship), oversized/heavy products (shipping cost kills margin),
  ultra-low-ticket items under $10 (no margin), anything requiring FDA clearance
- Ideal price point for dropshipping: $20–$150 retail

Output ONLY valid JSON, no markdown, no explanation outside the JSON."""

_USER_PROMPT_TEMPLATE = """Today's date: {today}

Below is raw trend data from multiple platforms. Analyze it and return your recommendations as JSON.

=== RAW TREND DATA ===
{data_json}
=== END DATA ===

Return a single JSON object with this exact structure:
{{
  "buy_now": [
    {{
      "product": "specific product name or type",
      "category": "category name",
      "platforms": ["amazon", "tiktok"],
      "confidence": "high|medium",
      "reason": "2-3 sentence explanation of why to buy NOW",
      "price_range": "$X–$Y suggested retail",
      "margin_estimate": "low|medium|high",
      "urgency": "Act within X days/weeks",
      "search_terms": ["term1", "term2"]
    }}
  ],
  "buy_soon": [
    {{
      "product": "specific product name or type",
      "category": "category name",
      "platforms": ["platform"],
      "confidence": "medium|low",
      "reason": "why this will trend soon",
      "predicted_peak": "timeframe e.g. 2-4 weeks",
      "watch_signal": "what to monitor to confirm the trend"
    }}
  ],
  "categories_to_watch": [
    {{
      "category": "category name",
      "momentum": "rising|exploding|stable",
      "reason": "brief reason"
    }}
  ],
  "avoid": [
    {{
      "product_type": "what to avoid",
      "reason": "why"
    }}
  ],
  "market_insights": "2-3 paragraph narrative about the current market moment and what it means for the dropshipper",
  "data_quality_note": "brief note on which platforms provided strong data vs weak/blocked"
}}

Rules:
- buy_now: 5 to 8 items, sorted by confidence then urgency
- buy_soon: 3 to 5 items
- categories_to_watch: 3 to 5 items
- avoid: 2 to 4 items
- Be SPECIFIC with product names, not generic ("LED strip lights" not "lighting products")
- If data from a platform was sparse or missing, note it in data_quality_note and still provide recommendations from available data"""


class ClaudeAnalyzer:
    def __init__(self):
        self.client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    def _build_data_summary(self, products: list[dict]) -> str:
        # Trim to fit context; prioritize movers_shakers and multi-platform
        movers = [p for p in products if p.get("list_type") == "movers_shakers"]
        tiktok = [p for p in products if p.get("platform") == "tiktok"]
        google = [p for p in products if p.get("platform") == "google_trends"]
        amazon_bs = [p for p in products if p.get("list_type") == "bestseller"]

        # Build a compact but information-dense representation
        sections = []

        if movers:
            sections.append("## Amazon Movers & Shakers (rank rising fastest — STRONG signal)")
            for p in movers[:30]:
                line = f"  - [{p.get('category','')}] {p['name']}"
                if p.get("rank"):
                    line += f" (rank #{p['rank']})"
                if p.get("rating"):
                    line += f" | {p['rating']}★"
                if p.get("price"):
                    line += f" | {p['price']}"
                sections.append(line)

        if tiktok:
            sections.append("\n## TikTok Trending Hashtags & Products")
            for p in tiktok[:25]:
                line = f"  - [{p.get('category','')}] {p['name']}"
                if p.get("view_count"):
                    views = int(p["view_count"])
                    line += f" | {views:,} views" if views < 1_000_000 else f" | {views/1_000_000:.1f}M views"
                sections.append(line)

        if google:
            sections.append("\n## Google Trends Rising Shopping Queries (active purchase intent)")
            for p in google[:30]:
                val = p.get("trend_value", "")
                val_str = "Breakout" if str(val) == "0" else f"+{val}%"
                sections.append(f"  - [{p.get('category','')}] '{p['name']}' — {val_str} ({p.get('timeframe','7d')})")

        if amazon_bs:
            sections.append("\n## Amazon Bestsellers (proven demand)")
            for p in amazon_bs[:30]:
                line = f"  - [{p.get('category','')}] {p['name']}"
                if p.get("rank"):
                    line += f" (#{p['rank']})"
                sections.append(line)

        return "\n".join(sections)

    def analyze(self, products: list[dict]) -> dict:
        if not products:
            logger.warning("No product data available for analysis")
            return _empty_analysis("No data was collected from any platform.")

        summary = self._build_data_summary(products)
        logger.info("Sending %d chars of trend data to Claude", len(summary))

        prompt = _USER_PROMPT_TEMPLATE.format(
            today=date.today().isoformat(),
            data_json=summary,
        )

        try:
            message = self.client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=4096,
                system=_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = message.content[0].text.strip()
            # Strip markdown code fences if Claude added them despite instructions
            if raw.startswith("```"):
                raw = raw.split("```", 2)[1]
                if raw.startswith("json"):
                    raw = raw[4:]
                raw = raw.rsplit("```", 1)[0]
            analysis = json.loads(raw)
            logger.info("Claude analysis complete. buy_now: %d, buy_soon: %d",
                        len(analysis.get("buy_now", [])),
                        len(analysis.get("buy_soon", [])))
            return analysis
        except json.JSONDecodeError as e:
            logger.error("Claude returned invalid JSON: %s", e)
            return _empty_analysis(f"JSON parse error: {e}")
        except anthropic.APIError as e:
            logger.error("Anthropic API error: %s", e)
            return _empty_analysis(f"API error: {e}")


def _empty_analysis(reason: str) -> dict:
    return {
        "buy_now": [],
        "buy_soon": [],
        "categories_to_watch": [],
        "avoid": [],
        "market_insights": f"Analysis unavailable: {reason}",
        "data_quality_note": reason,
    }
