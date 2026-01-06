"""
Script to schedule and trigger workflows.
Purpose: Provides CLI interface to schedule workflows with cron or trigger them manually.
"""
import asyncio
import argparse
from datetime import datetime
from temporalio.client import Client, TLSConfig, Schedule, ScheduleActionStartWorkflow, ScheduleSpec, ScheduleIntervalSpec
from datetime import timedelta
import structlog

from src.config import settings

logger = structlog.get_logger()


async def schedule_workflow(
    user_id: str,
    cron: str = None,
    interval_minutes: int = None,
    duration_minutes: int = 10
):
    """
    Schedule a workflow with cron or interval.
    Purpose: Set up recurring workflow execution via Temporal's scheduling feature.
    """
    logger.info("scheduling_workflow", user_id=user_id, cron=cron, interval=interval_minutes)
    
    # Connect to Temporal Cloud
    client = await Client.connect(
        settings.temporal_host,
        namespace=settings.temporal_namespace,
        tls=TLSConfig(
            client_cert=None,
            client_private_key=None,
        ),
        rpc_metadata={"temporal-namespace": settings.temporal_namespace},
        api_key=settings.temporal_api_key,
    )
    
    logger.info("connected_to_temporal", host=settings.temporal_host)
    
    # Create schedule spec
    if cron:
        spec = ScheduleSpec(cron_expressions=[cron])
        schedule_id = f"daily-task-{user_id}-cron"
    elif interval_minutes:
        spec = ScheduleSpec(
            intervals=[ScheduleIntervalSpec(every=timedelta(minutes=interval_minutes))]
        )
        schedule_id = f"daily-task-{user_id}-interval-{interval_minutes}m"
    else:
        raise ValueError("Must specify either cron or interval_minutes")
    
    # Create schedule
    await client.create_schedule(
        id=schedule_id,
        schedule=Schedule(
            action=ScheduleActionStartWorkflow(
                "DailyTaskManagementWorkflow",
                args=[user_id, duration_minutes, None],
                id=f"daily-task-{user_id}-{{}}",
                task_queue="daily-task-queue",
            ),
            spec=spec,
        ),
    )
    
    logger.info(
        "workflow_scheduled",
        schedule_id=schedule_id,
        cron=cron,
        interval_minutes=interval_minutes
    )
    
    print(f"✅ Workflow scheduled: {schedule_id}")
    if cron:
        print(f"   Cron: {cron}")
    else:
        print(f"   Interval: every {interval_minutes} minutes")
    print(f"   Duration: {duration_minutes} minutes")
    print(f"\n   View in Temporal Cloud UI: https://cloud.temporal.io/namespaces/{settings.temporal_namespace}/schedules")


async def trigger_workflow_once(
    user_id: str,
    duration_minutes: int = 10
):
    """
    Trigger a single workflow execution immediately.
    Purpose: Manual workflow trigger for testing and on-demand execution.
    """
    logger.info("triggering_workflow", user_id=user_id, duration=duration_minutes)
    
    # Connect to Temporal Cloud
    client = await Client.connect(
        settings.temporal_host,
        namespace=settings.temporal_namespace,
        tls=TLSConfig(
            client_cert=None,
            client_private_key=None,
        ),
        rpc_metadata={"temporal-namespace": settings.temporal_namespace},
        api_key=settings.temporal_api_key,
    )
    
    workflow_id = f"daily-task-{user_id}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    
    # Start workflow
    handle = await client.start_workflow(
        "DailyTaskManagementWorkflow",
        args=[user_id, duration_minutes, None],
        id=workflow_id,
        task_queue="daily-task-queue",
    )
    
    logger.info("workflow_started", workflow_id=workflow_id)
    
    print(f"✅ Workflow started: {workflow_id}")
    print(f"   Duration: {duration_minutes} minutes")
    print(f"   View in Temporal Cloud UI: https://cloud.temporal.io/namespaces/{settings.temporal_namespace}/workflows/{workflow_id}")
    print(f"\n   Waiting for completion...")
    
    # Wait for result
    result = await handle.result()
    
    print(f"\n{'='*80}")
    print(f"WORKFLOW COMPLETED")
    print(f"{'='*80}")
    print(f"\nStatus Report:")
    print(result.get("status_report", "No report available"))
    print(f"\n{'='*80}")
    print(f"Summary:")
    print(f"  - Tasks Generated: {result.get('tasks_generated', 0)}")
    print(f"  - Tasks Archived: {result.get('tasks_archived', 0)}")
    print(f"  - Execution Time: {result.get('execution_time_minutes', 0)} minutes")
    print(f"{'='*80}\n")


async def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(description="Schedule or trigger Temporal workflows")
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    
    # Schedule command
    schedule_parser = subparsers.add_parser("schedule", help="Schedule recurring workflow")
    schedule_parser.add_argument("--user_id", required=True, help="User ID")
    schedule_parser.add_argument("--cron", help="Cron expression (e.g., '0 8 * * *' for 8am daily)")
    schedule_parser.add_argument("--interval", type=int, help="Interval in minutes")
    schedule_parser.add_argument("--duration", type=int, default=10, help="Workflow duration in minutes")
    
    # Run command (manual trigger)
    run_parser = subparsers.add_parser("run", help="Run workflow once immediately")
    run_parser.add_argument("--user_id", default="default_user", help="User ID")
    run_parser.add_argument("--duration", type=int, default=10, help="Workflow duration in minutes")
    
    args = parser.parse_args()
    
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer()
        ]
    )
    
    if args.command == "schedule":
        if not args.cron and not args.interval:
            print("Error: Must specify either --cron or --interval")
            return
        await schedule_workflow(
            user_id=args.user_id,
            cron=args.cron,
            interval_minutes=args.interval,
            duration_minutes=args.duration
        )
    elif args.command == "run":
        await trigger_workflow_once(
            user_id=args.user_id,
            duration_minutes=args.duration
        )
    else:
        parser.print_help()


if __name__ == "__main__":
    asyncio.run(main())
