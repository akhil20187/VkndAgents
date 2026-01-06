"""
Agent tools for task management and database interaction.
Purpose: Provide tools that agents can use to interact with tasks, query history, and manage state.
"""
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
import uuid
import structlog
from contextvars import ContextVar
from pydantic import BaseModel, Field
from claude_agent_sdk import tool

logger = structlog.get_logger()

# Context Variables for tool execution context
# Purpose: Pass runtime context (DB, User, Workflow) to static tool functions
ctx_db_ops = ContextVar("db_ops", default=None)
ctx_workflow_id = ContextVar("workflow_id", default=None)
ctx_user_id = ContextVar("user_id", default=None)
ctx_workflow_deadline = ContextVar("workflow_deadline", default=None)

class AgentContext:
    """Context manager for setting up tool execution context"""
    def __init__(self, db_ops, workflow_id: str, user_id: str, workflow_deadline: datetime):
        self.db_ops = db_ops
        self.workflow_id = workflow_id
        self.user_id = user_id
        self.workflow_deadline = workflow_deadline
        self.tokens = []

    def __enter__(self):
        self.tokens.append(ctx_db_ops.set(self.db_ops))
        self.tokens.append(ctx_workflow_id.set(self.workflow_id))
        self.tokens.append(ctx_user_id.set(self.user_id))
        self.tokens.append(ctx_workflow_deadline.set(self.workflow_deadline))
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        for token in reversed(self.tokens):
            # We need to match the correct context var to reset, but simple popping works 
            # if we are careful. Actually ContextVar.reset() needs the specific token.
            # Let's do it cleanly.
            pass
        
        # Proper reset
        ctx_workflow_deadline.reset(self.tokens.pop())
        ctx_user_id.reset(self.tokens.pop())
        ctx_workflow_id.reset(self.tokens.pop())
        ctx_db_ops.reset(self.tokens.pop())


# --- Input Models ---

class CreateTaskInput(BaseModel):
    description: str = Field(..., description="Clear description of what the task should accomplish")

class UpdateTaskStatusInput(BaseModel):
    task_id: str = Field(..., description="ID of the task to update")
    status: str = Field(..., description="New status for the task", pattern="^(pending|in_progress|completed|failed)$")
    output: Optional[str] = Field(None, description="Optional output or result from the task")
    error_message: Optional[str] = Field(None, description="Optional error message if task failed")

class QueryTasksInput(BaseModel):
    status: Optional[str] = Field(None, description="Optional: filter tasks by status", pattern="^(generated|pending|in_progress|completed|failed)$")

class QueryHistoryInput(BaseModel):
    days: int = Field(7, description="Number of days of history to retrieve (default: 7)")

class LogMessageInput(BaseModel):
    message: str = Field(..., description="The message to log")
    level: str = Field("info", description="Log level (info, warning, error)")

class EmptyInput(BaseModel):
    pass


# --- Tool Implementations ---

@tool("create_task", input_schema=CreateTaskInput, description="Create a new task with a description. The task will be added to the pending queue.")
async def create_task(input: CreateTaskInput) -> Dict[str, Any]:
    db_ops = ctx_db_ops.get()
    workflow_id = ctx_workflow_id.get()
    user_id = ctx_user_id.get()
    
    task_id = f"task_{uuid.uuid4().hex[:8]}"
    
    await db_ops.create_task(
        task_id=task_id,
        user_id=user_id,
        workflow_id=workflow_id,
        description=input.description,
        status="pending"
    )
    
    return {
        "success": True,
        "task_id": task_id,
        "description": input.description,
        "status": "pending"
    }

@tool("update_task_status", input_schema=UpdateTaskStatusInput, description="Update the status of a task. Use this to mark tasks as in_progress, completed, or failed.")
async def update_task_status(input: UpdateTaskStatusInput) -> Dict[str, Any]:
    db_ops = ctx_db_ops.get()
    
    task = await db_ops.get_task(input.task_id)
    if not task:
        return {"success": False, "error": "Task not found"}
    
    await db_ops.update_task_status(
        task_id=input.task_id,
        status=input.status,
        output=input.output,
        error_message=input.error_message
    )
    
    return {
        "success": True,
        "task_id": input.task_id,
        "status": input.status
    }

@tool("query_tasks", input_schema=QueryTasksInput, description="Query tasks by status or get all tasks for the current workflow.")
async def query_tasks(input: QueryTasksInput) -> Dict[str, Any]:
    db_ops = ctx_db_ops.get()
    workflow_id = ctx_workflow_id.get()
    
    tasks = await db_ops.get_tasks(
        workflow_id=workflow_id,
        status=input.status
    )
    
    return {
        "success": True,
        "tasks": tasks,
        "count": len(tasks)
    }

@tool("query_history", input_schema=QueryHistoryInput, description="Query historical tasks from previous days.")
async def query_history(input: QueryHistoryInput) -> Dict[str, Any]:
    db_ops = ctx_db_ops.get()
    user_id = ctx_user_id.get()
    
    history = await db_ops.get_task_history(
        user_id=user_id,
        days=input.days
    )
    
    return {
        "success": True,
        "history": history,
        "count": len(history)
    }

@tool("get_current_time", input_schema=EmptyInput, description="Get the current time and check how much time remains until the workflow deadline.")
async def get_current_time(input: EmptyInput) -> Dict[str, Any]:
    deadline_val = ctx_workflow_deadline.get()
    
    now = datetime.now(timezone.utc)
    if deadline_val.tzinfo is None:
        deadline = deadline_val.replace(tzinfo=timezone.utc)
    else:
        deadline = deadline_val
        
    time_remaining = (deadline - now).total_seconds() / 60
    
    return {
        "success": True,
        "current_time": now.isoformat(),
        "workflow_deadline": deadline.isoformat(),
        "time_remaining_minutes": round(time_remaining, 1)
    }

@tool("log_message", input_schema=LogMessageInput, description="Log an informational message.")
async def log_message(input: LogMessageInput) -> Dict[str, Any]:
    workflow_id = ctx_workflow_id.get()
    
    if input.level == "info":
        logger.info("agent_log", message=input.message, workflow_id=workflow_id)
    elif input.level == "warning":
        logger.warning("agent_log", message=input.message, workflow_id=workflow_id)
    elif input.level == "error":
        logger.error("agent_log", message=input.message, workflow_id=workflow_id)
        
    return {"success": True, "logged": True}

# List of all tools
ALL_AGENT_TOOLS = [
    create_task,
    update_task_status,
    query_tasks,
    query_history,
    get_current_time,
    log_message
]
