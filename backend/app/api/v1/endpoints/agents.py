from fastapi import APIRouter, Depends, HTTPException
from typing import List, Optional
from pydantic import BaseModel
from app.agents.chairman import chairman
from app.agents.flow_coach import flow_coach, FlowCoachResponse
from app.agents.boardroom import boardroom, BoardroomDebate
from app.core.auth import get_current_user
from app.models.user import User
from app.models.task import Task
from app.models.project import Project
from datetime import datetime

router = APIRouter()

class ProcessInboxRequest(BaseModel):
    items: List[str]

class FlowChatRequest(BaseModel):
    message: str
    client_time: Optional[str] = None

class BoardroomRequest(BaseModel):
    project_id: str

@router.post("/process-inbox")
async def process_inbox(request: ProcessInboxRequest, current_user: User = Depends(get_current_user)):
    """
    Send raw text to the Chairman Agent for classification.
    """
    results = await chairman.process_inbox(request.items)
    return results

@router.post("/flow-chat", response_model=FlowCoachResponse)
async def flow_chat(request: FlowChatRequest, current_user: User = Depends(get_current_user)):
    """
    Chat with the Flow Coach. Context aware of today's tasks.
    """
    today = datetime.now().date()
    # Filter by user_id == current_user.clerk_id
    tasks = await Task.find(
        Task.user_id == current_user.clerk_id, 
        Task.scheduled_date == today
    ).to_list()
    
    current_time_str = request.client_time or datetime.now().strftime("%I:%M %p")
    
    # Serialize tasks safely
    tasks_data = []
    for t in tasks:
        t_dict = t.dict()
        # Convert non-serializable fields if any, though Pydantic handles most
        # Beanie Document.dict() includes internal stuff, but json.dumps handles primitives.
        # Id field might be ObjectId, but Beanie handles id as PydanticObjectId which serializes to str usually.
        # But for agent prompt, we want cleaner JSON.
        simple_task = {
            "title": t.title,
            "status": t.status,
            "priority": t.priority,
            "time_slot": t.time_slot,
            "description": t.description
        }
        tasks_data.append(simple_task)

    context = {
        "tasks": tasks_data, 
        "current_time": current_time_str
    }
    
    return await flow_coach.chat(request.message, context)

@router.post("/boardroom-meeting", response_model=BoardroomDebate)
async def boardroom_meeting(request: BoardroomRequest, current_user: User = Depends(get_current_user)):
    """
    Trigger a Boardroom Debate for a specific Project.
    """
    project = await Project.get(request.project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
        
    if project.user_id != current_user.clerk_id:
         raise HTTPException(status_code=403, detail="Not authorized")

    # Clean project data for prompt
    project_data = {
        "title": project.title,
        "description": project.description,
        "impact": project.impact,
        "effort": project.effort,
        "budget": project.budget,
        "milestones": [m.dict() for m in project.milestones]
    }

    return await boardroom.convening(project_data)
