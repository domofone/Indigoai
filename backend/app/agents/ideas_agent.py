"""
Ideas Agent - генерация идей и рекомендаций через OpenRouter.
"""
import json
from typing import Dict, Any, Optional, List
from datetime import datetime

from .base_agent import BaseAgent, AgentRequest, AgentResponse
from app.integrations.openrouter import OpenRouterClient
from app.core.config import settings


class IdeasAgent(BaseAgent):
    """Agent for generating creative ideas and suggestions."""
    
    agent_type = "ideas"
    dependencies = []  # Independent
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self.openrouter = OpenRouterClient()
    
    async def execute(self, request: AgentRequest) -> AgentResponse:
        """
        Generate ideas based on topic and constraints.
        
        Expected parameters:
        - topic: str (what to generate ideas about)
        - constraints: list of str (optional constraints)
        - count: int (number of ideas, default: 5)
        - context: dict (additional context like budget, date, location)
        """
        start_time = datetime.utcnow()
        
        try:
            topic = request.parameters.get("topic", "")
            constraints = request.parameters.get("constraints", [])
            count = request.parameters.get("count", 5)
            context = request.parameters.get("context", {})
            
            if not topic:
                return AgentResponse(
                    success=False,
                    data={},
                    error="Topic is required",
                    confidence=0.0,
                    processing_time_ms=int((datetime.utcnow() - start_time).total_seconds() * 1000)
                )
            
            # Build prompt with context
            prompt_parts = [f"Сгенерируй {count} идей/рекомендаций по теме: {topic}"]
            
            if constraints:
                prompt_parts.append(f"\nОграничения: {', '.join(constraints)}")
            
            # Add context
            if context:
                ctx_parts = []
                if context.get("budget"):
                    ctx_parts.append(f"Бюджет: {context['budget']} руб")
                if context.get("date"):
                    ctx_parts.append(f"Дата: {context['date']}")
                if context.get("location"):
                    ctx_parts.append(f"Локация: {context['location']}")
                if ctx_parts:
                    prompt_parts.append(f"\nКонтекст: {'; '.join(ctx_parts)}")
            
            prompt_parts.append("\nИдеи должны быть практичными, конкретными и соответствовать контексту.")
            prompt_parts.append("\nВерни результат в виде JSON: {\"ideas\": [\"идея 1\", \"идея 2\", ...]}")
            
            full_prompt = "".join(prompt_parts)
            
            messages = [
                {"role": "system", "content": "Ты - креативный помощник приложения 'браюз!'. Генерируешь практичные идеи для повседневных задач."},
                {"role": "user", "content": full_prompt}
            ]
            
            response = await self.openrouter.chat_completion(
                messages=messages,
                model=settings.openrouter_models["creative"],
                temperature=0.8,
                max_tokens=800
            )
            
            content = response["choices"][0]["message"]["content"]
            
            # Parse JSON response
            try:
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0].strip()
                result = json.loads(content)
                ideas = result.get("ideas", [])
            except Exception:
                # Fallback: extract list manually
                ideas = [line.strip("- *") for line in content.split("\n") if line.strip().startswith(("-", "*"))]
                if not ideas:
                    ideas = [content] if content else []
            
            return AgentResponse(
                success=True,
                data={"ideas": ideas[:count], "topic": topic},
                confidence=0.8,
                metadata={"model": settings.openrouter_models["creative"]},
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