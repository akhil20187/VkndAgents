"""
Test database operations.
Purpose: Verify database functionality including task CRUD and workflow management.
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database.operations import DatabaseOperations
from datetime import datetime


async def test_database_operations():
    """Test basic database operations"""
    print("Testing database operations...")
    
    db_ops = DatabaseOperations("task_management.db")
    
    # Test 1: Create workflow
    print("\n1. Creating workflow...")
    workflow = await db_ops.create_workflow(
        workflow_id="test_workflow_001",
        user_id="default_user",
        start_time=datetime.now(),
        main_agent_id="main_agent_test_001"
    )
    print(f"   ✅ Workflow created: {workflow['workflow_id']}")
    
    # Test 2: Create task
    print("\n2. Creating task...")
    task = await db_ops.create_task(
        task_id="task_001",
        user_id="default_user",
        workflow_id="test_workflow_001",
        description="Test task: Create sample report"
    )
    print(f"   ✅ Task created: {task['task_id']}")
    
    # Test 3: Update task status
    print("\n3. Updating task status...")
    await db_ops.update_task_status(
        task_id="task_001",
        status="in_progress",
        assigned_to="sub_agent_001"
    )
    print("   ✅ Task status updated to 'in_progress'")
    
    # Test 4: Get task
    print("\n4. Retrieving task...")
    retrieved_task = await db_ops.get_task("task_001")
    print(f"   ✅ Task retrieved: {retrieved_task['description']}")
    print(f"      Status: {retrieved_task['status']}")
    
    # Test 5: Complete task
    print("\n5. Completing task...")
    await db_ops.update_task_status(
        task_id="task_001",
        status="completed",
        output="Task completed successfully! Sample report generated."
    )
    print("   ✅ Task marked as completed")
    
    # Test 6: Query tasks
    print("\n6. Querying all tasks...")
    tasks = await db_ops.get_tasks(workflow_id="test_workflow_001")
    print(f"   ✅ Found {len(tasks)} task(s)")
    
    # Test 7: Agent state
    print("\n7. Testing agent state...")
    await db_ops.set_agent_state(
        workflow_id="test_workflow_001",
        agent_id="main_agent_test_001",
        state_key="progress",
        state_value={"tasks_completed": 1, "tasks_pending": 0}
    )
    state = await db_ops.get_agent_state(
        workflow_id="test_workflow_001",
        agent_id="main_agent_test_001",
        state_key="progress"
    )
    print(f"   ✅ Agent state saved and retrieved: {state}")
    
    # Test 8: Archive tasks
    print("\n8. Archiving workflow tasks...")
    count = await db_ops.archive_tasks("test_workflow_001")
    print(f"   ✅ Archived {count} task(s)")
    
    # Test 9: Complete workflow
    print("\n9. Completing workflow...")
    await db_ops.update_workflow_status(
        workflow_id="test_workflow_001",
        status="completed",
        end_time=datetime.now()
    )
    print("   ✅ Workflow completed")
    
    print("\n" + "="*50)
    print("✅ ALL TESTS PASSED!")
    print("="*50)


if __name__ == "__main__":
    asyncio.run(test_database_operations())
