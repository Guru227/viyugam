from beanie import Document, Indexed
from pydantic import Field, BaseModel
from typing import List, Optional
from datetime import date
from enum import Enum

class ProjectStatus(str, Enum):
    BACKLOG = 'backlog'
    ACTIVE = 'active'
    COMPLETED = 'completed'
    PAUSED = 'paused'

class MilestoneStatus(str, Enum):
    PENDING = 'pending'
    IN_PROGRESS = 'in-progress'
    COMPLETED = 'completed'

class Milestone(BaseModel):
    id: str # Client-side ID mainly, or we can generate one
    title: str
    status: MilestoneStatus = MilestoneStatus.PENDING
    due_date: Optional[date] = None
    cost_estimate: float = 0
    time_estimate_hours: float = 0

class Project(Document):
    user_id: Indexed(str)
    
    title: str
    domain_id: Indexed(str) # Links to LifeDomain.id
    description: Optional[str] = None
    
    status: ProjectStatus = ProjectStatus.BACKLOG
    
    # Lenses (Impact/Effort 1-10)
    impact: int = Field(default=5, ge=1, le=10)
    effort: int = Field(default=5, ge=1, le=10)
    budget: float = 0
    
    deadline: Optional[date] = None
    
    milestones: List[Milestone] = []

    class Settings:
        name = "projects"
        indexes = [
            "domain_id",
        ]
