import requests
from bs4 import BeautifulSoup
import time
from typing import Optional
import config


class BaseCrawler:
    def __init__(self, name: str, base_url: str):
        self.name = name
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update(config.HEADERS)

    def get_soup(self, url: str, retries: int = 3) -> Optional[BeautifulSoup]:
        for i in range(retries):
            try:
                resp = self.session.get(url, timeout=15)
                resp.raise_for_status()
                resp.encoding = "utf-8"
                return BeautifulSoup(resp.text, "lxml")
            except Exception as e:
                print(f"[{self.name}] Request failed ({i+1}/{retries}): {url} - {e}")
                time.sleep(2)
        return None

    def parse_size(self, size_str: str) -> float:
        size_str = size_str.upper().replace(",", "")
        units = {"B": 1, "KB": 1024, "MB": 1024**2, "GB": 1024**3, "TB": 1024**4}
        for unit, factor in units.items():
            if unit in size_str:
                try:
                    num = float(size_str.replace(unit, "").strip())
                    return num * factor
                except ValueError:
                    return 0.0
        return 0.0
