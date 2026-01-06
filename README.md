# Temporal + Claude Agent MVP

A sophisticated task orchestration system that combines Temporal workflow engine with Claude Agent SDK to enable autonomous daily task management with a web dashboard for monitoring and control.

## 🚀 Features

- **Autonomous Task Generation**: Main AI agent generates valuable daily tasks
- **Multi-Agent Execution**: Sub-agents execute tasks in parallel
- **Cron Scheduling**: Automatic workflow triggering via Temporal
- **Real-Time Dashboard**: Web UI with live task monitoring via WebSocket
- **Task Management**: Create, edit, delete, and track tasks
- **Comprehensive Reporting**: Automated status reports after workflow completion
- **Persistent Storage**: SQLite database with task history
- **Cloud-Ready**: Integrated with Temporal Cloud

## 🏗️ Architecture

```
Main Orchestrating Agent (Claude Opus)
    ↓
Generates 2-4 Daily Tasks
    ↓
Spawns Sub-Agents (Claude Haiku) → Execute Tasks in Parallel
    ↓
Generate Status Report
    ↓
Archive to History
```

**Key Technologies:**
- **Temporal**: Workflow orchestration and scheduling
- **Claude Agent SDK**: Robust agentic pattern implementation
- **FastAPI**: Real-time dashboard backend
- **SQLite**: Lightweight persistent storage

## 📋 Prerequisites

- Python 3.9+
- Temporal Cloud account (or local Temporal server)
- Anthropic API key
- Optional: Composio API key (for extended tools)

## ⚡ Quick Start

### 1. Install Dependencies

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install requirements
pip install -r requirements.txt
```

### 2. Configure Environment

Your `.env` file is already configured with:
- `ANTHROPIC_API_KEY` - Claude API key
- `TEMPORAL_HOST` - Temporal Cloud endpoint
- `TEMPORAL_NAMESPACE` - Your namespace
- `TEMPORAL_API` - Temporal API key
- `TEMPORAL_MTLS_CERT` / `TEMPORAL_MTLS_KEY` - Optional mTLS auth

### 3. Initialize Database

```bash
python scripts/init_database.py
```

### 4. Start the Worker

The worker processes Temporal workflows and activities:

```bash
python worker.py
```

Keep this running in a separate terminal.

### 5. Start the Web Dashboard

```bash
python src/api/main.py
```

Open http://localhost:8500 in your browser.

## 🎯 Usage

### Option A: Manual Workflow Trigger (for testing)

```bash
# Run a 10-minute demo workflow
python run_workflow.py run --user_id=default_user --duration=10

# Run a custom duration workflow
python run_workflow.py run --user_id=my_user --duration=30
```

### Option B: Scheduling Workflows

You have two powerful ways to schedule agent runs:

**1. Dual-Mode Schedules (Recommended)**
Use the dedicated schedule manager for complex, persistent schedules (e.g., "Daily at 8 AM").

```bash
# Create the permanent 8 AM daily schedule
python src/workflows/schedules.py create-daily --id "daily-agent-8am" --hour 8 --minute 0

# List active schedules
python src/workflows/schedules.py list

# Trigger manually via CLI or Dashboard
```

**2. Ad-hoc Cron**
Quickly schedule a recurring run via command line arguments.

```bash
# Schedule for testing (every 2 minutes)
python run_workflow.py schedule --user_id=default_user --cron="*/2 * * * *" --duration=5
```

### Web Dashboard Features

- **Create Tasks**: Add new tasks via the UI
- **Monitor Progress**: See real-time status updates
- **View Statistics**: Task breakdown by status
- **Schedules Tab**: View and trigger persistent Temporal Schedules
- **Filter Tasks**: Filter by status (pending, in progress, completed, failed)
- **Delete Tasks**: Remove pending tasks before execution
- **WebSocket Updates**: Automatic refresh every 5 seconds

## 📊 How It Works

1. **Workflow Initialization**: 
   - Creates workflow record in database
   - Sets up shared context and deadline

2. **Task Generation**:
   - Main agent analyzes context and history
   - Autonomously generates 2-4 valuable tasks
   - Tasks saved to database as "pending"

3. **Parallel Execution**:
   - Sub-agents spawn for each pending task
   - Execute tasks concurrently
   - Update status in real-time (in_progress → completed/failed)

4. **Status Reporting**:
   - Main agent generates comprehensive report
   - Includes all tasks with outputs and errors
   - Shows completion statistics

5. **Archival**:
   - Completed tasks moved to history
   - Available for future agent learning

## 🗄️ Database Schema

**Tables:**
- `users` - User configuration
- `workflows` - Workflow execution records
- `tasks` - Active tasks
- `task_history` - Archived completed tasks
- `agent_state` - Shared memory between agents

## 🔧 Configuration

Edit `.env` or environment variables:

```bash
# Workflow settings
WORKFLOW_DEMO_DURATION_MINUTES=10
WORKFLOW_PRODUCTION_DURATION_MINUTES=180
CHECKPOINT_INTERVAL_MINUTES=2

# Database
DATABASE_PATH=task_management.db

# API
API_HOST=0.0.0.0
API_PORT=8000

# Models
ANTHROPIC_MODEL=claude-haiku-4-5
```

## 📁 Project Structure

```
temporal-claude/
├── src/
│   ├── agents/          # Agent implementations (main, sub, tools)
│   ├── workflows/       # Temporal workflow definitions
│   ├── activities/      # Temporal activities
│   ├── database/        # Database schema and operations
│   ├── api/            # FastAPI backend + frontend
│   │   └── frontend/   # Web dashboard (HTML, CSS, JS)
│   └── config.py       # Configuration management
├── scripts/            # Utility scripts
├── tests/              # Unit and integration tests
├── worker.py           # Temporal worker
├── run_workflow.py     # CLI for triggering/scheduling
└── requirements.txt    # Python dependencies
```

## 🧪 Testing

### Run Unit Tests

```bash
pytest tests/ -v
```

### Manual End-to-End Test

1. Start worker: `python worker.py`
2. Start web dashboard: `python src/api/main.py`
3. Trigger workflow: `python run_workflow.py run --duration=5`
4. Watch tasks execute in dashboard at http://localhost:8000
5. Check console for final status report

## 🌐 Temporal Cloud UI

View your workflows in Temporal Cloud:
```
https://cloud.temporal.io/namespaces/{your-namespace}/workflows
```

- Monitor workflow execution
- View activity history
- Check schedules
- Debug failures

## 🛠️ Troubleshooting

**Worker won't connect to Temporal:**
- Check `TEMPORAL_HOST`, `TEMPORAL_NAMESPACE`, and `TEMPORAL_API` in `.env`
- Verify Temporal Cloud credentials

**Database errors:**
- Run `python scripts/init_database.py` to reinitialize
- Check file permissions on `task_management.db`

**WebSocket not connecting:**
- Ensure API server is running on correct port
- Check browser console for errors
- Verify firewall settings

**Agents not executing tasks:**
- Check `ANTHROPIC_API_KEY` is valid
- Monitor worker logs for errors
- Verify tasks are in "pending" status

## 📝 Environment Variables Reference

| Variable | Description | Default |
|----------|-------------|---------|
| `ANTHROPIC_API_KEY` | Claude API key | Required |
| `TEMPORAL_HOST` | Temporal server address | Required |
| `TEMPORAL_NAMESPACE` | Temporal namespace | Required |
| `TEMPORAL_API` | Temporal API key | Required |
| `DATABASE_PATH` | SQLite database path | `task_management.db` |
| `WORKFLOW_DEMO_DURATION_MINUTES` | Demo duration | 10 |
| `API_PORT` | Dashboard port | 8000 |

## 🚀 Next Steps

- Add Slack/Email notifications
- Implement user authentication
- Add more agent tools (file ops, APIs, etc.)
- Create detailed analytics dashboard
- Add workflow templates
- Implement human-in-the-loop approvals

## 📄 License

MIT License - feel free to use and modify for your needs.

---

Built with ❤️ using Temporal & Claude
