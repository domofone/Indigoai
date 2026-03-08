"""
OpenRouter API integration for LLM calls.
"""
import httpx
from typing import Dict, Any, Optional
from app.core.config import settings


class OpenRouterClient:
    """Client for OpenRouter API (compatible with OpenAI format)."""
    
    def __init__(self):
        self.base_url = settings.openrouter_base_url
        self.api_key = settings.openrouter_api_key
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://brauz.app",  # Optional: your app URL
            "X-Title": "braz!"  # Optional: app name for OpenRouter dashboard
        }
    
    async def chat_completion(
        self,
        messages: list,
        model: str = "anthropic/claude-3-haiku",
        temperature: float = 0.7,
        max_tokens: int = 1000
    ) -> Dict[str, Any]:
        """
        Send chat completion request to OpenRouter.
        
        Args:
            messages: List of message dicts [{"role": "user", "content": "..."}]
            model: Model identifier (see OpenRouter models)
            temperature: 0.0-1.0
            max_tokens: Max response tokens
            
        Returns:
            Raw API response
        """
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers=self.headers
            )
            response.raise_for_status()
            return response.json()
    
    async def analyze_intent(self, text: str) -> Dict[str, Any]:
        """
        Analyze user intent and decompose into agent tasks.
        
        Returns:
            {
                "intent": "plan_date",
                "tasks": [
                    {"agent": "weather", "params": {"date": "2025-03-15"}},
                    {"agent": "location", "params": {"type": "cafe", "budget": 5000}},
                    {"agent": "planning", "params": {}}
                ],
                "summary": "User wants to plan a date with budget 5000 RUB"
            }
        """
        system_prompt = """Ты - оркестратор мультиагентной системы. 
Анализируй запрос пользователя и определи:
1. Какие агенты нужны (weather, location, planning, ideas, calendar, budget)
2. Параметры для каждого агента
3. Краткое описание намерения

Верни JSON:
{
    "intent": "категория_запроса",
    "tasks": [
        {"agent": "имя_агента", "params": {"ключ": "значение"}}
    ],
    "summary": "краткое_описание"
}
Только JSON, без пояснений."""
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text}
        ]
        
        response = await self.chat_completion(
            messages=messages,
            model=settings.openrouter_models["orchestrator"],
            temperature=0.3
        )
        
        # Extract and parse JSON from response
        content = response["choices"][0]["message"]["content"]
        try:
            import json
            # Sometimes model wraps JSON in ```json ... ```
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            result = json.loads(content)
            return result
        except Exception as e:
            return {
                "intent": "unknown",
                "tasks": [{"agent": "ideas", "params": {}}],
                "summary": text[:100],
                "error": str(e)
            }