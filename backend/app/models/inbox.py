from beanie import Document
from pydantic import Field
from datetime import datetime

class InboxItem(Document):
    user_id: str
    content: str
    source: str = "mobile_pwa" # "cli", "voice"
    is_processed: bool = False
    created_at: datetime = Field(default_factory=datetime.now)

    class Settings:
        name = "inbox"
