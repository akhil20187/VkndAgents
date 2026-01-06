"""
Database operations for Temporal + Claude Agent system.
Purpose: Provide async interface for all database operations including tasks, workflows, and agent state management.
"""
import aiosqlite
import json
from datetime import datetime
from typing import List, Dict, Optional, Any
from pathlib import Path
import structlog

logger = structlog.get_logger()


class DatabaseOperations:
    """Handles all database operations for the system"""
    
    def __init__(self, db_path: str):
        """Initialize database operations with path to SQLite database"""
        self.db_path = db_path
        
    async def initialize(self):
        """Initialize database schema from SQL file"""
        schema_path = Path(__file__).parent / "schema.sql"
        
        async with aiosqlite.connect(self.db_path) as db:
            with open(schema_path, 'r') as f:
                schema_sql = f.read()
            await db.executescript(schema_sql)
            await db.commit()
            
        logger.info("database_initialized", db_path=self.db_path)
    
    # Task Operations
    
    async def create_task(
        self,
        task_id: str,
        user_id: str,
        workflow_id: str,
        description: str,
        status: str = "generated"
    ) -> Dict[str, Any]:
        """Create a new task in the database"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO tasks (task_id, user_id, workflow_id, description, status)
                VALUES (?, ?, ?, ?, ?)
                """,
                (task_id, user_id, workflow_id, description, status)
            )
            await db.commit()
            
        logger.info("task_created", task_id=task_id, workflow_id=workflow_id)
        return {
            "task_id": task_id,
            "user_id": user_id,
            "workflow_id": workflow_id,
            "description": description,
            "status": status
        }
    
    async def update_task_status(
        self,
        task_id: str,
        status: str,
        assigned_to: Optional[str] = None,
        output: Optional[str] = None,
        error_message: Optional[str] = None
    ) -> None:
        """Update task status and related fields"""
        async with aiosqlite.connect(self.db_path) as db:
            # Build dynamic update query based on provided fields
            fields = ["status = ?"]
            values = [status]
            
            if assigned_to is not None:
                fields.append("assigned_to = ?")
                values.append(assigned_to)
            
            if status == "in_progress" and assigned_to:
                fields.append("start_time = CURRENT_TIMESTAMP")
                
            if status in ["completed", "failed"]:
                fields.append("end_time = CURRENT_TIMESTAMP")
                
            if output is not None:
                fields.append("output = ?")
                values.append(output)
                
            if error_message is not None:
                fields.append("error_message = ?")
                values.append(error_message)
                
            values.append(task_id)
            
            query = f"UPDATE tasks SET {', '.join(fields)} WHERE task_id = ?"
            await db.execute(query, values)
            await db.commit()
            
        logger.info("task_updated", task_id=task_id, status=status)
    
    async def get_tasks(
        self,
        workflow_id: Optional[str] = None,
        user_id: Optional[str] = None,
        status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Query tasks with optional filters"""
        query = "SELECT * FROM tasks WHERE 1=1"
        params = []
        
        if workflow_id:
            query += " AND workflow_id = ?"
            params.append(workflow_id)
        
        if user_id:
            query += " AND user_id = ?"
            params.append(user_id)
            
        if status:
            query += " AND status = ?"
            params.append(status)
        
        query += " ORDER BY created_at DESC"
        
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(query, params) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
    
    async def get_tasks_for_workflow(
        self,
        workflow_id: str,
        status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get all tasks for a specific workflow, optionally filtered by status.
        Purpose: Dedicated method for agent task queries.
        """
        return await self.get_tasks(workflow_id=workflow_id, status=status)

    async def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get a single task by ID"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None
    
    async def update_task_workflow(self, task_id: str, workflow_id: str) -> None:
        """Update the workflow_id for a task (used when manual tasks are picked up by a workflow)"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE tasks SET workflow_id = ? WHERE task_id = ?",
                (workflow_id, task_id)
            )
            await db.commit()
        
        logger.info("task_workflow_updated", task_id=task_id, workflow_id=workflow_id)
    
    async def delete_task(self, task_id: str) -> None:
        """Delete a task (from active tasks or history)"""
        async with aiosqlite.connect(self.db_path) as db:
            # Delete from active tasks (restricted to pending)
            await db.execute("DELETE FROM tasks WHERE task_id = ? AND status = 'pending'", (task_id,))
            
            # Delete from history (if it exists there, e.g. archived pending tasks)
            await db.execute("DELETE FROM task_history WHERE task_id = ?", (task_id,))
            
            await db.commit()
        
        logger.info("task_deleted", task_id=task_id)
    
    # Workflow Operations
    
    async def create_workflow(
        self,
        workflow_id: str,
        user_id: str,
        start_time: datetime,
        main_agent_id: str
    ) -> Dict[str, Any]:
        """Create a new workflow record"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO workflows (workflow_id, user_id, start_time, status, main_agent_id)
                VALUES (?, ?, ?, ?, ?)
                """,
                (workflow_id, user_id, start_time.isoformat(), "running", main_agent_id)
            )
            await db.commit()
            
        logger.info("workflow_created", workflow_id=workflow_id, user_id=user_id)
        return {
            "workflow_id": workflow_id,
            "user_id": user_id,
            "start_time": start_time.isoformat(),
            "status": "running"
        }
    
    async def update_workflow_status(
        self,
        workflow_id: str,
        status: str,
        end_time: Optional[datetime] = None
    ) -> None:
        """Update workflow status"""
        async with aiosqlite.connect(self.db_path) as db:
            if end_time:
                await db.execute(
                    "UPDATE workflows SET status = ?, end_time = ? WHERE workflow_id = ?",
                    (status, end_time.isoformat(), workflow_id)
                )
            else:
                await db.execute(
                    "UPDATE workflows SET status = ? WHERE workflow_id = ?",
                    (status, workflow_id)
                )
            await db.commit()
            
        logger.info("workflow_updated", workflow_id=workflow_id, status=status)
    
    async def get_workflow(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        """Get workflow by ID"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM workflows WHERE workflow_id = ?", (workflow_id,)) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None
    
    # Agent State Operations
    
    async def set_agent_state(
        self,
        workflow_id: str,
        agent_id: str,
        state_key: str,
        state_value: Any
    ) -> None:
        """Set agent state (shared memory)"""
        value_json = json.dumps(state_value)
        
        async with aiosqlite.connect(self.db_path) as db:
            # Delete existing state with same key
            await db.execute(
                "DELETE FROM agent_state WHERE workflow_id = ? AND agent_id = ? AND state_key = ?",
                (workflow_id, agent_id, state_key)
            )
            
            # Insert new state
            await db.execute(
                """
                INSERT INTO agent_state (workflow_id, agent_id, state_key, state_value)
                VALUES (?, ?, ?, ?)
                """,
                (workflow_id, agent_id, state_key, value_json)
            )
            await db.commit()
    
    async def get_agent_state(
        self,
        workflow_id: str,
        agent_id: str,
        state_key: str
    ) -> Optional[Any]:
        """Get agent state value"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                """
                SELECT state_value FROM agent_state 
                WHERE workflow_id = ? AND agent_id = ? AND state_key = ?
                ORDER BY updated_at DESC LIMIT 1
                """,
                (workflow_id, agent_id, state_key)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return json.loads(row[0])
                return None
    
    async def get_all_agent_state(self, workflow_id: str) -> Dict[str, Any]:
        """Get all agent state for a workflow"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM agent_state WHERE workflow_id = ? ORDER BY updated_at DESC",
                (workflow_id,)
            ) as cursor:
                rows = await cursor.fetchall()
                return {
                    f"{row['agent_id']}.{row['state_key']}": json.loads(row['state_value'])
                    for row in rows
                }
    
    # Task History Operations
    
    async def archive_tasks(self, workflow_id: str) -> int:
        """Archive all tasks from a workflow to history"""
        async with aiosqlite.connect(self.db_path) as db:
            # Copy tasks to history
            await db.execute(
                """
                INSERT INTO task_history 
                (task_id, user_id, workflow_id, description, status, assigned_to, 
                 created_at, start_time, end_time, output, error_message, retry_count)
                SELECT task_id, user_id, workflow_id, description, status, assigned_to,
                       created_at, start_time, end_time, output, error_message, retry_count
                FROM tasks WHERE workflow_id = ?
                """,
                (workflow_id,)
            )
            
            # Get count of archived tasks
            async with db.execute(
                "SELECT COUNT(*) FROM tasks WHERE workflow_id = ?",
                (workflow_id,)
            ) as cursor:
                row = await cursor.fetchone()
                count = row[0] if row else 0
            
            # Delete from tasks table
            await db.execute("DELETE FROM tasks WHERE workflow_id = ?", (workflow_id,))
            await db.commit()
            
        logger.info("tasks_archived", workflow_id=workflow_id, count=count)
        return count
    
    async def get_task_history(
        self,
        user_id: str,
        days: int = 7
    ) -> List[Dict[str, Any]]:
        """Get task history for learning and context"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                """
                SELECT * FROM task_history 
                WHERE user_id = ? 
                AND archived_at >= datetime('now', '-' || ? || ' days')
                ORDER BY archived_at DESC
                """,
                (user_id, days)
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
