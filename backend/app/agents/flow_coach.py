from pydantic import BaseModel, Field
from typing import List, Optional
from app.services.gemini import gemini_service
import json

class FlowCoachResponse(BaseModel):
    message: str = Field(..., description="The conversational response to the user. Be concise, punchy, and action-oriented.")
    suggested_actions: List[str] = Field(default=[], description="Short, clickable follow-up actions (max 3).")
    sentiment: str = Field(..., description="Current vibe: 'Encouraging', 'Stern', 'Analytical'")

class FlowCoachAgent:
    """
    The Flow Coach provides real-time tactical advice based on the user's schedule and current state.
    """
    
    async def chat(self, user_message: str, context: dict) -> FlowCoachResponse:
        schedule_str = json.dumps(context.get('tasks', []), indent=2)
        current_time = context.get('current_time', 'Unknown')
        
        prompt = f"""
        You are The Flow Coach. You are a mix of David Goggins (discipline) and James Clear (systems).
        
        CONTEXT:
        Current Time: {current_time}
        User's Daily Schedule:
        {schedule_str}
        
        USER MESSAGE: "{user_message}"
        
        INSTRUCTIONS:
        1. Answer the user's question or provide guidance.
        2. Reference the schedule specifically if relevant (e.g., "You have a meeting in 10 mins").
        3. Be concise. No fluff.
        4. Suggest 1-3 immediate actions.
        """
        
        return await gemini_service.generate_structured(prompt, FlowCoachResponse)

flow_coach = FlowCoachAgent()
