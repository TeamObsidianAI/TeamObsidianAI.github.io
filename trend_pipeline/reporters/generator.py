"""
Writes the final trend-data.json that the dashboard reads.

The JSON structure:
{
  "generated_at": "ISO timestamp",
  "stats": { platform counts },
  "analysis": { Claude's structured output },
  "raw_sample": [ first 50 products for debugging ]
}
"""

import json
import logging
import os
from datetime import datetime, timezone

from config import REPORT_OUTPUT_PATH

logger = logging.getLogger(__name__)


def write_report(products: list[dict], analysis: dict) -> str:
    platform_counts: dict[str, int] = {}
    for p in products:
        platform = p.get("platform", "unknown")
        platform_counts[platform] = platform_counts.get(platform, 0) + 1

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "stats": {
            "total_products_scraped": len(products),
            "by_platform": platform_counts,
        },
        "analysis": analysis,
        "raw_sample": products[:50],
    }

    output_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", REPORT_OUTPUT_PATH)
    )
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    logger.info("Report written to %s", output_path)
    return output_path
