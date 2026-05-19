import re
from typing import List, Dict, Optional
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from src.crawler import BaseCrawler
import config


class CNmkvCrawler(BaseCrawler):
    def __init__(self):
        super().__init__("cnmkv", config.SITES["cnmkv"]["base_url"])

    def crawl_category(self, cat_key: str, limit: int = 10) -> List[Dict]:
        cat_info = config.SITES["cnmkv"]["categories"][cat_key]
        url = urljoin(self.base_url + "/", cat_info["path"].lstrip("/"))
        print(f"[{self.name}] Crawling category: {cat_info['name']} -> {url}")

        soup = self.get_soup(url)
        if not soup:
            return []

        movies = []
        entries = soup.find_all("article", class_="entry") or soup.find_all("div", class_="entry")
        if not entries:
            entries = soup.select(".post,.item,.entry")

        for entry in entries[:limit]:
            movie = self._parse_entry(entry)
            if movie:
                movies.append(movie)

        return movies

    def _parse_entry(self, entry: BeautifulSoup) -> Optional[Dict]:
        title_tag = entry.find("h2", class_="entry-title")
        if not title_tag:
            title_tag = entry.find("h2")
        if not title_tag:
            return None

        a_tag = title_tag.find("a")
        if not a_tag:
            return None

        detail_url = a_tag.get("href", "")
        title_text = a_tag.get_text(strip=True)

        year, region, genre, name = self._parse_title(title_text)
        if not name:
            return None

        links = self._crawl_detail(detail_url)
        if not links:
            return None

        best_link = self._select_best_link(links)

        return {
            "name": name,
            "year": year,
            "genre": genre,
            "link": best_link["url"],
            "size": best_link.get("size", ""),
            "size_bytes": best_link.get("size_bytes", 0),
            "source": self.name,
            "link_type": best_link.get("type", "未知"),
        }

    def _parse_title(self, title: str):
        pattern = r"(\d{4})([^《]*)片《([^》]+)》"
        m = re.search(pattern, title)
        if m:
            year = m.group(1)
            region_type = m.group(2).strip()
            name = m.group(3).strip()

            region = ""
            genre = ""
            if "国" in region_type or "产" in region_type:
                region = "国产"
            elif "欧美" in region_type:
                region = "欧美"
            elif "日韩" in region_type or "韩" in region_type or "日" in region_type:
                region = "日韩"

            for g in ["剧情", "喜剧", "动作", "科幻", "恐怖", "悬疑", "爱情", "动画", "犯罪", "惊悚", "战争", "奇幻"]:
                if g in region_type:
                    genre = g
                    break

            if not genre:
                genre = region_type.replace(region, "").strip()

            return year, region, genre, name

        return "", "", "", title.replace("高清下载", "").strip()

    def _crawl_detail(self, url: str) -> List[Dict]:
        soup = self.get_soup(url)
        if not soup:
            return []

        content = soup.find("div", class_="entry-content")
        if not content:
            content = soup.find("article") or soup

        links = []
        for a in content.find_all("a", href=True):
            href = a["href"]
            text = a.get_text(strip=True)

            if "pan.quark.cn" in href or "quark" in href:
                links.append({"url": href, "type": "夸克网盘", "size": "", "size_bytes": 0})
            elif "pan.baidu.com" in href:
                links.append({"url": href, "type": "百度网盘", "size": "", "size_bytes": 0})
            elif "pan.xunlei.com" in href:
                links.append({"url": href, "type": "迅雷网盘", "size": "", "size_bytes": 0})

        return links

    def _select_best_link(self, links: List[Dict]) -> Dict:
        priority = {"夸克网盘": 0, "百度网盘": 1, "迅雷网盘": 2}
        links.sort(key=lambda x: priority.get(x["type"], 99))
        return links[0] if links else {}
