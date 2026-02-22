from beanie import Document, Indexed
from pydantic import Field, BaseModel
from datetime import datetime
from typing import Optional
from enum import Enum

class TransactionType(str, Enum):
    INCOME = "income"
    EXPENSE = "expense"

class BudgetCategory(str, Enum):
    NEEDS = "needs"
    WANTS = "wants"
    SAVINGS = "savings"
    INVESTMENT = "investment"

class Budget(Document):
    user_id: Indexed(str)
    category: str # e.g., "Housing", "Software", "Coffee"
    type: BudgetCategory = BudgetCategory.NEEDS
    
    monthly_limit: float = 0.0
    
    class Settings:
        name = "budgets"
        indexes = ["user_id"]

class Transaction(Document):
    user_id: Indexed(str)
    
    amount: float
    description: str
    date: datetime = Field(default_factory=datetime.now)
    type: TransactionType = TransactionType.EXPENSE
    
    category: Optional[str] = None # Links to Budget.category
    
    class Settings:
        name = "transactions"
        indexes = ["user_id", "date"]
