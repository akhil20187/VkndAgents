import asyncio
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database.operations import DatabaseOperations
from src.agents.main_agent import MainAgent
from src.config import settings
import structlog

# Configure structlog to print to stderr
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer()
    ]
)

async def main():
    print("Testing MainAgent task generation...")
    
    workflow_id = "test-debug-workflow"
    user_id = "test-user"
    deadline = (datetime.now() + timedelta(minutes=15)).isoformat()
    
    # Init DB
    db_ops = DatabaseOperations(settings.database_path)
    await db_ops.initialize()
    
    # Create Agent
    try:
        main_agent = MainAgent(
            workflow_id=workflow_id,
            user_id=user_id,
            workflow_deadline=deadline,
            db_ops=db_ops
        )
        print("Agent initialized successfully.", flush=True)
        
        # Run generation
        print("Running generate_tasks()...", flush=True)
        result = await main_agent.generate_tasks()
        print("Generation result:", result, flush=True)
        
    except Exception as e:
        print(f"\n❌ CAUGHT EXCEPTION: {type(e).__name__}: {e}", flush=True)
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
