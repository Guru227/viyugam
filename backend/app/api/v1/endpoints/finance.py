from fastapi import APIRouter, Depends, HTTPException
from typing import List
from app.core.auth import get_current_user
from app.models.user import User
from app.models.finance import Budget, Transaction
from app.services.finance import finance_service
from pydantic import BaseModel

router = APIRouter()

class TransactionCreate(BaseModel):
    amount: float
    description: str
    type: str = "expense"
    category: str = "Uncategorized"

class BudgetCreate(BaseModel):
    category: str
    monthly_limit: float
    type: str = "needs"

@router.get("/overview")
async def get_overview(current_user: User = Depends(get_current_user)):
    """
    Get the Financial Overview (Safe to Spend).
    """
    return await finance_service.calculate_safe_to_spend(current_user.clerk_id)

@router.post("/transactions")
async def create_transaction(txn: TransactionCreate, current_user: User = Depends(get_current_user)):
    t = Transaction(
        user_id=current_user.clerk_id,
        amount=txn.amount,
        description=txn.description,
        type=txn.type,
        category=txn.category
    )
    await t.save()
    return t

@router.get("/transactions")
async def get_transactions(current_user: User = Depends(get_current_user)):
    return await Transaction.find(Transaction.user_id == current_user.clerk_id).sort("-date").limit(50).to_list()

@router.post("/budgets")
async def create_budget(budget: BudgetCreate, current_user: User = Depends(get_current_user)):
    b = Budget(
        user_id=current_user.clerk_id,
        category=budget.category,
        monthly_limit=budget.monthly_limit,
        type=budget.type
    )
    await b.save()
    return b

@router.get("/budgets")
async def get_budgets(current_user: User = Depends(get_current_user)):
    return await Budget.find(Budget.user_id == current_user.clerk_id).to_list()
