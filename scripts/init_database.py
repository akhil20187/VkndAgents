"""
Database initialization script.
Purpose: Initialize SQLite database with schema.
"""
import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database.operations import DatabaseOperations
from src.config import settings


async def main():
    """Initialize the database"""
    print(f"Initializing database at: {settings.database_path}")
    
    db_ops = DatabaseOperations(settings.database_path)
    await db_ops.initialize()
    
    print("✅ Database initialized successfully!")
    print(f"   Tables created: users, workflows, tasks, task_history, agent_state")
    print(f"   Default user created: default_user")


if __name__ == "__main__":
    asyncio.run(main())
