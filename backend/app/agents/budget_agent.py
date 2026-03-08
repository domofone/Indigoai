"""
Budget Agent - расчёт и оптимизация бюджета.
"""
from typing import Dict, Any, Optional, List
from datetime import datetime

from .base_agent import BaseAgent, AgentRequest, AgentResponse
from app.core.config import settings


class BudgetAgent(BaseAgent):
    """Agent for budget calculation and optimization."""
    
    agent_type = "budget"
    dependencies = []  # Independent
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
    
    async def execute(self, request: AgentRequest) -> AgentResponse:
        """
        Calculate budget for items or optimize expenses.
        
        Expected parameters:
        - items: list of dicts [{"name": "restaurant", "cost": 2000, "category": "food"}]
        - currency: str (default: "RUB")
        - optimize: bool (if True, suggest cheaper alternatives)
        - total_budget: float (optional, to check if within budget)
        """
        start_time = datetime.utcnow()
        
        try:
            items = request.parameters.get("items", [])
            currency = request.parameters.get("currency", "RUB")
            optimize = request.parameters.get("optimize", False)
            total_budget = request.parameters.get("total_budget")
            
            if not items:
                return AgentResponse(
                    success=False,
                    data={},
                    error="Items list is required",
                    confidence=0.0,
                    processing_time_ms=int((datetime.utcnow() - start_time).total_seconds() * 1000)
                )
            
            # Calculate total
            total = sum(item.get("cost", 0) for item in items)
            
            # Categorize expenses
            categories = {}
            for item in items:
                cat = item.get("category", "other")
                categories[cat] = categories.get(cat, 0) + item.get("cost", 0)
            
            result = {
                "total": total,
                "currency": currency,
                "item_count": len(items),
                "categories": categories,
                "per_category_breakdown": [
                    {"category": cat, "amount": amt, "percentage": (amt / total * 100) if total > 0 else 0}
                    for cat, amt in categories.items()
                ]
            }
            
            # Check against budget
            if total_budget is not None:
                result["within_budget"] = total <= total_budget
                result["budget_remaining"] = total_budget - total if total <= total_budget else 0
                result["budget_exceeded_by"] = total - total_budget if total > total_budget else 0
            
            # Optimization suggestions
            if optimize:
                suggestions = self._suggest_optimizations(items, categories, total_budget or total * 1.2)
                result["optimization_suggestions"] = suggestions
                result["potential_savings"] = sum(s.get("savings", 0) for s in suggestions)
            
            return AgentResponse(
                success=True,
                data=result,
                confidence=0.95,
                processing_time_ms=int((datetime.utcnow() - start_time).total_seconds() * 1000)
            )
            
        except Exception as e:
            return AgentResponse(
                success=False,
                data={},
                error=str(e),
                confidence=0.0,
                processing_time_ms=int((datetime.utcnow() - start_time).total_seconds() * 1000)
            )
    
    def _suggest_optimizations(
        self,
        items: List[Dict[str, Any]],
        categories: Dict[str, float],
        target_budget: float
    ) -> List[Dict[str, Any]]:
        """
        Suggest ways to optimize budget.
        """
        current_total = sum(item.get("cost", 0) for item in items)
        overspend = current_total - target_budget
        
        if overspend <= 0:
            return [{"message": "Бюджет в норме, оптимизация не требуется", "savings": 0}]
        
        suggestions = []
        
        # Simple heuristics for common categories
        category_avg = {
            "food": 1500,
            "transport": 800,
            "entertainment": 2000,
            "shopping": 3000,
            "other": 1000
        }
        
        # Find expensive items that could be replaced
        expensive_items = sorted(
            [item for item in items if item.get("cost", 0) > category_avg.get(item.get("category", "other"), 1000)],
            key=lambda x: x.get("cost", 0),
            reverse=True
        )
        
        for item in expensive_items[:3]:  # Top 3 expensive items
            current_cost = item.get("cost", 0)
            avg = category_avg.get(item.get("category", "other"), current_cost * 0.7)
            if current_cost > avg * 1.2:
                savings = current_cost - avg
                suggestions.append({
                    "item": item.get("name", "Item"),
                    "current_cost": current_cost,
                    "suggested_cost": avg,
                    "savings": savings,
                    "message": f"'{item.get('name')}' слишком дорогой, можно найти аналогичный за ~{avg} руб"
                })
        
        # Suggest category reductions
        for cat, amount in categories.items():
            if amount > (target_budget * 0.4):  # Category takes >40% of budget
                reduction_needed = amount - (target_budget * 0.3)
                suggestions.append({
                    "category": cat,
                    "current_amount": amount,
                    "suggested_max": target_budget * 0.3,
                    "savings": reduction_needed,
                    "message": f"Слишком много трат на '{cat}': {amount} руб. Сократить до {target_budget * 0.3:.0f} руб"
                })
        
        return suggestions