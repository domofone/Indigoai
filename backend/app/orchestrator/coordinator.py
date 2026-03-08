"""
Orchestrator (Coordinator) - ядро мультиагентной системы.
Принимает запрос, определяет необходимые агенты, координирует их параллельное выполнение,
агрегирует результаты и генерирует финальный ответ.
"""
import asyncio
import json
from typing import Dict, Any, List, Optional
from datetime import datetime
from dataclasses import dataclass, field

from .base_agent import BaseAgent, AgentRequest, AgentResponse
from app.integrations.openrouter import OpenRouterClient
from app.core.config import settings
from app.models.models import Query, AgentExecution, QueryResult
from app.database.database import AsyncSessionLocal
from app.crud.crud_query import (
    create_query_execution,
    update_query_status,
    complete_query,
    save_agent_execution
)


@dataclass
class TaskPlan:
    """План задач, сгенерированный оркестратором."""
    intent: str
    tasks: List[Dict[str, Any]]
    summary: str
    query_id: str


class Orchestrator:
    """
    Главный координатор мультиагентной системы.
    
    Responsibilities:
    1. Анализ запроса пользователя через OpenRouter
    2. Определение необходимых агентов и их параметров
    3. Параллельное выполнение агентов с управлением зависимостями
    4. Агрегация результатов
    5. Генерация финального ответа
    6. Сохранение истории в БД
    """
    
    def __init__(self, agents: Dict[str, BaseAgent]):
        self.agents = agents
        self.openrouter = OpenRouterClient()
        self.max_concurrent_agents = settings.max_agents_per_query
    
    async def process_query(
        self,
        user_text: str,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Обработать запрос пользователя через оркестрацию агентов.
        
        Args:
            user_text: Исходный текст запроса от пользователя
            user_id: ID пользователя (для истории)
            session_id: ID сессии (для группировки запросов)
            context: Дополнительный контекст (локация, бюджет, дата и т.д.)
            
        Returns:
            Структурированный результат с финальным ответом
        """
        start_time = datetime.utcnow()
        query_id = None
        
        async with AsyncSessionLocal() as db:
            try:
                # 1. Сохранить запрос в БД
                query_db = await create_query_execution(
                    db=db,
                    user_id=user_id,
                    session_id=session_id,
                    original_text=user_text,
                    context=context or {}
                )
                query_id = str(query_db.id)
                await db.commit()
                
                # 2. Анализ намерения и планирование задач
                plan = await self._plan_tasks(user_text, context, query_id)
                await update_query_status(db, query_id, "processing")
                
                # 3. Выполнить агентов параллельно (с учётом зависимостей)
                results = await self._execute_agents(plan, context)
                
                # 4. Агрегировать результаты
                aggregated = self._aggregate_results(plan.intent, results, user_text)
                
                # 5. Генерировать финальный ответ через OpenRouter
                final_response = await self._generate_final_response(
                    user_text, aggregated, results
                )
                
                # 6. Сохранить финальный результат
                await complete_query(
                    db=db,
                    query_id=query_id,
                    result=final_response,
                    agent_executions=results
                )
                await db.commit()
                
                processing_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)
                
                return {
                    "query_id": query_id,
                    "status": "completed",
                    "final_result": final_response,
                    "processing_time_ms": processing_time,
                    "agents_used": [r["agent"] for r in results if r["success"]]
                }
                
            except Exception as e:
                if query_id:
                    await update_query_status(
                        db, query_id, "failed", error=str(e)
                    )
                    await db.commit()
                return {
                    "query_id": query_id,
                    "status": "failed",
                    "error": str(e)
                }
    
    async def _plan_tasks(
        self,
        user_text: str,
        context: Optional[Dict[str, Any]],
        query_id: str
    ) -> TaskPlan:
        """
        Использует OpenRouter для анализа запроса и создания плана задач.
        """
        # Подготовка контекста
        context_str = ""
        if context:
            context_parts = []
            if context.get("location"):
                context_parts.append(f"Локация: {context['location']}")
            if context.get("budget"):
                context_parts.append(f"Бюджет: {context['budget']} руб")
            if context.get("date"):
                context_parts.append(f"Дата: {context['date']}")
            if context_parts:
                context_str = "\nДополнительный контекст: " + ", ".join(context_parts)
        
        prompt = f"""Запрос пользователя: "{user_text}"{context_str}

Опредеleen, какие агенты нужны для ответа. Доступные агенты:
- weather: погода (параметры: location, date)
- location: места (параметры: location, place_type, budget, radius)
- ideas: генерация идей (параметры: topic, constraints)
- budget: расчёт бюджета (параметры: items, currency)
- calendar: календарь (параметры: date_range, check_only)
- schedule: составление расписания (параметры: date, time_window, activities)

Верни ТОЛЬКО JSON:
{{
    "intent": "категория_запроса",
    "tasks": [
        {{"agent": "agent_name", "params": {{"ключ": "значение"}}}}
    ],
    "summary": "краткое_описание_намерения"
}}"""

        messages = [
            {"role": "system", "content": "Ты - оркестратор мультиагентной системы для бэкенда приложения 'брауз!'. Анализируй запросы на русском языке."},
            {"role": "user", "content": prompt}
        ]
        
        try:
            response = await self.openrouter.chat_completion(
                messages=messages,
                model=settings.openrouter_models["orchestrator"],
                temperature=0.3,
                max_tokens=500
            )
            
            content = response["choices"][0]["message"]["content"]
            # Очистка от markdown
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            
            plan_data = json.loads(content)
            
            # Валидация: проверяем существование агентов
            valid_tasks = []
            for task in plan_data.get("tasks", []):
                if task["agent"] in self.agents:
                    valid_tasks.append(task)
                else:
                    print(f"Warning: Agent '{task['agent']}' not found, skipping")
            
            if not valid_tasks:
                # Fallback на ideas агента
                valid_tasks = [{"agent": "ideas", "params": {}}]
                plan_data["summary"] = f"Идеи по запросу: {user_text[:50]}"
            
            return TaskPlan(
                intent=plan_data.get("intent", "unknown"),
                tasks=valid_tasks,
                summary=plan_data.get("summary", user_text[:100]),
                query_id=query_id
            )
            
        except Exception as e:
            print(f"Error in _plan_tasks: {e}")
            # Fallback: используем только ideas агента
            return TaskPlan(
                intent="fallback",
                tasks=[{"agent": "ideas", "params": {}}],
                summary=f"Идеи по запросу: {user_text[:50]}",
                query_id=query_id
            )
    
    async def _execute_agents(
        self,
        plan: TaskPlan,
        context: Optional[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Выполняет задачи агентов параллельно с учётом зависимостей.
        Возвращает список результатов.
        """
        results = []
        # Маппинг: agent_name -> execution_order
        execution_plan = []
        
        # Простой топологический сорт по зависимостям (BFS)
        executed = set()
        pending = plan.tasks.copy()
        
        while pending:
            # Находим агенты, готовые к выполнению (все зависимости выполнены)
            ready = []
            for task in pending:
                agent_name = task["agent"]
                agent = self.agents[agent_name]
                deps = set(agent.dependencies)
                if deps.issubset(executed):
                    ready.append(task)
            
            if not ready:
                # Циклические зависимости или ошибка - выполняем оставшиеся
                ready = pending[:1] if pending else []
            
            # Выполняем готовые агенты параллельно
            tasks_to_run = []
            for task in ready:
                agent_name = task["agent"]
                params = {**task["params"], "context": context or {}}
                tasks_to_run.append(self._execute_single_agent(agent_name, params))
            
            if tasks_to_run:
                batch_results = await asyncio.gather(*tasks_to_run, return_exceptions=True)
                for i, result in enumerate(batch_results):
                    task = ready[i]
                    agent_name = task["agent"]
                    
                    if isinstance(result, Exception):
                        results.append({
                            "agent": agent_name,
                            "success": False,
                            "error": str(result),
                            "data": {},
                            "confidence": 0.0
                        })
                    else:
                        results.append({
                            "agent": agent_name,
                            "success": result.success,
                            "data": result.data,
                            "confidence": result.confidence,
                            "error": result.error,
                            "metadata": result.metadata
                        })
                    executed.add(agent_name)
            
            # Удаляем выполненные из pending
            for task in ready:
                if task in pending:
                    pending.remove(task)
        
        return results
    
    async def _execute_single_agent(
        self,
        agent_name: str,
        params: Dict[str, Any]
    ) -> AgentResponse:
        """
        Выполнить одного агента с таймаутом и обработкой ошибок.
        """
        agent = self.agents[agent_name]
        request = AgentRequest(
            query_id="",  # Будет заполнено в医药执行
            user_id=None,
            parameters=params,
            context=params.get("context", {})
        )
        
        try:
            # Таймаут на выполнение агента
            response = await asyncio.wait_for(
                agent.execute(request),
                timeout=settings.request_timeout_seconds
            )
            return response
        except asyncio.TimeoutError:
            return AgentResponse(
                success=False,
                data={},
                error="Agent timeout",
                confidence=0.0
            )
        except Exception as e:
            return AgentResponse(
                success=False,
                data={},
                error=str(e),
                confidence=0.0
            )
    
    def _aggregate_results(
        self,
        intent: str,
        agent_results: List[Dict[str, Any]],
        original_query: str
    ) -> Dict[str, Any]:
        """
        Агрегировать результаты всех агентов в структурированный ответ.
        """
        successful_results = [r for r in agent_results if r["success"]]
        
        aggregated = {
            "intent": intent,
            "summary": "",
            "stages": [],
            "suggestions": [],
            "estimated_budget": None,
            "visual_data": None
        }
        
        # Собираем данные от агентов
        for i, result in enumerate(successful_results):
            stage = {
                "agent": result["agent"],
                "title": self._get_agent_title(result["agent"]),
                "data": result["data"],
                "confidence": result["confidence"],
                "display_order": i
            }
            aggregated["stages"].append(stage)
            
            # Специфичная обработка
            if result["agent"] == "weather" and "forecast" in result["data"]:
                aggregated["summary"] += f"Погода: {result['data'].get('description', 'неизвестно')}. "
            
            elif result["agent"] == "location" and "places" in result["data"]:
                num_places = len(result["data"]["places"])
                aggregated["summary"] += f"Найдено мест: {num_places}. "
                if "estimated_budget" not in aggregated and result["data"].get("places"):
                    # Оценочный бюджет (средний)
                    prices = []
                    for p in result["data"]["places"]:
                        if p.get("price_level") is not None:
                            # Преобразуем Google price_level (0-4) в примерную стоимость
                            prices.append((p["price_level"] + 1) * 500)  # ~ руб
                    if prices:
                        aggregated["estimated_budget"] = sum(prices) / len(prices)
            
            elif result["agent"] == "budget":
                if "total" in result["data"]:
                    aggregated["estimated_budget"] = result["data"]["total"]
                if "breakdown" in result["data"]:
                    aggregated["budget_breakdown"] = result["data"]["breakdown"]
            
            elif result["agent"] == "schedule":
                if "schedule" in result["data"]:
                    aggregated["schedule"] = result["data"]["schedule"]
                    aggregated["summary"] += "Составлено расписание. "
        
        # Если нет собранного summary, используем OpenRouter для генерации
        if not aggregated["summary"].strip():
            aggregated["summary"] = self._generate_simple_summary(intent, successful_results)
        
        return aggregated
    
    def _generate_simple_summary(
        self,
        intent: str,
        results: List[Dict[str, Any]]
    ) -> str:
        """Генерирует простой summary на основе результатов."""
        summaries = []
        for r in results:
            if r["agent"] == "weather":
                data = r["data"]
                summaries.append(f"Погода: {data.get('description', 'неизвестно')}, {data.get('temperature', '?')}°C")
            elif r["agent"] == "location":
                data = r["data"]
                summaries.append(f"Найдено {data.get('total_found', 0)} мест")
            elif r["agent"] == "ideas":
                data = r["data"]
                if "ideas" in data:
                    summaries.append(f"Идеи: {', '.join(data['ideas'][:3])}")
        return " | ".join(summaries) if summaries else "Запрос обработан"
    
    def _get_agent_title(self, agent_name: str) -> str:
        """Человекочитаемое название агента."""
        titles = {
            "weather": "Погода",
            "location": "Места",
            "ideas": "Идеи",
            "budget": "Бюджет",
            "calendar": "Календарь",
            "schedule": "Расписание"
        }
        return titles.get(agent_name, agent_name.capitalize())
    
    async def _generate_final_response(
        self,
        user_query: str,
        aggregated: Dict[str, Any],
        agent_results: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Генерирует финальный, связный ответ для пользователя через OpenRouter.
        """
        # Формируем контекст для LLM
        context_parts = [f"Запрос пользователя: {user_query}\n"]
        
        for stage in aggregated.get("stages", []):
            context_parts.append(f"\n=== {stage['title']} ===")
            context_parts.append(json.dumps(stage["data"], ensure_ascii=False, indent=2))
        
        if aggregated.get("estimated_budget"):
            context_parts.append(f"\n=== Общий бюджет ===\n{aggregated['estimated_budget']} руб")
        
        context_str = "\n".join(context_parts)
        
        system_prompt = """Ты - ассистент приложения "брауз!".
На основе предоставленных данных от различных агентов составь связный, полезный и дружелюбный ответ пользователю.
Ответ должен быть на русском языке, кратким, но содержать всю важную информацию.
Если есть конкретные рекомендации (места, идеи) - перечисли их."""
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Данные:\n{context_str}\n\nСоздай финальный ответ:"}
        ]
        
        try:
            response = await self.openrouter.chat_completion(
                messages=messages,
                model=settings.openrouter_models["fast"],
                temperature=0.7,
                max_tokens=1000
            )
            
            final_text = response["choices"][0]["message"]["content"]
            
            return {
                "text": final_text,
                "summary": aggregated.get("summary", ""),
                "stages": aggregated.get("stages", []),
                "suggestions": aggregated.get("suggestions", []),
                "estimated_budget": aggregated.get("estimated_budget"),
                "metadata": {
                    "model": settings.openrouter_models["fast"],
                    "tokens_used": response.get("usage", {})
                }
            }
            
        except Exception as e:
            # Fallback: возвращаем агрегированные данные без LLM
            return {
                "text": aggregated.get("summary", "Ошибка генерации ответа"),
                "summary": aggregated.get("summary", ""),
                "stages": aggregated.get("stages", []),
                "suggestions": aggregated.get("suggestions", []),
                "estimated_budget": aggregated.get("estimated_budget"),
                "metadata": {"error": str(e)}
            }