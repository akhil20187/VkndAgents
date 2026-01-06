---
description: Manage tasks in the Temporal task database - create, update, query, and archive tasks
allowed-tools:
  - Bash
  - Read
---

# Task Management Skill

This skill enables interaction with the Temporal task management database.

## Available Operations

### Create a Task
Use the database CLI to create new tasks:
```bash
cd /Users/akhilesh/Documents/Workplace/temporal-claude
./venv/bin/python -c "
import asyncio
from src.database.operations import DatabaseOperations
import uuid

async def create_task(description):
    db = DatabaseOperations()
    await db.initialize()
    task_id = f'task_{uuid.uuid4().hex[:8]}'
    await db.create_task(
        task_id=task_id,
        user_id='default_user',
        workflow_id='manual',
        description=description,
        status='pending'
    )
    print(f'Created task: {task_id}')

asyncio.run(create_task('YOUR_TASK_DESCRIPTION'))
"
```

### Query Tasks
```bash
cd /Users/akhilesh/Documents/Workplace/temporal-claude
./venv/bin/python -c "
import asyncio
from src.database.operations import DatabaseOperations

async def query():
    db = DatabaseOperations()
    await db.initialize()
    tasks = await db.get_all_tasks('default_user')
    for t in tasks:
        print(f'{t[\"task_id\"]}: {t[\"status\"]} - {t[\"description\"]}')

asyncio.run(query())
"
```

### Update Task Status
```bash
cd /Users/akhilesh/Documents/Workplace/temporal-claude
./venv/bin/python -c "
import asyncio
from src.database.operations import DatabaseOperations

async def update(task_id, status, output=None):
    db = DatabaseOperations()
    await db.initialize()
    await db.update_task_status(task_id, status, output=output)
    print(f'Updated {task_id} to {status}')

asyncio.run(update('TASK_ID', 'completed', 'Task output here'))
"
```

## When to Use
- When asked to create, list, or manage tasks
- When tracking work items or todos
- When updating task progress or status
