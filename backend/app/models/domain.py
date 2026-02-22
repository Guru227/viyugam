from beanie import Document, Indexed
from pydantic import Field
from typing import Optional
from enum import Enum

class DomainName(str, Enum):
    HEALTH = 'Health'
    WEALTH = 'Wealth'
    RELATIONSHIPS = 'Relationships'
    GROWTH = 'Growth'
    CAREER = 'Career'
    SPIRITUALITY = 'Spirituality'

class LifeDomain(Document):
    name: Indexed(str, unique=True)
    
    # Scores (1-10)
    budget_score: int = Field(default=5, ge=1, le=10)
    time_score: int = Field(default=5, ge=1, le=10)
    scope_score: int = Field(default=5, ge=1, le=10)
    target_score: int = Field(default=8, ge=1, le=10)
    
    definition_of_success: str
    color: str

    class Settings:
        name = "domains"
