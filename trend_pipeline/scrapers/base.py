import time
import random
import logging
import requests
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)

_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Safari/605.1.15",
]

BASE_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}


class BaseScraper(ABC):
    def __init__(self, delay: float = 4.0):
        self.delay = delay
        self.session = requests.Session()
        self.session.headers.update(BASE_HEADERS)
        self._rotate_ua()

    def _rotate_ua(self):
        self.session.headers["User-Agent"] = random.choice(_USER_AGENTS)

    def _get(self, url: str, **kwargs) -> requests.Response:
        self._rotate_ua()
        jitter = random.uniform(0.5, 2.0)
        time.sleep(self.delay + jitter)
        try:
            resp = self.session.get(url, timeout=30, **kwargs)
            resp.raise_for_status()
            return resp
        except requests.HTTPError as e:
            logger.warning("HTTP %s for %s", e.response.status_code, url)
            raise
        except requests.RequestException as e:
            logger.warning("Request failed for %s: %s", url, e)
            raise

    @abstractmethod
    def get_trending(self) -> list[dict]:
        """Return a list of product/trend dicts."""
