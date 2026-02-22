from beanie import Document, Indexed
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional

class SeasonConfig(BaseModel):
    name: str = "Default"
    weight_health: float = 0.2
    weight_wealth: float = 0.2
    weight_career: float = 0.2
    weight_joy: float = 0.2
    weight_learning: float = 0.2

class UserSettings(BaseModel):
    daily_work_hours_cap: int = 8
    currency_symbol: str = "₹"
    timezone: str = "Asia/Kolkata"
    theme: str = "dark"

class User(Document):
    clerk_id: Indexed(str, unique=True)
    email: str
    display_name: str
    
    settings: UserSettings = UserSettings()
    current_season: SeasonConfig = SeasonConfig()
    
    last_login_at: datetime = Field(default_factory=datetime.now)
    current_streak: int = 0

    class Settings:
        name = "users"
