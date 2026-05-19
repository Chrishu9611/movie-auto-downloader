from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import config


def start_scheduler(crawl_func):
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        crawl_func,
        trigger=CronTrigger(hour=config.SCHEDULE_HOUR, minute=config.SCHEDULE_MINUTE),
        id="daily_crawl",
        name="Daily Movie Crawl",
        replace_existing=True,
    )
    scheduler.start()
    print(f"[Scheduler] Daily crawl scheduled at {config.SCHEDULE_HOUR:02d}:{config.SCHEDULE_MINUTE:02d}")
    return scheduler
