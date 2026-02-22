from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
from datetime import date
from app.models.task import Task, TaskStatus, TaskPriority
from app.core.auth import get_current_user
from app.models.user import User
from pydantic import BaseModel

router = APIRouter()

class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = None
    project_id: Optional[str] = None
    scheduled_date: Optional[date] = None
    time_slot: Optional[str] = None
    status: TaskStatus = TaskStatus.TODO
    priority: TaskPriority = TaskPriority.MEDIUM
    cash_budget: float = 0.0
    planning_horizon: str = "Daily Focus"

@router.get("/", response_model=List[Task])
async def list_tasks(
    scheduled_date: Optional[date] = None,
    project_id: Optional[str] = None,
    milestone_id: Optional[str] = None,
    current_user: User = Depends(get_current_user)
):
    query = Task.find(Task.user_id == current_user.clerk_id)
    
    if scheduled_date:
        query = query.find(Task.scheduled_date == scheduled_date)
    if project_id:
        query = query.find(Task.project_id == project_id)
    if milestone_id:
        query = query.find(Task.milestone_id == milestone_id)
    
    tasks = await query.to_list()
    return tasks

@router.post("/", response_model=Task)
async def create_task(payload: TaskCreate, current_user: User = Depends(get_current_user)):
    task = Task(
        user_id=current_user.clerk_id,
        **payload.dict()
    )
    await task.insert()
    return task

@router.put("/{task_id}", response_model=Task)
async def update_task(task_id: str, payload: dict, current_user: User = Depends(get_current_user)):
    task = await Task.find_one(Task.id == task_id, Task.user_id == current_user.clerk_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    for k, v in payload.items():
        if hasattr(task, k) and k != "id" and k != "user_id":
            setattr(task, k, v)
    
    await task.save()
    return task

@router.delete("/{task_id}")
async def delete_task(task_id: str, current_user: User = Depends(get_current_user)):
    task = await Task.find_one(Task.id == task_id, Task.user_id == current_user.clerk_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    await task.delete()
    return {"status": "deleted"}
