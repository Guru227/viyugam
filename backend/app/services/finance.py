from datetime import datetime, timedelta
import calendar
from app.models.finance import Budget, Transaction, TransactionType

class FinanceService:
    
    async def calculate_safe_to_spend(self, user_id: str) -> dict:
        """
        Calculates the "Safe to Spend" daily amount.
        Formula: (Income - Fixed Costs - Savings - Already Spent) / Days Remaining
        """
        today = datetime.now()
        _, last_day = calendar.monthrange(today.year, today.month)
        days_remaining = max(1, last_day - today.day + 1) # Include today
        
        # 1. Get Monthly Income (Estimated from budgets or transactions? For now, hardcoded or single budget entry)
        # Let's assume a 'Income' budget type or just positive transactions?
        # Simpler: Total Budget Limit for 'Needs' + 'Wants' is the cap.
        
        # Real approach for "Safe to Spend":
        # We need a 'Disposable Income' number.
        # Let's assume for MVP: Total Budget - Actual Spend.
        
        all_budgets = await Budget.find(Budget.user_id == user_id).to_list()
        total_budget = sum(b.monthly_limit for b in all_budgets if b.type != 'income')
        
        # 2. Get Actual Spend this month
        start_of_month = today.replace(day=1, hour=0, minute=0, second=0)
        transactions = await Transaction.find(
            Transaction.user_id == user_id,
            Transaction.date >= start_of_month,
            Transaction.type == TransactionType.EXPENSE
        ).to_list()
        
        total_spent = sum(t.amount for t in transactions)
        
        remaining_budget = total_budget - total_spent
        safe_daily = remaining_budget / days_remaining
        
        return {
            "total_budget": total_budget,
            "total_spent": total_spent,
            "remaining": remaining_budget,
            "days_remaining": days_remaining,
            "safe_to_spend_daily": safe_daily
        }

finance_service = FinanceService()
