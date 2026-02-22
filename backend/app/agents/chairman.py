import json
from typing import List, Dict, Any
from app.services.gemini import gemini_service

class ChairmanAgent:
    """
    L2 Chairman Agent: Handles Inbox Triage and Daily Scheduling.
    Phase 1 Focus: Inbox Triage.
    """
    
    async def process_inbox(self, raw_items: List[str]) -> List[Dict[str, Any]]:
        if not raw_items:
            return []

        prompt = f"""
        You are The Chairman, an elite Executive Assistant AI for High Performance Individuals.
        
        YOUR GOAL: Classify the following raw inbox items into 'task', 'project', or 'note'.
        
        INPUTS:
        {json.dumps(raw_items, indent=2)}
        
        INSTRUCTIONS:
        1. Analyze each item.
        2. Assign a 'type': 'task', 'project', or 'note'.
        3. If 'task':
           - Extract 'title'.
           - Estimate 'energy_cost' (1-10, where 1=Low, 10=High).
           - Estimate 'estimated_minutes' (default 15 if unknown).
           - Extract 'context' (e.g. "errand", "desk", "call").
        4. If 'project':
           - Extract 'title'.
        5. If 'note':
           - Keep content.
           
        OUTPUT FORMAT:
        Return ONLY a raw valid JSON list of objects. Do not include markdown formatting like ```json.
        Example object: {{ "original_text": "...", "type": "task", "task_data": {{ ... }} }}
        """
        
        response_text = await gemini_service.generate_json(prompt)
        
        # Clean up potential markdown code blocks if the model ignores the instruction
        cleaned_text = response_text.replace("```json", "").replace("```", "").strip()
        
        try:
            processed_data = json.loads(cleaned_text)
            return processed_data
        except json.JSONDecodeError:
            print(f"Failed to parse JSON from Agent: {cleaned_text}")
            return [{"original_text": item, "error": "Parse Error", "raw_response": cleaned_text} for item in raw_items]

chairman = ChairmanAgent()
