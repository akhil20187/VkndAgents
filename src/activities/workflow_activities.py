"""
Temporal workflow activities for the daily task management system.
Purpose: Define activities that can be executed by Temporal workflows, including agent execution and database operations.
"""
from temporalio import activity
from datetime import datetime, timedelta
from typing import Dict, Any
import asyncio
import structlog

from src.database.operations import DatabaseOperations
from src.agents.main_agent import MainAgent
from src.agents.sub_agent import SubAgent
from src.config import settings

logger = structlog.get_logger()


@activity.defn(name="initialize_workflow_activity")
async def initialize_workflow(
    workflow_id: str,
    user_id: str,
    start_time: str,
    duration_minutes: int
) -> Dict[str, Any]:
    """
    Initialize workflow with database and agent setup.
    Purpose: Set up workflow context, create database records, and prepare for task generation.
    """
    logger.info("activity_initialize_workflow", workflow_id=workflow_id)
    
    # Initialize database
    db_ops = DatabaseOperations(settings.database_path)
    await db_ops.initialize()
    
    # Create workflow record
    start_dt = datetime.fromisoformat(start_time)
    await db_ops.create_workflow(
        workflow_id=workflow_id,
        user_id=user_id,
        start_time=start_dt,
        main_agent_id=f"main_agent_{workflow_id}"
    )
    
    logger.info("workflow_initialized", workflow_id=workflow_id, duration=duration_minutes)
    
    return {
        "workflow_id": workflow_id,
        "user_id": user_id,
        "start_time": start_time,
        "duration_minutes": duration_minutes,
        "deadline": (start_dt + timedelta(minutes=duration_minutes)).isoformat()
    }


@activity.defn(name="get_pending_manual_tasks_activity")
async def get_pending_manual_tasks(
    workflow_id: str,
    user_id: str
) -> Dict[str, Any]:
    """
    Get pending tasks created manually via the dashboard.
    Purpose: Fetch tasks with workflow_id='manual' that need to be executed.
    """
    logger.info("activity_get_manual_tasks", workflow_id=workflow_id)
    
    db_ops = DatabaseOperations(settings.database_path)
    
    # Get all pending manual tasks
    tasks = await db_ops.get_tasks(workflow_id="manual", status="pending")
    
    # Associate them with this workflow
    for task in tasks:
        await db_ops.update_task_workflow(task["task_id"], workflow_id)
    
    logger.info("manual_tasks_found", count=len(tasks))
    
    return {
        "tasks": tasks,
        "count": len(tasks)
    }

@activity.defn(name="generate_tasks_activity")
async def generate_tasks(
    workflow_id: str,
    user_id: str,
    deadline: str
) -> Dict[str, Any]:
    """
    Main agent generates daily tasks.
    Purpose: Use main agent to autonomously create tasks for the workflow.
    """
    logger.info("activity_generate_tasks", workflow_id=workflow_id)
    
    # Set up database
    db_ops = DatabaseOperations(settings.database_path)
    
    # Create and run main agent
    main_agent = MainAgent(
        workflow_id=workflow_id,
        user_id=user_id,
        workflow_deadline=deadline,
        db_ops=db_ops
    )
    
    result = await main_agent.generate_tasks()
    
    # Get all generated tasks
    tasks = await db_ops.get_tasks(workflow_id=workflow_id)
    
    logger.info(
        "tasks_generated",
        workflow_id=workflow_id,
        task_count=len(tasks)
    )
    
    return {
        "workflow_id": workflow_id,
        "tasks_generated": len(tasks),
        "tasks": tasks,
        "agent_result": result
    }


@activity.defn(name="execute_task_activity")
async def execute_task(
    task_id: str,
    task_description: str,
    workflow_id: str,
    user_id: str,
    deadline: str
) -> Dict[str, Any]:
    """
    Execute a single task using a sub-agent.
    Purpose: Spawn sub-agent to complete a specific task.
    """
    logger.info("activity_execute_task", task_id=task_id, workflow_id=workflow_id)
    
    # Set up database
    db_ops = DatabaseOperations(settings.database_path)
    
    # Create and run sub-agent
    try:
        sub_agent = SubAgent(
            task_id=task_id,
            task_description=task_description,
            workflow_id=workflow_id,
            user_id=user_id,
            workflow_deadline=deadline,
            db_ops=db_ops
        )
        
        result = await sub_agent.execute_task()
    except Exception as e:
        logger.error("sub_agent_error", task_id=task_id, error=str(e))
        result = {"error": str(e)}
        # Ensure failed status is recorded if sub-agent crashed before doing so
        try:
            await db_ops.update_task_status(task_id, "failed", error_message=str(e))
        except:
            pass
    
    # Get final task status
    task = await db_ops.get_task(task_id)
    
    logger.info(
        "task_executed",
        task_id=task_id,
        final_status=task.get("status") if task else "unknown"
    )
    
    return {
        "task_id": task_id,
        "workflow_id": workflow_id,
        "agent_result": result,
        "task_status": task
    }


@activity.defn(name="generate_status_report_activity")
async def generate_status_report(
    workflow_id: str,
    user_id: str,
    deadline: str
) -> Dict[str, Any]:
    """
    Generate final status report using main agent.
    Purpose: Create comprehensive summary of workflow execution.
    """
    logger.info("activity_generate_status", workflow_id=workflow_id)
    
    # Set up database
    db_ops = DatabaseOperations(settings.database_path)
    
    # Create main agent and generate report
    main_agent = MainAgent(
        workflow_id=workflow_id,
        user_id=user_id,
        workflow_deadline=deadline,
        db_ops=db_ops
    )
    
    status_report = await main_agent.generate_status_report()
    
    logger.info("status_report_generated", workflow_id=workflow_id)
    
    return {
        "workflow_id": workflow_id,
        "status_report": status_report,
        "timestamp": datetime.now().isoformat()
    }


@activity.defn(name="archive_workflow_activity")
async def archive_workflow(
    workflow_id: str
) -> Dict[str, Any]:
    """
    Archive workflow tasks to history.
    Purpose: Move completed tasks to history table for future reference.
    """
    logger.info("activity_archive_workflow", workflow_id=workflow_id)
    
    db_ops = DatabaseOperations(settings.database_path)
    
    # Archive tasks
    count = await db_ops.archive_tasks(workflow_id)
    
    # Update workflow status
    await db_ops.update_workflow_status(
        workflow_id=workflow_id,
        status="completed",
        end_time=datetime.now()
    )
    
    logger.info("workflow_archived", workflow_id=workflow_id, tasks_archived=count)
    
    return {
        "workflow_id": workflow_id,
        "tasks_archived": count
    }


@activity.defn(name="run_agent_sdk_task_activity")
async def run_agent_sdk_task(
    task_id: str,
    task_description: str,
    workflow_id: str,
    user_id: str,
    use_skills: bool = True,
    allowed_tools: list = None
) -> Dict[str, Any]:
    """
    Execute a task using Claude Agent SDK subprocess.
    Purpose: Run tasks with full Agent SDK capabilities (file ops, bash, web search, skills).
    This provides hybrid integration - Temporal orchestrates, Agent SDK executes.
    """
    import subprocess
    import json
    import os
    
    logger.info("activity_run_agent_sdk_task", 
               task_id=task_id, 
               workflow_id=workflow_id)
    
    # Update task status to in_progress
    db_ops = DatabaseOperations(settings.database_path)
    await db_ops.update_task_status(task_id, "in_progress")
    
    # Build command
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    runner_path = os.path.join(project_root, "src", "agents", "agent_runner.py")
    python_path = os.path.join(project_root, "venv", "bin", "python")
    
    cmd = [
        python_path,
        runner_path,
        "--prompt", task_description,
        "--cwd", project_root,
        "--permission-mode", "acceptEdits",
        "--json"
    ]
    
    if not use_skills:
        cmd.append("--no-skills")
    
    if allowed_tools:
        cmd.extend(["--tools", ",".join(allowed_tools)])
    
    try:
        # Run agent subprocess with timeout
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,  # 5 minute timeout
            cwd=project_root,
            env={**os.environ, "ANTHROPIC_API_KEY": settings.anthropic_api_key}
        )
        
        # Parse JSON output
        try:
            output_data = json.loads(result.stdout)
        except json.JSONDecodeError:
            output_data = {
                "status": "success" if result.returncode == 0 else "error",
                "output": result.stdout,
                "error": result.stderr if result.returncode != 0 else None
            }
        
        # Determine final status
        if output_data.get("error") or result.returncode != 0:
            status = "failed"
            error_msg = output_data.get("error") or result.stderr
            output = output_data.get("output", "")
        else:
            status = "completed"
            error_msg = None
            output = output_data.get("output", "")
        
        # Update task in database
        await db_ops.update_task_status(
            task_id=task_id,
            status=status,
            output=output[:10000] if output else None,  # Truncate if too long
            error_message=error_msg
        )
        
        logger.info("agent_sdk_task_completed", 
                   task_id=task_id, 
                   status=status,
                   tool_calls=len(output_data.get("tool_calls", [])))
        
        return {
            "task_id": task_id,
            "status": status,
            "output": output,
            "tool_calls": output_data.get("tool_calls", []),
            "error": error_msg
        }
        
    except subprocess.TimeoutExpired:
        await db_ops.update_task_status(
            task_id=task_id,
            status="failed",
            error_message="Task execution timed out after 5 minutes"
        )
        logger.error("agent_sdk_task_timeout", task_id=task_id)
        return {
            "task_id": task_id,
            "status": "failed",
            "error": "Timeout after 5 minutes"
        }
        
    except Exception as e:
        await db_ops.update_task_status(
            task_id=task_id,
            status="failed",
            error_message=str(e)
        )
        logger.error("agent_sdk_task_error", task_id=task_id, error=str(e))
        return {
            "task_id": task_id,
            "status": "failed",
            "error": str(e)
        }

