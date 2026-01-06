# Temporal + Claude Agent SDK Daily Task Management System Specification

## Project Overview

A sophisticated task orchestration system that combines Temporal workflow engine with Claude Agent SDK to enable autonomous daily task management. The system runs a daily 3-hour workflow window (8/10 AM → 11 AM) where a main orchestrating agent generates tasks, spawns sub-agents to execute them, and provides a comprehensive status update at 11 AM.

**Key Innovation**: Multi-agent hierarchical system with shared memory, where the main agent orchestrates task generation and delegation to specialized sub-agents.

---

## System Architecture

### High-Level Flow

```
8/10 AM: Trigger Daily Workflow
    ↓
Main Agent Initializes
    ↓
Main Agent Generates Daily Tasks (AI-generated, fully autonomous)
    ↓
Main Agent Spawns Sub-Agents & Assigns Tasks
    ↓
Hybrid Execution: Continuous + Checkpoint Validation (0-180 min)
    ↓
11 AM: Hard Stop & Status Update Generation
    ↓
Send Status via Notification Channel
    ↓
Archive Task Data for Historical Context
```

### Agent Architecture

#### Main Orchestrating Agent
- **Role**: Generates daily tasks, spawns sub-agents, coordinates execution, manages shared state
- **Autonomy**: Fully autonomous - decides what tasks matter each day
- **Capabilities**: Full system access via provided tools
- **Scope**: Task generation, sub-agent coordination, progress monitoring
- **Output**: Daily status report of all work completed/in-progress

#### Sub-Agents
- **Role**: Execute specific tasks assigned by main agent
- **Quantity**: Dynamically created by main agent (1+ per day)
- **Communication**: Via shared task list and shared memory store
- **Constraints**: Pre-validated tasks only
- **Failure Mode**: Escalate to human after repeated failures

#### Shared Resources
- **Task List**: All agents read/write to central task store (SQLite)
- **Memory/Context**: Shared knowledge base accessible to all agents
- **History**: Full access to previous days' work for learning and optimization

---

## Workflow Execution Model

### Execution Type: Hybrid (Continuous + Checkpoints)

**Continuous Execution Phase**:
- Main agent continuously monitors and spawns sub-agents as needed
- Sub-agents work independently on assigned tasks
- Agents leverage shared task list and memory for coordination

**Checkpoint Validation Phase**:
- System validates agent progress at predetermined checkpoints (recommend: 15-min intervals)
- Updates shared state, handles task transitions
- Allows for graceful checkpoint recovery if needed

### Timing & Scheduling

#### Per-User Timezone-Aware Scheduling
```
User Configured Start Time: 8 AM or 10 AM (user's local timezone)
Execution Window: 3 hours
Status Update Time: Start Time + 3 hours (11 AM or 1 PM user's timezone)
Recurrence: Daily
```

#### Time Management
- **Hard deadline at 11 AM**: Workflow terminates, status generated regardless of task state
- **In-progress handling**: Tasks not completed are marked as "In Progress" in status
- **Pending tasks**: Can be modified/added until assigned to sub-agent
- **Grace period**: Agent receives internal warnings at 10:55 AM (5 min before deadline)

### Failure & Recovery

#### Failure Scenarios
1. **Task Execution Failure**:
   - Sub-agent attempts task → failure
   - Automatic retry with exponential backoff (up to 3 attempts)
   - After repeated failures → escalate to human (notification)
   - Record failure in task database with reason

2. **Workflow/Network Interruption**:
   - Recovery mechanism: **Resume from checkpoint**
   - Temporal event sourcing replays workflow from last checkpoint
   - Agents resume assigned tasks from saved state
   - No data loss due to event sourcing

3. **Agent Failure**:
   - Sub-agent crashes → main agent detects via checkpoint
   - Task returned to "pending" status
   - Can be re-assigned or escalated based on failure reason

#### Error Handling Strategy
- **Automatic Recovery**: Exponential backoff retry for transient errors (network, timeout)
- **Human Escalation**: After 3 failed attempts, notify user with error context
- **Agent Intelligence**: Escalating agents should attempt to decide next actions if possible
- **Record Everything**: All failures logged with timestamps, error messages, retry counts

---

## Task Management System

### Task Lifecycle

```
Generated (by Main Agent)
    ↓
Pre-Validated ← (Check resource availability, tool requirements)
    ↓
Pending ← (Ready for assignment)
    ↓
In-Progress ← (Assigned to sub-agent)
    ↓
Completed OR Failed
    ↓
Archived (After 11 AM status update)
```

### Task Definition & Validation

#### Pre-Validation Requirements
- Validate before execution (not just-in-time)
- Check: Required tools available, resource prerequisites met, data dependencies satisfied
- Validation failure → return to pending, notify main agent

#### Task Attributes (Database Schema)
```
- task_id (UUID)
- user_id (for multi-user support)
- created_at (timestamp)
- generated_by (main agent)
- assigned_to (sub-agent ID or null)
- description (text)
- status (generated, pending, in_progress, completed, failed)
- start_time (when execution began)
- end_time (when execution ended)
- output (task result/artifact)
- error_message (if failed)
- retry_count (for failed tasks)
- workflow_id (Temporal workflow reference)
```

### Task Completion Criteria

**Task is considered "Completed" when**:
- Sub-agent explicitly reports task completion AND/OR
- Required output artifact is successfully generated

**Task is considered "In-Progress" at 11 AM if**:
- Execution started but not yet completed
- Status update includes current progress percentage if available

### Mid-Execution Task Modifications

**Allowed Operations**:
- Add new tasks (immediately pending, ready for assignment)
- Modify pending tasks (not yet in progress)
- Cancel pending tasks

**Not Allowed**:
- Modify in-progress tasks (avoid state corruption)
- Force-stop in-progress tasks (except via human escalation)

---

## Data Persistence & Storage

### Database: SQLite

**Rationale**:
- Simplicity for small team deployment
- Cost-effective (file-based, no external service)
- Sufficient for task tracking and querying needs
- Easy to backup and version control

**Core Tables**:

1. **users** (multi-user support)
   - user_id, email, timezone, preferred_start_time (8am/10am), slack_channel

2. **tasks**
   - task_id, user_id, description, status, created_at, assigned_to, start_time, end_time, output, error_message, retry_count, workflow_id

3. **task_history** (archive)
   - Bulk archive of completed tasks from previous days (for learning)

4. **workflows**
   - workflow_id, user_id, start_time, end_time, status, main_agent_id

5. **agent_state** (shared memory)
   - agent_id, state_key, state_value, updated_at
   - Acts as shared knowledge base for all agents

**Query Optimization**:
- Index on: user_id, status, created_at, assigned_to
- Enables agents to quickly query: pending tasks, assigned tasks, task history

### Historical Context Access

**Main Agent Capabilities**:
- Full read access to all historical task data
- Query patterns:
  - "Get all tasks from last 7 days"
  - "Get completed tasks by category"
  - "Get failure patterns"
- Use for learning: Agent optimizes task generation based on past success/failure patterns

**Sub-Agent Capabilities**:
- Read access to shared memory and task list
- Can query task history to understand context
- Cannot directly modify history

### Data Retention
- **Live data**: Kept in tasks table during workflow execution
- **Historical data**: Moved to task_history after 11 AM status update
- **Retention policy**: Keep 90 days of history (configurable)

---

## Claude Agent SDK Integration

### Main Agent Initialization

```python
# Pseudocode
main_agent = ClaudeAgent(
    name="daily_orchestrator",
    system_prompt="""
        You are an autonomous daily task orchestrator. At the start of each day:
        1. Review yesterday's work from the shared memory
        2. Generate 3-8 meaningful tasks for today that would be valuable
        3. For each task, identify required sub-agents/capabilities
        4. Coordinate execution of tasks by spawning sub-agents
        5. Monitor progress via the shared task list
        6. At the end of the window, prepare a comprehensive status update

        You have full system access. Think critically about what matters.
    """,
    tools=[list_pending_tasks, create_task, spawn_subagent, update_task_status, query_history, ...],
    model="claude-opus-4.5",  # Use capable model for orchestration
    memory=shared_memory_store
)
```

### Sub-Agent Creation

```python
# Main agent dynamically creates sub-agents like:
sub_agent = ClaudeAgent.spawn(
    name=f"executor_{task_id}",
    system_prompt=f"Execute this task: {task_description}",
    assigned_task=task_id,
    tools=[relevant_tools_for_task],
    model="claude-haiku-4.5",  # Use cheaper model for execution (cost optimization)
    parent_agent=main_agent
)
```

### Shared State Management

```python
# All agents access shared memory
shared_memory = {
    "current_tasks": task_list,  # SQLite query result
    "agent_state": agent_state_store,
    "context": {
        "workflow_id": current_workflow_id,
        "user_id": current_user_id,
        "execution_start_time": workflow_start,
        "deadline": deadline_11am
    }
}

# Agents read/update via:
main_agent.memory.get("current_tasks")
sub_agent.memory.update("task_status", task_id, "in_progress")
```

### Tool Design

**Main Agent Tools**:
- `generate_tasks()` - AI-generate task ideas
- `spawn_subagent(task_id, capabilities_needed)` - Create new sub-agent
- `query_task_database(filters)` - Check task status
- `query_history(days=7)` - Get past work
- `update_main_state(key, value)` - Update shared memory
- `send_status_update(content)` - Prepare final status

**Sub-Agent Tools** (Provided based on task type):
- File operations: read, write, list files
- API calls: HTTP requests to external services
- Database: query, insert, update records
- Computation: code execution, analysis
- Notifications: send messages
- etc. (based on specific task needs)

**Universal Tools** (Available to all agents):
- `get_current_time()` - Check if deadline approaching
- `read_task_database()` - Access current task state
- `read_shared_memory()` - Access shared context

### Cost Optimization

**Strategy**: Use smaller models where possible, cache shared context
- **Main Agent**: Use Claude Opus 4.5 (capable orchestration)
- **Sub-Agents**: Use Claude Haiku 4.5 (cost-efficient execution)
- **Token Budget**: Set per-agent limits, monitor usage
- **Caching**: Cache task history and shared memory to reduce repeated API calls

---

## Temporal Workflow Configuration

### Workflow Definition

```python
@temporal.workflow.defn
class DailyTaskManagementWorkflow:
    async def run(self, user_id: str, start_time: datetime) -> WorkflowResult:
        # 1. Initialize main agent
        # 2. Main agent generates tasks
        # 3. Hybrid execution: continuous + checkpoints
        # 4. At 11 AM: collect results and prepare status
        # 5. Return status for notification
```

### Activity Patterns

```
Activity 1: Initialize Workflow (1 min)
    - Load user config
    - Create shared memory store
    - Initialize main agent

Activity 2-N: Execute Tasks (175 min)
    - Main agent coordinates
    - Sub-agents execute
    - Checkpoint validation every 15 min

Activity N+1: Generate Status Update (4 min)
    - Collect all task results
    - Format status report
    - Return for delivery

Activity N+2: Archive & Notify (1 min)
    - Move completed tasks to history
    - Send notification
    - Clean up agent instances
```

### Temporal Specific Features Used

- **Event Sourcing**: Enable resume from checkpoint capability
- **Durable Timers**: Use for 11 AM deadline and checkpoint intervals
- **Signals**: Allow mid-workflow task modifications (add/modify pending tasks)
- **Queries**: Expose current workflow state (for dashboard monitoring)
- **Retries**: Built-in retry policies for activities (especially agent initialization)

### Namespace & Workflow Configuration

```python
client = WorkflowServiceClient(
    host="localhost",  # or cloud Temporal endpoint
    port=7233
)

workflow_options = WorkflowOptions(
    id=f"daily-task-{user_id}-{date}",
    task_queue="daily-tasks",
    retry_policy=RetryPolicy(
        initial_interval=timedelta(seconds=1),
        backoff_coefficient=2,
        max_interval=timedelta(seconds=100),
        max_attempts=3,
        non_retryable_error_types=["UserException"]
    ),
    timeout=timedelta(hours=4),  # 4 hour max (covers setup + 3hr window + buffer)
    cron_schedule="0 8,10 * * *"  # Trigger at 8 AM and 10 AM daily
)
```

---

## User Interface & Notifications

### Web Dashboard

**Technologies**:
- Backend: Python FastAPI (existing infrastructure)
- Frontend: React or vanilla JS (simple monitoring)
- Real-time updates: WebSocket or polling (every 10 sec)

**Features**:

1. **Task Management Panel**
   - View all pending tasks for today
   - Add new tasks (natural language input)
   - Modify pending tasks (edit description, etc.)
   - Delete pending tasks
   - View in-progress and completed tasks

2. **Live Execution Monitor**
   - Real-time task status board
   - Timeline of task start/end times
   - Sub-agent activity indicators
   - Progress percentage for long-running tasks
   - Error notifications with details

3. **Historical View**
   - Calendar/timeline of past workflows
   - Task breakdown by date
   - Success/failure analytics
   - Time spent per task type

4. **Settings**
   - Preferred start time (8 AM or 10 AM)
   - Timezone selection
   - Notification channel (Slack webhook URL, email)
   - Task validation rules

### Status Update Format

**Delivery**: Notification channel (Slack, email, etc.)

**Content Structure**:
```
📋 Daily Task Summary - [Date]
Execution Window: 8:00 AM - 11:00 AM [Timezone]

✅ COMPLETED (X tasks)
- Task 1 Description
  Status: Completed | Duration: 12 min | Output: [brief]
- Task 2 Description
  Status: Completed | Duration: 28 min | Output: [brief]

🔄 IN PROGRESS (Y tasks)
- Task 3 Description
  Status: In Progress | Progress: 45% | Elapsed: 15 min
- Task 4 Description
  Status: In Progress | Progress: 10% | Elapsed: 3 min

❌ FAILED (Z tasks)
- Task 5 Description
  Status: Failed | Reason: [error] | Attempts: 3

⏸️  NOT STARTED (W tasks)
- Task 6 Description
  Status: Pending | Reason: Not yet assigned

---
Summary Stats:
- Total Generated: X+Y+Z+W
- Completion Rate: X/(X+Y+Z+W)
- Average Task Time: [calculated]
- Total Time Used: [out of 180 min]

Next Steps: [Main agent's recommendation for continuation/next day]
```

---

## Multi-User Support

### User Management

**User Data**:
- user_id, email, timezone, slack_webhook, notification_preferences
- workflow_preferences (start_time, task_generation_style)
- api_key (for dashboard access)

**Isolation**:
- Each workflow_id is scoped to user_id
- Tasks filtered by user_id in all queries
- Shared memory is per-workflow (not global)

**Scaling Approach**:
- Small team: Run multiple workflows concurrently (Temporal supports this)
- Each workflow instance is independent
- Shared Temporal infrastructure handles orchestration

---

## Development & Deployment

### Development Environment

**Setup**:
```bash
# 1. Temporal Server (existing, use current setup)
temporal server start-dev  # Or connect to existing server

# 2. Python Environment
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 3. Database
sqlite3 task_management.db < schema.sql

# 4. Local Testing
pytest tests/
python run_workflow.py --user_id=test_user --dry_run=true
```

**Testing Strategy**:
- Unit tests for agents (mocked tools)
- Integration tests with mock Temporal server
- End-to-end test: Run 30-min workflow (scaled time)
- Manual testing: Run with live agents and verify task execution

### Production Deployment

**Hybrid Approach**:

1. **Local Development**
   - Temporal Server: Local dev instance
   - Database: SQLite file
   - Web Dashboard: Local dev server
   - Testing: Full 3-hour workflows on demand

2. **Cloud Production**
   - Temporal Server: Cloud instance (Temporal Cloud or self-hosted)
   - Database: SQLite (can be synced to cloud storage) or PostgreSQL for reliability
   - Web Dashboard: FastAPI on cloud (Vercel, AWS Lambda, or container)
   - Scheduled Workflows: Cloud cron or Temporal's native cron
   - Monitoring: Basic logging (structured logs to stdout/file)

**CI/CD**:
- Git push → Run tests → Deploy to staging → Manual approval → Deploy to production
- Rollback: Previous version available in git, easy revert

---

## Observability & Monitoring

### Logging Strategy

**Scope**: Basic logging (as per requirements)

**Log Levels**:
- INFO: Workflow start/end, task status changes, agent spawning
- WARN: Failures, retries, approaching deadline
- ERROR: Unrecoverable errors, escalations
- DEBUG: (During development) Detailed agent decision logs

**Log Output**:
- STDOUT (captured by container/cloud provider)
- File (for local development)
- Structured JSON format (easy parsing)

**Sample Log**:
```json
{
  "timestamp": "2024-01-15T08:00:01Z",
  "workflow_id": "daily-task-user1-2024-01-15",
  "event": "workflow_started",
  "user_id": "user1",
  "level": "INFO"
}
```

### Metrics to Track

- Workflow success rate (%)
- Average tasks per day
- Average completion time per task
- Failure rate and top error types
- Status update delivery success rate

---

## Implementation Roadmap

### Phase 1: Foundation (Week 1-2)
- [ ] Set up Temporal workflow structure
- [ ] Design SQLite schema
- [ ] Implement basic database operations
- [ ] Create main orchestrating agent (Claude Agent SDK)
- [ ] Manual testing with synthetic workflows

### Phase 2: Sub-Agent System (Week 2-3)
- [ ] Implement sub-agent spawning mechanism
- [ ] Create shared memory/state management
- [ ] Implement task assignment and execution
- [ ] Add checkpoint validation
- [ ] Test multi-agent coordination

### Phase 3: UI & Notifications (Week 3-4)
- [ ] Build web dashboard (basic version)
- [ ] Implement notification channel integration
- [ ] Add real-time status updates
- [ ] Implement task creation/modification UI

### Phase 4: Polish & Deployment (Week 4-5)
- [ ] Error handling and resilience
- [ ] Performance optimization and cost reduction
- [ ] Comprehensive testing and documentation
- [ ] Production deployment setup
- [ ] Monitoring and logging

---

## Success Criteria

- ✅ Daily workflow triggers at specified time
- ✅ Main agent generates diverse, autonomous tasks
- ✅ Sub-agents execute tasks and report completion
- ✅ Status update delivered at 11 AM with task breakdown
- ✅ No data loss on workflow interruption
- ✅ Dashboard shows live execution progress
- ✅ Small team can run multiple concurrent workflows
- ✅ Cost-efficient operation (budget-conscious model usage)
- ✅ All work completed in 3-hour window logged and retrievable

---

## Future Enhancements

- Learning: Agent improves task generation based on completion patterns
- Analytics: Dashboard showing trends in task types, durations, success rates
- Human-in-the-Loop: Optional approval workflow for certain task types
- Tool Marketplace: Easy way to add new tools/capabilities to agents
- Cross-Team Workflows: Multiple teams with shared task management
- Advanced Scheduling: Support more complex schedules (weekly, monthly)

---

## Questions for Implementation

1. Slack/Email Integration: Do you have existing webhook URLs or should we implement OAuth flow?
2. Local Storage: Should SQLite file live in project directory or cloud sync (e.g., iCloud, Dropbox)?
3. Agent Model Choice: Is Claude Opus 4.5 sufficient for main agent, or need stronger model?
4. Sub-Agent Toolkit: Which tools should we implement first (file ops, APIs, code execution)?
