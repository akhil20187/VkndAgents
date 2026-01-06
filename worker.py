"""
Temporal worker for running workflow and activity tasks.
Purpose: Worker process that executes workflows and activities, connecting to Temporal Cloud.
"""
import asyncio
import sys
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from temporalio.client import Client, TLSConfig
from temporalio.worker import Worker
import structlog

from src.config import settings
from src.workflows.daily_workflow import DailyTaskManagementWorkflow
from src.activities.workflow_activities import (
    initialize_workflow,
    get_pending_manual_tasks,
    generate_tasks,
    execute_task,
    generate_status_report,
    archive_workflow,
)

logger = structlog.get_logger()


async def main():
    """
    Start the Temporal worker.
    Purpose: Connect to Temporal Cloud and process workflow/activity tasks.
    """
    logger.info("worker_starting", namespace=settings.temporal_namespace)
    
    # Connect to Temporal Cloud
    client = await Client.connect(
        settings.temporal_host,
        namespace=settings.temporal_namespace,
        tls=TLSConfig(
            # Temporal Cloud uses API key authentication
            client_cert=None,
            client_private_key=None,
        ),
        rpc_metadata={"temporal-namespace": settings.temporal_namespace},
        api_key=settings.temporal_api_key,
    )
    
    logger.info("connected_to_temporal", host=settings.temporal_host)
    
    # Create worker
    worker = Worker(
        client,
        task_queue="daily-task-queue",
        workflows=[DailyTaskManagementWorkflow],
        activities=[
            initialize_workflow,
            get_pending_manual_tasks,
            generate_tasks,
            execute_task,
            generate_status_report,
            archive_workflow,
        ],
    )
    
    logger.info("worker_started", task_queue="daily-task-queue")
    
    # Run worker
    await worker.run()


if __name__ == "__main__":
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer()
        ]
    )
    
    asyncio.run(main())
