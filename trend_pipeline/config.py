import os
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

REPORT_OUTPUT_PATH = os.getenv("REPORT_OUTPUT_PATH", "../trend-data.json")

# (display_name, amazon_url_slug)
AMAZON_CATEGORIES = [
    ("Electronics", "electronics"),
    ("Home & Kitchen", "home-garden"),
    ("Toys & Games", "toys-and-games"),
    ("Beauty & Personal Care", "beauty"),
    ("Sports & Outdoors", "sporting-goods"),
    ("Pet Supplies", "pet-supplies"),
]

# Seconds to wait between HTTP requests to avoid rate-limiting
REQUEST_DELAY = 4

# Number of products to pull per Amazon list (bestsellers + movers & shakers)
AMAZON_PRODUCTS_PER_LIST = 20

# How many products to feed into Claude (keeps prompt size manageable)
MAX_PRODUCTS_FOR_ANALYSIS = 120
