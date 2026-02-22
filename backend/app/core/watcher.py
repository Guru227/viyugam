import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime, date, timedelta
from app.models.task import Task, TaskStatus
from app.models.user import User

logger = logging.getLogger(__name__)

class NightlyWatcher:
    """
    Guardian of the system's resilience.
    Runs every night to:
    1. Rollover unfinished daily tasks.
    2. Reset daily metrics.
    """
    
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        
    def start(self):
        # Run at 00:00 every day
        self.scheduler.add_job(
            self.perform_nightly_rollover, 
            CronTrigger(hour=0, minute=0),
            id="nightly_rollover",
            replace_existing=True
        )
        self.scheduler.start()
        logger.info("NightlyWatcher started.")

    async def perform_nightly_rollover(self):
        logger.info("Starting nightly rollover...")
        today = datetime.now().date()
        yesterday = today - timedelta(days=1)
        
        # 1. Find tasks scheduled for yesterday that are NOT done
        # Using $lt today to catch anything from the past
        tasks_to_rollover = await Task.find(
            Task.scheduled_date < today,
            Task.status != TaskStatus.DONE
        ).to_list()
        
        count = 0
        for task in tasks_to_rollover:
            # If it's a daily task that was missed, we have two choices:
            # A) Move to today (Textbook "Snowball")
            # B) Move to Pending/Backlog (Textbook "Fresh Start")
            
            # Implementation: Move to 'PENDING' status and remove scheduled_date (Backlog)
            # This forces the user to intentionally re-schedule it, preventing accumulation clutter.
            
            task.status = TaskStatus.PENDING
            task.scheduled_date = None
            task.time_slot = None
            await task.save()
            count += 1
            
        logger.info(f"Rolled over {count} tasks to backlog.")
        
    async def check_bankruptcy(self, user_id: str) -> bool:
        """
        Returns True if the user is in a state of 'Task Bankruptcy' (>50 backlog items).
        """
        backlog_count = await Task.find(
            Task.user_id == user_id,
            Task.status == TaskStatus.PENDING # Encapsulates Todo/Pending without a date
        ).count()
        
        return backlog_count > 50

watcher = NightlyWatcher()
