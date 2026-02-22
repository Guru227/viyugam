from fastapi import APIRouter, HTTPException
from app.models.project import Project, ProjectStatus
from typing import List, Optional
from pydantic import BaseModel

router = APIRouter()

class ProjectCreate(BaseModel):
    title: str
    domain_id: str
    description: Optional[str] = None
    status: ProjectStatus = ProjectStatus.ACTIVE
    budget: float = 0
    impact: int = 5
    effort: int = 5

@router.post("/", response_model=Project)
async def create_project(payload: ProjectCreate):
    # For MVP, we assume a single user or hardcode user_id
    # TODO: Get user from auth context
    project = Project(
        user_id="user_2r9n...", # Placeholder or real ID
        **payload.dict()
    )
    await project.insert()
    return project

@router.get("/", response_model=List[Project])
async def get_projects(status: Optional[ProjectStatus] = None):
    # Filter by user_id in real app
    if status:
        return await Project.find(Project.status == status).to_list()
    return await Project.find_all().to_list()

@router.put("/{project_id}", response_model=Project)
async def update_project(project_id: str, payload: dict):
    project = await Project.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Generic update
    for k, v in payload.items():
        if hasattr(project, k):
            setattr(project, k, v)
    
    await project.save()
    return project

@router.delete("/{project_id}")
async def delete_project(project_id: str):
    project = await Project.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    await project.delete()
    return {"status": "deleted"}
