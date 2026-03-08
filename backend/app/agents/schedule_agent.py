"""
Schedule Agent - составление расписания и тайм-менеджмент.
"""
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta, time
import json

from .base_agent import BaseAgent, AgentRequest, AgentResponse
from app.integrations.openrouter import OpenRouterClient
from app.core.config import settings


class ScheduleAgent(BaseAgent):
    """Agent for creating schedules and timetables."""
    
    agent_type = "schedule"
    dependencies = []  # Could depend on weather/location in future
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self.openrouter = OpenRouterClient()
    
    async def execute(self, request: AgentRequest) -> AgentResponse:
        """
        Create a schedule for activities.
        
        Expected parameters:
        - activities: list of dicts [{"name": "Ужин", "duration_minutes": 90, "priority": 1, "category": "food"}]
        - date: str (ISO date, default: today)
        - start_time: str (HH:MM, default: 09:00)
        - end_time: str (HH:MM, default: 21:00)
        - breaks: bool (include breaks between activities, default: True)
        - optimize_order: bool (reorder for efficiency, default: True)
        """
        start_time_req = datetime.utcnow()
        
        try:
            activities = request.parameters.get("activities", [])
            schedule_date = request.parameters.get("date", datetime.utcnow().strftime("%Y-%m-%d"))
            start_time_str = request.parameters.get("start_time", "09:00")
            end_time_str = request.parameters.get("end_time", "21:00")
            include_breaks = request.parameters.get("breaks", True)
            optimize_order = request.parameters.get("optimize_order", True)
            
            if not activities:
                return AgentResponse(
                    success=False,
                    data={},
                    error="Activities list is required",
                    confidence=0.0,
                    processing_time_ms=int((datetime.utcnow() - start_time_req).total_seconds() * 1000)
                )
            
            # Parse times
            start_hour, start_min = map(int, start_time_str.split(":"))
            end_hour, end_min = map(int, end_time_str.split(":"))
            work_start = time(start_hour, start_min)
            work_end = time(end_hour, end_min)
            
            # Convert activities to internal format
            parsed_activities = []
            for i, act in enumerate(activities):
                parsed_activities.append({
                    "id": i,
                    "name": act.get("name", f"Activity {i+1}"),
                    "duration": act.get("duration_minutes", 60),
                    "priority": act.get("priority", 5),  # 1=highest, 10=lowest
                    "category": act.get("category", "general"),
                    "location": act.get("location", ""),
                    "fixed_time": act.get("fixed_time")  # If activity must be at specific time
                })
            
            # Optimize order if requested and no fixed times
            if optimize_order:
                parsed_activities = self._optimize_activity_order(parsed_activities)
            
            # Generate schedule
            schedule = self._create_schedule(
                parsed_activities,
                schedule_date,
                work_start,
                work_end,
                include_breaks
            )
            
            # Calculate statistics
            total_time = sum(s["duration_minutes"] for s in schedule)
            break_time = sum(s.get("break_after", 0) for s in schedule)
            
            result = {
                "date": schedule_date,
                "schedule": schedule,
                "total_activity_minutes": total_time,
                "total_break_minutes": break_time,
                "total_scheduled_minutes": total_time + break_time,
                "work_hours_available": self._calculate_minutes_between(work_start, work_end),
                "utilization_rate": (total_time + break_time) / max(self._calculate_minutes_between(work_start, work_end), 1) * 100,
                "activities_count": len(activities)
            }
            
            return AgentResponse(
                success=True,
                data=result,
                confidence=0.9,
                processing_time_ms=int((datetime.utcnow() - start_time_req).total_seconds() * 1000)
            )
            
        except Exception as e:
            return AgentResponse(
                success=False,
                data={},
                error=str(e),
                confidence=0.0,
                processing_time_ms=int((datetime.utcnow() - start_time_req).total_seconds() * 1000)
            )
    
    def _optimize_activity_order(self, activities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Optimize activity order based on priority and logical grouping.
        Simple heuristic: sort by priority, then by category.
        """
        # Separate fixed-time activities
        fixed = [a for a in activities if a.get("fixed_time")]
        flexible = [a for a in activities if not a.get("fixed_time")]
        
        # Sort flexible by priority (lower number = higher priority)
        flexible.sort(key=lambda x: x["priority"])
        
        # Group by category for efficiency (optional enhancement)
        # For now just return fixed + sorted flexible
        return fixed + flexible
    
    def _create_schedule(
        self,
        activities: List[Dict[str, Any]],
        date_str: str,
        work_start: time,
        work_end: time,
        include_breaks: bool
    ) -> List[Dict[str, Any]]:
        """
        Create a timetable by placing activities sequentially.
        """
        schedule = []
        current_time = datetime.strptime(f"{date_str} {work_start.strftime('%H:%M')}", "%Y-%m-%d %H:%M")
        work_end_dt = datetime.strptime(f"{date_str} {work_end.strftime('%H:%M')}", "%Y-%m-%d %H:%M")
        
        for activity in activities:
            # Check if activity has fixed time
            if activity.get("fixed_time"):
                fixed_start = datetime.strptime(f"{date_str} {activity['fixed_time']}", "%Y-%m-%d %H:%M")
                duration = activity["duration"]
                fixed_end = fixed_start + timedelta(minutes=duration)
                
                schedule.append({
                    "activity_id": activity["id"],
                    "name": activity["name"],
                    "category": activity["category"],
                    "location": activity.get("location", ""),
                    "start_time": fixed_start.strftime("%H:%M"),
                    "end_time": fixed_end.strftime("%H:%M"),
                    "duration_minutes": duration,
                    "is_fixed": True
                })
                current_time = fixed_end  # Update current time after fixed activity
                continue
            
            # Check if activity fits before work end
            duration = activity["duration"]
            activity_end = current_time + timedelta(minutes=duration)
            
            if activity_end > work_end_dt:
                # Activity doesn't fit, skip or move to next day (simple: skip for now)
                continue
            
            # Add activity to schedule
            schedule.append({
                "activity_id": activity["id"],
                "name": activity["name"],
                "category": activity["category"],
                "location": activity.get("location", ""),
                "start_time": current_time.strftime("%H:%M"),
                "end_time": activity_end.strftime("%H:%M"),
                "duration_minutes": duration,
                "is_fixed": False
            })
            
            # Add break after if needed
            if include_breaks and activity != activities[-1]:
                break_minutes = 15  # Default break
                current_time = activity_end + timedelta(minutes=break_minutes)
                schedule[-1]["break_after"] = break_minutes
            else:
                current_time = activity_end
        
        return schedule
    
    def _calculate_minutes_between(self, start: time, end: time) -> int:
        """Calculate total minutes between two time objects."""
        start_dt = datetime.combine(datetime.today(), start)
        end_dt = datetime.combine(datetime.today(), end)
        return int((end_dt - start_dt).total_seconds() / 60)