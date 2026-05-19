import argparse
import time
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.cnmkv import CNmkvCrawler
from src.hdzu import HdzuCrawler
from src.deduplicator import Deduplicator
from src.excel_exporter import export_to_excel
from src.scheduler import start_scheduler
import config


def run_crawl():
    print("=" * 50)
    print("Movie Auto Downloader - Starting crawl...")
    print("=" * 50)

    all_movies = []
    dedup = Deduplicator()

    # Crawl cnmkv
    cnmkv = CNmkvCrawler()
    for cat_key in config.SITES["cnmkv"]["categories"]:
        movies = cnmkv.crawl_category(cat_key, limit=config.MOVIES_PER_CATEGORY)
        all_movies.extend(movies)
        time.sleep(2)

    # Crawl hdzu
    hdzu = HdzuCrawler()
    hdzu_movies = hdzu.crawl(limit=config.MOVIES_PER_CATEGORY * 3)
    all_movies.extend(hdzu_movies)

    # Deduplicate
    unique_movies = dedup.deduplicate(all_movies)

    # Export to Excel
    if unique_movies:
        export_to_excel(unique_movies)
    else:
        print("[Main] No movies found.")

    print("=" * 50)
    print(f"Crawl finished. Total: {len(unique_movies)} unique movies.")
    print("=" * 50)


def main():
    parser = argparse.ArgumentParser(description="Movie Auto Downloader")
    parser.add_argument("--run-now", action="store_true", help="Run crawl immediately")
    parser.add_argument("--schedule", action="store_true", help="Start scheduler")
    args = parser.parse_args()

    if args.run_now:
        run_crawl()
    elif args.schedule:
        run_crawl()
        scheduler = start_scheduler(run_crawl)
        print("[Main] Scheduler is running. Press Ctrl+C to exit.")
        try:
            while True:
                time.sleep(60)
        except KeyboardInterrupt:
            scheduler.shutdown()
            print("[Main] Scheduler stopped.")
    else:
        print("Usage:")
        print("  python main.py --run-now    # Run once immediately")
        print("  python main.py --schedule   # Start daily scheduler")


if __name__ == "__main__":
    main()
