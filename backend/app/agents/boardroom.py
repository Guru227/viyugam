from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from app.services.gemini import gemini_service
import json

class DialogueTurn(BaseModel):
    speaker: str = Field(..., description="The persona speaking (e.g., 'Director', 'CFO').")
    text: str = Field(..., description="The content of the speech.")

class BoardroomDebate(BaseModel):
    transcript: List[DialogueTurn] = Field(..., description="List of dialogue turns in order.")
    verdict: str = Field(..., description="Final decision: 'APPROVED', 'REJECTED', or 'REVISE'.")
    summary: str = Field(..., description="Brief summary of the decision rationale.")

class BoardroomAgent:
    """
    Simulates a debate between internal personas (Director, CFO, etc.) -> Boardroom Meeting.
    """
    
    async def convening(self, project_data: dict) -> BoardroomDebate:
        project_str = json.dumps(project_data, indent=2)
        
        prompt = f"""
        Convening a Boardroom Meeting for Project Proposal.
        
        PROJECT DATA:
        {project_str}
        
        PERSONAS:
        - The Director: Visionary, expansionist, risk-taker. Wants growth.
        - The CFO: Conservative, resource-guarding, risk-averse. Wants ROI.
        
        INSTRUCTIONS:
        1. Simulate a debate between The Director and The CFO about this project.
        2. Discuss feasibility, budget, and impact.
        3. Reach a verdict.
        
        OUTPUT:
        Produce a structured debate transcript and valid final verdict.
        """
        
        return await gemini_service.generate_structured(prompt, BoardroomDebate)

boardroom = BoardroomAgent()
