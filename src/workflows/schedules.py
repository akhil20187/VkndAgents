"""
Temporal Schedule Management
Purpose: Create, list, delete, and trigger Temporal Schedules for recurring workflow execution.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import asyncio
import structlog
from datetime import timedelta
from typing import List, Dict, Any, Optional
from temporalio.client import Client, Schedule, ScheduleActionStartWorkflow, ScheduleSpec, ScheduleIntervalSpec, ScheduleCalendarSpec, ScheduleRange
from src.config import settings

logger = structlog.get_logger()

class ScheduleManager:
    """
    Manages Temporal Schedules.
    Purpose: CRUD operations for workflow schedules.
    """
    
    def __init__(self):
        self.client: Optional[Client] = None
        
    async def connect(self):
        """Connect to Temporal Cloud"""
        if not self.client:
            # Load certificates if provided
            tls_config = None
            if settings.temporal_mtls_cert and settings.temporal_mtls_key:
                with open(settings.temporal_mtls_cert, "rb") as f:
                    client_cert = f.read()
                with open(settings.temporal_mtls_key, "rb") as f:
                    client_key = f.read()
                
                tls_config = list(
                    Client.new_tls_config(
                        client_cert=client_cert,
                        client_private_key=client_key,
                    )
                )[0] # Extract the config object
            
            self.client = await Client.connect(
                settings.temporal_host,
                namespace=settings.temporal_namespace,
                api_key=settings.temporal_api_key,
                tls=tls_config,
            )
            logger.info("connected_to_temporal_schedules")

    async def create_daily_schedule(
        self,
        schedule_id: str,
        workflow_id_prefix: str,
        hour: int,
        minute: int,
        workflow_name: str,
        duration_minutes: int,
        timezone: str = "UTC"
    ):
        """
        Create a daily schedule.
        Purpose: Schedule a workflow to run every day at a specific time.
        """
        await self.connect()
        
        # Define what the schedule runs
        action = ScheduleActionStartWorkflow(
            workflow_name,
            args=[settings.default_user_id, duration_minutes],
            id=f"{workflow_id_prefix}-${{scheduledTime}}", # Temporal replaces ${scheduledTime}
            task_queue="daily-task-queue",
        )
        
        # Define when it runs (Daily at hour:minute)
        spec = ScheduleSpec(
            time_zone_name=timezone,
            calendars=[
                ScheduleCalendarSpec(
                    hour=[ScheduleRange(start=hour)],
                    minute=[ScheduleRange(start=minute)],
                )
            ]
        )
        
        # Create the schedule
        try:
            # Check if exists first to avoid error or decide to update
            try:
                await self.client.get_schedule_handle(schedule_id).describe()
                logger.info("schedule_exists_updating", schedule_id=schedule_id)
                # If exists, update it (simplified: delete and recreate or update)
                # For now, let's just delete and recreate to ensure clean state
                await self.client.get_schedule_handle(schedule_id).delete()
            except:
                pass # Doesn't exist
            
            await self.client.create_schedule(
                schedule_id,
                Schedule(action=action, spec=spec),
            )
            logger.info("daily_schedule_created", schedule_id=schedule_id, time=f"{hour}:{minute:02d}")
            return {"success": True, "schedule_id": schedule_id, "action": "created"}
            
        except Exception as e:
            logger.error("create_schedule_failed", error=str(e))
            return {"success": False, "error": str(e)}

    async def list_schedules(self) -> List[Dict[str, Any]]:
        """List all schedules"""
        await self.connect()
        
        schedules = []
        async for schedule_item in await self.client.list_schedules():
            handle = self.client.get_schedule_handle(schedule_item.id)
            desc = await handle.describe()
            schedules.append({
                "id": schedule_item.id,
                "spec": str(desc.schedule.spec), # Simplified representation
                "paused": desc.schedule.state.paused,
                "next_run": desc.info.next_action_times[0].isoformat() if desc.info.next_action_times else None
            })
            
        return schedules

    async def trigger_schedule(self, schedule_id: str):
        """Trigger a schedule immediately"""
        await self.connect()
        try:
            await self.client.get_schedule_handle(schedule_id).trigger()
            logger.info("schedule_triggered", schedule_id=schedule_id)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def delete_schedule(self, schedule_id: str):
        """Delete a schedule"""
        await self.connect()
        try:
            await self.client.get_schedule_handle(schedule_id).delete()
            logger.info("schedule_deleted", schedule_id=schedule_id)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

# CLI Helper
async def main():
    import argparse
    parser = argparse.ArgumentParser(description="Manage Temporal Schedules")
    subparsers = parser.add_subparsers(dest="command")
    
    # List cmd
    parser_list = subparsers.add_parser("list", help="List schedules")
    
    # Create Daily cmd
    parser_create = subparsers.add_parser("create-daily", help="Create daily schedule")
    parser_create.add_argument("--id", required=True, help="Schedule ID")
    parser_create.add_argument("--hour", type=int, required=True, help="Hour (0-23)")
    parser_create.add_argument("--minute", type=int, required=True, help="Minute (0-59)")
    parser_create.add_argument("--timezone", type=str, default="UTC", help="Timezone (e.g. Asia/Kolkata)")
    
    # Trigger cmd
    parser_trigger = subparsers.add_parser("trigger", help="Trigger schedule immediate")
    parser_trigger.add_argument("--id", required=True, help="Schedule ID")
    
    # Delete cmd
    parser_delete = subparsers.add_parser("delete", help="Delete schedule")
    parser_delete.add_argument("--id", required=True, help="Schedule ID")
    
    args = parser.parse_args()
    manager = ScheduleManager()
    
    if args.command == "list":
        schedules = await manager.list_schedules()
        print(f"Found {len(schedules)} schedules:")
        for s in schedules:
            print(f"- {s['id']}: Next run {s['next_run']}, Paused: {s['paused']}")
            
    elif args.command == "create-daily":
        from src.workflows.daily_workflow import DailyTaskManagementWorkflow
        res = await manager.create_daily_schedule(
            schedule_id=args.id,
            workflow_id_prefix="daily-agent",
            hour=args.hour,
            minute=args.minute,
            workflow_name="DailyTaskManagementWorkflow", # String name required
            duration_minutes=15,
            timezone=args.timezone
        )
        print(res)
        
    elif args.command == "trigger":
        res = await manager.trigger_schedule(args.id)
        print(res)
        
    elif args.command == "delete":
        res = await manager.delete_schedule(args.id)
        print(res)

if __name__ == "__main__":
    asyncio.run(main())
