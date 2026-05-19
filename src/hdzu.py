import re
from typing import List, Dict, Optional
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from bs4.element import NavigableString
from src.crawler import BaseCrawler
import config


class HdzuCrawler(BaseCrawler):
    def __init__(self):
        super().__init__("hdzu", config.SITES["hdzu"]["base_url"])

    def crawl(self, limit: int = None, dedup=None) -> List[Dict]:
        print(f"[{self.name}] Crawling with pagination")

        movies = []
        page = 1
        stop = False

        while not stop:
            url = self.base_url + "/"
            if page > 1:
                url = f"{self.base_url}/?page={page}"

            soup = self.get_soup(url)
            if not soup:
                break

            entries = soup.find_all("li", class_="movie-item")
            if not entries:
                entries = soup.select("li.topic-item.media.movie-item")

            if not entries:
                break

            for entry in entries:
                if limit and len(movies) >= limit:
                    stop = True
                    break

                movie = self._parse_entry(entry, dedup)
                if movie:
                    movies.append(movie)

            if len(entries) < 10:
                break

            page += 1

        return movies

    def _parse_entry(self, entry: BeautifulSoup, dedup=None) -> Optional[Dict]:
        title_tag = entry.find("h2", class_="topic-title")
        if not title_tag:
            return None

        a_tag = title_tag.find("a")
        if not a_tag:
            return None

        detail_url = a_tag.get("href", "")
        if detail_url.startswith("/"):
            detail_url = urljoin(self.base_url + "/", detail_url.lstrip("/"))

        name = a_tag.get_text(strip=True)

        # Extract cover from entry
        cover_url = ""
        img_tag = entry.find("img", class_="list-pic")
        if img_tag and img_tag.get("src"):
            cover_url = urljoin(self.base_url + "/", img_tag["src"].lstrip("/"))

        info = self._crawl_detail(detail_url)
        if not info or not info.get("links"):
            return None

        # Incremental check
        if dedup and dedup.check_exists(name, info.get("year", "")):
            return None

        best_link = self._select_best_link(info["links"])

        return {
            "name": name,
            "year": info.get("year", ""),
            "genre": info.get("genre", ""),
            "link": best_link["url"],
            "size": best_link.get("size", ""),
            "size_bytes": best_link.get("size_bytes", 0),
            "source": self.name,
            "link_type": best_link.get("type", "未知"),
            "description": info.get("description", ""),
            "cover_url": cover_url,
        }

    def _crawl_detail(self, url: str) -> Dict:
        soup = self.get_soup(url)
        if not soup:
            return {}

        info = {"year": "", "genre": "", "links": [], "description": ""}

        # Parse year, region, genre from movie info section
        movie_info = soup.find("div", class_="movie-info")
        if movie_info:
            for p in movie_info.find_all("p"):
                text = p.get_text(strip=True)
                if "◎年　　代" in text or "◎年代" in text:
                    m = re.search(r"(\d{4})", text)
                    if m:
                        info["year"] = m.group(1)
                elif "◎类　　别" in text or "◎类别" in text:
                    parts = text.replace("◎类　　别", "").replace("◎类别", "").strip().split("/")
                    info["genre"] = parts[0].strip() if parts else ""

        # Parse description
        # hdzu puts synopsis in a p tag inside panel-body div, usually the longest paragraph
        panel_body = soup.find("div", class_="panel-body")
        if panel_body:
            longest_text = ""
            for p in panel_body.find_all("p"):
                text = p.get_text(strip=True)
                # Skip short paragraphs and metadata paragraphs with ◎ markers
                if len(text) > len(longest_text) and len(text) > 50 and "◎" not in text[:10]:
                    longest_text = text
            if longest_text:
                info["description"] = longest_text[:500]

        # Fallback: p.content-des
        if not info["description"]:
            content_des = soup.find("p", class_="content-des")
            if content_des:
                info["description"] = content_des.get_text(strip=True)[:500]

        # Parse download links
        movie_url_div = soup.find("div", class_="movie-url")
        if movie_url_div:
            table = movie_url_div.find("table")
            if table:
                for row in table.find_all("tr"):
                    a_tag = row.find("a", href=True, class_="open-url")
                    if a_tag and "magnet:?" in a_tag.get("href", ""):
                        href = a_tag["href"]
                        title = a_tag.get("title", "")
                        text = a_tag.get_text(strip=True)

                        size_str = ""
                        size_bytes = 0
                        size_match = re.search(r"\[([^\]]+)\]", text)
                        if size_match:
                            size_str = size_match.group(1)
                            size_bytes = self.parse_size(size_str)

                        info["links"].append({
                            "url": href,
                            "type": "磁力链接",
                            "size": size_str,
                            "size_bytes": size_bytes,
                            "title": title,
                        })

        return info

    def _select_best_link(self, links: List[Dict]) -> Dict:
        valid_links = [l for l in links if l.get("size_bytes", 0) > 0]
        if valid_links:
            valid_links.sort(key=lambda x: x["size_bytes"])
            return valid_links[0]
        return links[0] if links else {}
