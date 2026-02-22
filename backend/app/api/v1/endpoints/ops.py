from fastapi import APIRouter, Depends, HTTPException
from typing import List
from app.core.auth import get_current_user
from app.models.user import User
from app.models.task import Task, TaskStatus
from app.core.watcher import watcher

router = APIRouter()

@router.post("/trigger-nightly")
async def trigger_nightly(current_user: User = Depends(get_current_user)):
    """
    Manually trigger the nightly rollover logic.
    Useful for testing.
    """
    await watcher.perform_nightly_rollover()
    return {"status": "triggered"}

@router.post("/reset-bankruptcy")
async def reset_bankruptcy(current_user: User = Depends(get_current_user)):
    """
    The 'Declare Bankruptcy' Protocol.
    Moves ALL pending/todo tasks to 'backlog' (or deleted/archived) to give a fresh start.
    For this implementation, we will mark them as TaskStatus.PENDING with no date (Backlog),
    but maybe tag them as 'bankrupt_recovery' so we know.
    """
    # 1. Find all active tasks
    tasks = await Task.find(
        Task.user_id == current_user.clerk_id,
        Task.status != TaskStatus.DONE,
        Task.status != TaskStatus.PENDING # If already pending/backlog, leave it? Or maybe clear daily schedule.
    ).to_list()
    
    count = 0
    for task in tasks:
        task.status = TaskStatus.PENDING
        task.scheduled_date = None
        task.time_slot = None
        await task.save()
        count += 1
        
    return {"status": "bankruptcy_declared", "tasks_moved_to_backlog": count}
