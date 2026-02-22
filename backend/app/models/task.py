from beanie import Document, Indexed
from pydantic import Field
from datetime import datetime, date
from typing import Optional, List
from enum import Enum

class TaskStatus(str, Enum):
    TODO = "todo"
    IN_PROGRESS = "doing" # Changed from in_progress to match frontend 'doing'
    DONE = "done"
    # Backlog is usually handled by not having a date, or explicit status if needed
    PENDING = "pending" # For daily tasks not yet started

class TaskPriority(str, Enum):
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"

class Task(Document):
    user_id: Indexed(str)
    
    title: str
    description: Optional[str] = None
    
    # Links
    project_id: Optional[Indexed(str)] = None # Link to Project
    milestone_id: Optional[str] = None # Link to Milestone within Project
    life_domain_id: Optional[str] = None # Fallback/Quick link
    
    # Scheduling
    status: TaskStatus = TaskStatus.TODO
    priority: TaskPriority = TaskPriority.MEDIUM
    
    planning_horizon: str = "Daily Focus" # "Daily Focus", "Weekly", "Backlog"
    
    scheduled_date: Optional[date] = None # For Daily View
    time_slot: Optional[str] = None # HH:MM AM - HH:MM PM
    
    # Resources
    estimated_minutes: int = 30
    actual_duration: Optional[int] = None
    cash_budget: float = 0.0
    
    # Metadata
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    class Settings:
        name = "tasks"
        indexes = [
            "scheduled_date",
            "project_id",
            "status"
        ]
