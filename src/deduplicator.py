import sqlite3
from typing import List, Dict
import config


class Deduplicator:
    def __init__(self):
        self.db_path = config.DB_PATH
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS movies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    year TEXT,
                    genre TEXT,
                    link TEXT NOT NULL,
                    size TEXT,
                    size_bytes REAL,
                    source TEXT,
                    link_type TEXT,
                    description TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(name, year)
                )
            """)
            # Migrate: add description column if missing
            try:
                conn.execute("SELECT description FROM movies LIMIT 1")
            except sqlite3.OperationalError:
                conn.execute("ALTER TABLE movies ADD COLUMN description TEXT")

            conn.execute("""
                CREATE TABLE IF NOT EXISTS crawl_state (
                    site TEXT NOT NULL,
                    category TEXT NOT NULL,
                    last_page INTEGER DEFAULT 0,
                    last_movie_id TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (site, category)
                )
            """)
            conn.commit()

    def deduplicate(self, movies: List[Dict]) -> List[Dict]:
        result = []
        for movie in movies:
            existing = self._find(movie["name"], movie.get("year", ""))
            if existing:
                # If existing is not quark but new is quark, update
                if existing["link_type"] != "夸克网盘" and movie["link_type"] == "夸克网盘":
                    self._update(movie)
                    result.append(movie)
                # Otherwise skip (keep existing)
            else:
                self._insert(movie)
                result.append(movie)
        return result

    def _find(self, name: str, year: str) -> Dict:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.execute(
                "SELECT * FROM movies WHERE name=? AND year=?",
                (name, year)
            )
            row = cur.fetchone()
            if row:
                return dict(row)
            return {}

    def _insert(self, movie: Dict):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT INTO movies (name, year, genre, link, size, size_bytes, source, link_type, description)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (movie["name"], movie.get("year", ""), movie.get("genre", ""),
                 movie["link"], movie.get("size", ""), movie.get("size_bytes", 0),
                 movie["source"], movie["link_type"], movie.get("description", ""))
            )
            conn.commit()

    def _update(self, movie: Dict):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """UPDATE movies SET link=?, size=?, size_bytes=?, source=?, link_type=?, description=?
                   WHERE name=? AND year=?""",
                (movie["link"], movie.get("size", ""), movie.get("size_bytes", 0),
                 movie["source"], movie["link_type"], movie.get("description", ""),
                 movie["name"], movie.get("year", ""))
            )
            conn.commit()

    def check_exists(self, name: str, year: str) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute("SELECT 1 FROM movies WHERE name=? AND year=?", (name, year))
            return cur.fetchone() is not None

    def get_crawl_state(self, site: str, category: str) -> Dict:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.execute(
                "SELECT * FROM crawl_state WHERE site=? AND category=?",
                (site, category)
            )
            row = cur.fetchone()
            return dict(row) if row else {"last_page": 0, "last_movie_id": ""}

    def set_crawl_state(self, site: str, category: str, last_page: int, last_movie_id: str = ""):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT INTO crawl_state (site, category, last_page, last_movie_id, updated_at)
                   VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                   ON CONFLICT(site, category) DO UPDATE SET
                   last_page=excluded.last_page,
                   last_movie_id=excluded.last_movie_id,
                   updated_at=CURRENT_TIMESTAMP""",
                (site, category, last_page, last_movie_id)
            )
            conn.commit()

    def get_all(self) -> List[Dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.execute("SELECT * FROM movies ORDER BY created_at DESC")
            return [dict(row) for row in cur.fetchall()]
