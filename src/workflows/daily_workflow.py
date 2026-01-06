"""
Daily task management workflow for Temporal.
Purpose: Orchestrate daily task generation, execution, and reporting using Temporal workflow engine.
"""
from temporalio import workflow
from temporalio.common import RetryPolicy
from datetime import datetime, timedelta
from typing import List, Any
import asyncio

with workflow.unsafe.imports_passed_through():
    from src.activities.workflow_activities import (
        initialize_workflow,
        get_pending_manual_tasks,
        generate_tasks,
        execute_task,
        generate_status_report,
        archive_workflow,
    )


@workflow.defn(name="DailyTaskManagementWorkflow")
class DailyTaskManagementWorkflow:
    """
    Main workflow for daily task management.
    Purpose: Coordinate task generation, execution by sub-agents, and status reporting within time window.
    """
    
    @workflow.run
    async def run(
        self,
        user_id: str,
        duration_minutes: Any = 10,
        workflow_start_time: str = None
    ) -> dict:
        """
        Execute daily task management workflow.
        
        Purpose: Main workflow execution that:
        1. Initializes workflow and database
        2. Generates tasks via main agent
        3. Executes tasks in parallel via sub-agents
        4. Generates status report
        5. Archives results
        
        Args:
            user_id: User identifier
            duration_minutes: Workflow duration (default 10 min for demo)
            workflow_start_time: Optional start time (ISO format)
        
        Returns:
            Dictionary with workflow results and status report
        """
        workflow_id = workflow.info().workflow_id
        start_time = workflow_start_time or workflow.now().isoformat()
        
        # Ensure duration_minutes is an integer
        try:
            duration_minutes = int(duration_minutes)
        except (TypeError, ValueError):
            duration_minutes = 10
            workflow.logger.warning(f"Invalid duration_minutes type {type(duration_minutes)}, defaulting to 10")
        
        # Retry policy for activities
        retry_policy = RetryPolicy(
            initial_interval=timedelta(seconds=1),
            maximum_interval=timedelta(seconds=10),
            maximum_attempts=3,
        )
        
        # Step 1: Initialize workflow
        init_result = await workflow.execute_activity(
            initialize_workflow,
            args=[workflow_id, user_id, start_time, duration_minutes],
            start_to_close_timeout=timedelta(minutes=2),
            retry_policy=retry_policy,
        )
        
        deadline = init_result["deadline"]
        
        # Step 2a: Fetch pending manual tasks from dashboard
        manual_tasks_result = await workflow.execute_activity(
            get_pending_manual_tasks,
            args=[workflow_id, user_id],
            start_to_close_timeout=timedelta(minutes=1),
            retry_policy=retry_policy,
        )
        
        manual_tasks = manual_tasks_result.get("tasks", [])
        workflow.logger.info(f"Found {len(manual_tasks)} pending manual tasks")
        
        # Step 2b: Generate additional tasks via main agent
        task_gen_result = await workflow.execute_activity(
            generate_tasks,
            args=[workflow_id, user_id, deadline],
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=retry_policy,
        )
        
        generated_tasks = task_gen_result.get("tasks", [])
        workflow.logger.info(f"Generated {len(generated_tasks)} tasks")
        
        # Combine all tasks for execution
        all_tasks = manual_tasks + [t for t in generated_tasks if t["status"] == "pending"]
        workflow.logger.info(f"Total tasks to execute: {len(all_tasks)}")
        
        # Step 3: Execute all tasks in parallel (manual + generated)
        if all_tasks:
            # Execute tasks concurrently with sub-agents
            task_executions = []
            for task in all_tasks:
                task_exec = workflow.execute_activity(
                    execute_task,
                    args=[
                        task["task_id"],
                        task["description"],
                        workflow_id,
                        user_id,
                        deadline
                    ],
                    start_to_close_timeout=timedelta(minutes=3),
                    retry_policy=retry_policy,
                )
                task_executions.append(task_exec)
            
            # Wait for all tasks to complete (or timeout based on workflow duration)
            try:
                # Calculate remaining time
                deadline_dt = datetime.fromisoformat(deadline)
                now = workflow.now()
                remaining = (deadline_dt - now).total_seconds()
                
                if remaining > 60:  # At least 1 minute remaining
                    # Give tasks time to execute, but leave time for status generation
                    execution_time = max(60, remaining - 120)  # Reserve 2 min for status
                    await asyncio.wait_for(
                        asyncio.gather(*task_executions, return_exceptions=True),
                        timeout=execution_time
                    )
                else:
                    # Not enough time, gather what we can quickly
                    await asyncio.gather(*task_executions, return_exceptions=True)
                    
            except asyncio.TimeoutError:
                workflow.logger.warning("Task execution timed out, proceeding to status generation")
        
        # Step 4: Generate status report
        status_result = await workflow.execute_activity(
            generate_status_report,
            args=[workflow_id, user_id, deadline],
            start_to_close_timeout=timedelta(minutes=2),
            retry_policy=retry_policy,
        )
        
        status_report = status_result.get("status_report", "")
        
        # Step 5: Archive workflow
        archive_result = await workflow.execute_activity(
            archive_workflow,
            args=[workflow_id],
            start_to_close_timeout=timedelta(minutes=1),
            retry_policy=retry_policy,
        )
        
        # Return final result
        return {
            "workflow_id": workflow_id,
            "user_id": user_id,
            "status": "completed",
            "tasks_generated": len(generated_tasks),
            "tasks_archived": archive_result.get("tasks_archived", 0),
            "status_report": status_report,
            "execution_time_minutes": duration_minutes
        }
