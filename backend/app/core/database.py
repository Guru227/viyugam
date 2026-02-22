from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie
from app.core.config import settings
from app.models.user import User
from app.models.task import Task
from app.models.inbox import InboxItem
from app.models.domain import LifeDomain
from app.models.project import Project, Milestone
from app.models.finance import Budget, Transaction

async def init_db():
    print(f"DEBUG: Connecting to MongoDB at '{settings.MONGO_URI}'")
    try:
        client = AsyncIOMotorClient(settings.MONGO_URI)
        # Ping the DB to ensure connection
        await client.admin.command('ping')
        
        # Initialize Beanie with the actual models
        await init_beanie(
            database=client[settings.DATABASE_NAME], 
            document_models=[
                User, 
                Task, 
                InboxItem, 
                LifeDomain, 
                Project, 
                Budget,
                Transaction
            ]
        )
        print(f"Connected to MongoDB at {settings.MONGO_URI}")
        return client
    except Exception as e:
        print(f"Failed to connect to MongoDB: {e}")
        raise e
