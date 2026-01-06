"""
FastAPI backend for task management dashboard.
Purpose: Provide REST API and WebSocket support for real-time task monitoring and management.
"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import asyncio
import json
import structlog

from src.database.operations import DatabaseOperations
from src.config import settings

logger = structlog.get_logger()

app = FastAPI(title="Temporal Agent Task Dashboard")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database instance
db_ops = DatabaseOperations(settings.database_path)

# WebSocket connections for real-time updates
active_connections: List[WebSocket] = []


# Pydantic models for API
class TaskCreate(BaseModel):
    description: str
    workflow_id: Optional[str] = None


class TaskUpdate(BaseModel):
    description: Optional[str] = None
    status: Optional[str] = None


class SkillCreate(BaseModel):
    name: str
    content: str


class MCPConfig(BaseModel):
    config: str  # JSON string


class EnvConfig(BaseModel):
    key: str
    value: str


# WebSocket manager
class ConnectionManager:
    """Manages WebSocket connections for real-time updates"""
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info("websocket_connected", total_connections=len(self.active_connections))
    
    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
        logger.info("websocket_disconnected", total_connections=len(self.active_connections))
    
    async def broadcast(self, message: dict):
        """Broadcast message to all connected clients"""
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error("broadcast_error", error=str(e))


manager = ConnectionManager()


# API Endpoints

@app.on_event("startup")
async def startup():
    """Initialize database on startup"""
    await db_ops.initialize()
    logger.info("api_started")


@app.get("/")
async def get_dashboard():
    """Serve the dashboard HTML"""
    html_path = Path(__file__).parent / "frontend" / "index.html"
    with open(html_path, "r") as f:
        html_content = f.read()
    return HTMLResponse(content=html_content)


@app.get("/api/tasks")
async def get_tasks(
    workflow_id: Optional[str] = None,
    user_id: Optional[str] = None,
    status: Optional[str] = None
):
    """Get tasks with optional filters, including recent history"""
    # Active tasks
    tasks = await db_ops.get_tasks(
        workflow_id=workflow_id,
        user_id=user_id,
        status=status
    )
    
    # Fetch recent history (last 24h) to show completed workflow tasks
    # We always include this to fix UI visibility for archived tasks
    if not status or status in ["completed", "failed"]:
        history = await db_ops.get_task_history(
             user_id=user_id or settings.default_user_id,
             days=1
        )
        # Apply in-memory filter for workflow_id if needed
        if workflow_id:
            history = [t for t in history if t.get("workflow_id") == workflow_id]
            
        tasks.extend(history)
        
    return {"tasks": tasks, "count": len(tasks)}


@app.get("/api/tasks/{task_id}")
async def get_task(task_id: str):
    """Get a single task by ID"""
    task = await db_ops.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@app.post("/api/tasks")
async def create_task(task: TaskCreate):
    """Create a new task"""
    import uuid
    from datetime import datetime
    
    task_id = f"task_{uuid.uuid4().hex[:8]}"
    workflow_id = task.workflow_id or "manual"
    
    created_task = await db_ops.create_task(
        task_id=task_id,
        user_id=settings.default_user_id,
        workflow_id=workflow_id,
        description=task.description,
        status="pending"
    )
    
    # Broadcast update
    await manager.broadcast({
        "type": "task_created",
        "task": created_task
    })
    
    return created_task


@app.put("/api/tasks/{task_id}")
async def update_task(task_id: str, update: TaskUpdate):
    """Update a task"""
    # Get existing task
    existing = await db_ops.get_task(task_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Update task
    if update.status:
        await db_ops.update_task_status(
            task_id=task_id,
            status=update.status
        )
    
    # Get updated task
    updated_task = await db_ops.get_task(task_id)
    
    # Broadcast update
    await manager.broadcast({
        "type": "task_updated",
        "task": updated_task
    })
    
    return updated_task


@app.delete("/api/tasks/{task_id}")
async def delete_task(task_id: str):
    """Delete a pending task"""
    await db_ops.delete_task(task_id)
    
    # Broadcast update
    await manager.broadcast({
        "type": "task_deleted",
        "task_id": task_id
    })
    
    return {"status": "deleted", "task_id": task_id}


@app.get("/api/workflows")
async def get_workflows(user_id: Optional[str] = None):
    """Get all workflows"""
    # This is a simplified version - you could add more filtering
    import aiosqlite
    
    async with aiosqlite.connect(settings.database_path) as db:
        db.row_factory = aiosqlite.Row
        query = "SELECT * FROM workflows ORDER BY start_time DESC LIMIT 50"
        params = []
        
        if user_id:
            query = "SELECT * FROM workflows WHERE user_id = ? ORDER BY start_time DESC LIMIT 50"
            params = [user_id]
        
        async with db.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            workflows = [dict(row) for row in rows]
    
    return {"workflows": workflows, "count": len(workflows)}


@app.get("/api/history")
async def get_history(user_id: Optional[str] = None, days: int = 7):
    """Get task history"""
    history = await db_ops.get_task_history(
        user_id=user_id or settings.default_user_id,
        days=days
    )
    return {"history": history, "count": len(history)}


@app.post("/api/trigger-workflow")
async def trigger_workflow(duration_minutes: int = 5):
    """Trigger a new workflow execution"""
    import subprocess
    from datetime import datetime
    
    workflow_id = f"daily-task-{settings.default_user_id}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    
    # Start workflow in background
    try:
        subprocess.Popen(
            [
                sys.executable,
                str(Path(__file__).parent.parent.parent / "run_workflow.py"),
                "run",
                f"--user_id={settings.default_user_id}",
                f"--duration={duration_minutes}"
            ],
            cwd=str(Path(__file__).parent.parent.parent),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        return {"status": "started", "workflow_id": workflow_id, "duration_minutes": duration_minutes}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/tasks/{task_id}/execute")
async def execute_single_task(task_id: str):
    """
    Execute a single task immediately using a sub-agent.
    Purpose: Allow users to run individual tasks without triggering a full workflow.
    """
    from datetime import datetime, timedelta
    
    # Get the task
    task = await db_ops.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if task["status"] != "pending":
        raise HTTPException(status_code=400, detail=f"Task is not pending (status: {task['status']})")
    
    # Update task status to in_progress
    await db_ops.update_task_status(task_id, "in_progress", assigned_to="manual_executor")
    
    # Broadcast update
    await manager.broadcast({
        "type": "task_updated",
        "task": await db_ops.get_task(task_id)
    })
    
    # Execute task in background
    import asyncio
    asyncio.create_task(run_single_task_execution(task_id, task["description"]))
    
    return {"status": "started", "task_id": task_id, "message": "Task execution started"}


async def run_single_task_execution(task_id: str, description: str):
    """
    Background task execution using E2B Claude Code Sandbox.
    Purpose: Execute manual tasks in isolated E2B sandbox with file sync.
    """
    import os
    from datetime import datetime
    from src.agents.e2b_tool import ClaudeCodeSandbox
    
    try:
        # Update task status to in_progress
        await db_ops.update_task_status(task_id, "in_progress")
        
        # Broadcast update
        await manager.broadcast({
            "type": "task_updated",
            "task": await db_ops.get_task(task_id)
        })
        
        logger.info("starting_e2b_sandbox_execution", task_id=task_id, description=description[:100])
        
        # Create sandbox and execute prompt
        sandbox = ClaudeCodeSandbox()
        result = await sandbox.execute_prompt(
            prompt=description,
            task_id=task_id,
            timeout_seconds=300
        )
        
        # Determine final status
        if result.get("success"):
            status = "completed"
            error_msg = None
            output = result.get("stdout", "")
            synced_files = result.get("synced_files", [])
            if synced_files:
                output += f"\n\n**Synced Files:** {', '.join(synced_files)}"
        else:
            status = "failed"
            error_msg = result.get("stderr") or "Unknown error"
            output = result.get("stdout", "")
        
        # Update task in database
        await db_ops.update_task_status(
            task_id=task_id,
            status=status,
            output=output[:10000] if output else None,  # Truncate if too long
            error_message=error_msg
        )
        
        logger.info("e2b_sandbox_task_completed", 
                   task_id=task_id, 
                   status=status,
                   synced_files=result.get("synced_files", []))
        
    except Exception as e:
        await db_ops.update_task_status(
            task_id=task_id,
            status="failed",
            error_message=str(e)
        )
        logger.error("e2b_sandbox_task_error", task_id=task_id, error=str(e))
    
    # Broadcast final update
    updated_task = await db_ops.get_task(task_id)
    await manager.broadcast({
        "type": "task_updated",
        "task": updated_task
    })

# Schedule Endpoints
@app.get("/api/schedules")
async def list_schedules():
    """List all active schedules"""
    try:
        from src.workflows.schedules import ScheduleManager
        manager = ScheduleManager()
        schedules = await manager.list_schedules()
        return {"schedules": schedules}
    except Exception as e:
        logger.error("list_schedules_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/schedules/{schedule_id}/trigger")
async def trigger_schedule(schedule_id: str):
    """Trigger a schedule immediately"""
    try:
        from src.workflows.schedules import ScheduleManager
        manager = ScheduleManager()
        result = await manager.trigger_schedule(schedule_id)
        if not result["success"]:
            raise Exception(result.get("error"))
        return {"status": "triggered", "schedule_id": schedule_id}
    except Exception as e:
        logger.error("trigger_schedule_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket Endpoint for real-time updates"""
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive and listen for any client messages
            data = await websocket.receive_text()
            # Echo back for now (could handle client commands here)
            await websocket.send_json({"type": "pong", "message": "connected"})
    except WebSocketDisconnect:
        manager.disconnect(websocket)


# Background task to periodically check for updates
@app.on_event("startup")
async def start_background_tasks():
    """Start background task for periodic updates"""
    asyncio.create_task(periodic_task_check())


# Track last state to avoid redundant broadcasts
last_tasks_state = None

async def periodic_task_check():
    """Periodically check for task updates and broadcast"""
    global last_tasks_state
    while True:
        await asyncio.sleep(5)  # Check every 5 seconds
        
        # Get recent tasks
        tasks = await db_ops.get_tasks()
        
        # Create a light state hash to check for changes
        current_state = [(t["task_id"], t["status"]) for t in tasks]
        
        if last_tasks_state != current_state:
            last_tasks_state = current_state
            # Broadcast to all clients
            await manager.broadcast({
                "type": "tasks_refresh",
                "tasks": tasks,
                "count": len(tasks)
            })


# Configuration API Endpoints

@app.get("/api/skills")
async def list_skills():
    """List all available skills"""
    import os
    
    skills_dir = Path(__file__).parent.parent.parent / ".claude" / "skills"
    skills = []
    
    if skills_dir.exists():
        for skill_path in skills_dir.iterdir():
            if skill_path.is_dir() and (skill_path / "SKILL.md").exists():
                with open(skill_path / "SKILL.md", "r") as f:
                    content = f.read()
                skills.append({
                    "name": skill_path.name,
                    "content": content
                })
                
    return {"skills": skills}


@app.post("/api/skills")
async def create_update_skill(skill: SkillCreate):
    """Create or update a skill"""
    skills_dir = Path(__file__).parent.parent.parent / ".claude" / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)
    
    skill_path = skills_dir / skill.name
    skill_path.mkdir(exist_ok=True)
    
    with open(skill_path / "SKILL.md", "w") as f:
        f.write(skill.content)
        
    return {"status": "success", "name": skill.name}


@app.get("/api/mcps")
async def get_mcp_config():
    """Get MCP configuration"""
    config_path = Path(__file__).parent.parent.parent / "mcp_config.json"
    
    if config_path.exists():
        with open(config_path, "r") as f:
            content = f.read()
        return {"config": content}
    
    return {"config": "{}"}


@app.post("/api/mcps")
async def update_mcp_config(config: MCPConfig):
    """Update MCP configuration"""
    config_path = Path(__file__).parent.parent.parent / "mcp_config.json"
    
    try:
        # Validate that it's valid JSON
        json.loads(config.config)
        
        with open(config_path, "w") as f:
            f.write(config.config)
            
        return {"status": "success"}
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON format")


@app.get("/api/env")
async def get_env_vars():
    """Get environment variables (filtered for safety)"""
    env_path = Path(__file__).parent.parent.parent / ".env"
    env_vars = {}
    
    if env_path.exists():
        with open(env_path, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    env_vars[key.strip()] = value.strip()
                    
    return {"env": env_vars}


@app.post("/api/env")
async def update_env_vars(config: EnvConfig):
    """Update an environment variable"""
    env_path = Path(__file__).parent.parent.parent / ".env"
    lines = []
    
    # Read existing
    if env_path.exists():
        with open(env_path, "r") as f:
            lines = f.readlines()
            
    # Check if key exists and update
    found = False
    for i, line in enumerate(lines):
        if line.strip().startswith(f"{config.key}="):
            lines[i] = f"{config.key}={config.value}\n"
            found = True
            break
            
    if not found:
        # Ensure newline before appending if file not empty and no newline at end
        if lines and not lines[-1].endswith('\n'):
            lines[-1] += '\n'
        lines.append(f"{config.key}={config.value}\n")
        
    with open(env_path, "w") as f:
        f.writelines(lines)
        
    # Reload settings/restart might be needed for some apps, but for now just updating file
    return {"status": "success", "key": config.key}


# Task Output Files API
@app.get("/api/tasks/{task_id}/files")
async def get_task_files(task_id: str):
    """
    List files generated by a task.
    Purpose: Allow frontend to retrieve and display task output files.
    """
    import os
    output_dir = Path(__file__).parent.parent.parent / "output" / task_id
    
    if not output_dir.exists():
        return {"files": [], "output_dir": str(output_dir)}
    
    files = []
    for f in output_dir.iterdir():
        if f.is_file():
            files.append({
                "name": f.name,
                "size": f.stat().st_size,
                "url": f"/api/tasks/{task_id}/files/{f.name}"
            })
    
    return {"files": files, "output_dir": str(output_dir)}


@app.get("/api/tasks/{task_id}/files/{filename}")
async def get_task_file(task_id: str, filename: str):
    """
    Serve a specific task output file.
    Purpose: Allow frontend to download/display task-generated files.
    """
    from fastapi.responses import FileResponse
    
    output_dir = Path(__file__).parent.parent.parent / "output" / task_id
    file_path = output_dir / filename
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    
    return FileResponse(file_path, filename=filename)


# Serve static files (CSS, JS)
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "frontend"), name="static")


if __name__ == "__main__":
    import uvicorn
    
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer()
        ]
    )
    
    uvicorn.run(
        app,
        host=settings.api_host,
        port=settings.api_port,
        log_level="info"
    )
