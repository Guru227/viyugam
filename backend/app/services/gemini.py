import google.generativeai as genai
from app.core.config import settings
from typing import Optional, Type, List, Any
from pydantic import BaseModel
import json

class GeminiService:
    def __init__(self):
        if settings.GEMINI_API_KEY:
            genai.configure(api_key=settings.GEMINI_API_KEY)
            self.model_flash = genai.GenerativeModel('gemini-2.0-flash-exp') # Using experimental flash as per PRD "Gemini 2.0 Flash"
            self.embedding_model = 'models/text-embedding-004'
        else:
            print("Warning: GEMINI_API_KEY not set.")

    async def generate_content(self, prompt: str) -> str:
        if not settings.GEMINI_API_KEY:
            return "Error: API Key missing"
        
        response = await self.model_flash.generate_content_async(prompt)
        return response.text

    async def generate_json(self, prompt: str) -> str:
        """
        Legacy JSON generation without strict schema enforcement.
        Returns raw JSON string.
        """
        if not settings.GEMINI_API_KEY:
            raise ValueError("No API Key")

        generation_config = {"response_mime_type": "application/json"}
        model = genai.GenerativeModel('gemini-2.0-flash-exp', generation_config=generation_config)
        response = await model.generate_content_async(prompt)
        return response.text

    async def generate_structured(self, prompt: str, schema_class: Type[BaseModel]) -> BaseModel:
        """
        Generates a response strictly adhering to the Pydantic schema.
        """
        if not settings.GEMINI_API_KEY:
            raise ValueError("No API Key")

        # Pass the schema class directly to response_schema
        generation_config = {
            "response_mime_type": "application/json",
            "response_schema": schema_class
        }
        
        model = genai.GenerativeModel('gemini-2.0-flash-exp', generation_config=generation_config)
        response = await model.generate_content_async(prompt)
        
        try:
            # Parse JSON and validate with Pydantic
            data = json.loads(response.text)
            return schema_class(**data)
        except json.JSONDecodeError:
            print(f"Failed to parse JSON: {response.text}")
            raise
        except Exception as e:
            print(f"Validation Error: {e}")
            raise

    async def get_embedding(self, text: str) -> List[float]:
        if not settings.GEMINI_API_KEY:
            raise ValueError("No API Key")
            
        result = await genai.embed_content_async(
            model=self.embedding_model,
            content=text,
            task_type="retrieval_document"
        )
        return result['embedding']

gemini_service = GeminiService()
