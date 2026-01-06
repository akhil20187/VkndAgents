-- SQLite Database Schema for Temporal + Claude Agent System
-- Purpose: Store users, tasks, workflows, and shared agent state for task orchestration

-- Users table: Store user configuration and preferences
CREATE TABLE IF NOT EXISTS users (
    user_id TEXT PRIMARY KEY,
    email TEXT,
    timezone TEXT DEFAULT 'UTC',
    preferred_start_time INTEGER DEFAULT 8,  -- 8 AM or 10 AM
    notification_channel TEXT,  -- For future Slack/email integration
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Workflows table: Track workflow execution records
CREATE TABLE IF NOT EXISTS workflows (
    workflow_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP,
    status TEXT NOT NULL,  -- running, completed, failed
    main_agent_id TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

-- Tasks table: Current and active tasks
CREATE TABLE IF NOT EXISTS tasks (
    task_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    workflow_id TEXT NOT NULL,
    description TEXT NOT NULL,
    status TEXT NOT NULL,  -- generated, pending, in_progress, completed, failed
    assigned_to TEXT,  -- Sub-agent ID
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    start_time TIMESTAMP,
    end_time TIMESTAMP,
    output TEXT,  -- Task result/artifact
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    FOREIGN KEY (workflow_id) REFERENCES workflows(workflow_id)
);

-- Task history: Archive of completed tasks
CREATE TABLE IF NOT EXISTS task_history (
    task_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    workflow_id TEXT NOT NULL,
    description TEXT NOT NULL,
    status TEXT NOT NULL,
    assigned_to TEXT,
    created_at TIMESTAMP,
    start_time TIMESTAMP,
    end_time TIMESTAMP,
    output TEXT,
    error_message TEXT,
    retry_count INTEGER,
    archived_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    FOREIGN KEY (workflow_id) REFERENCES workflows(workflow_id)
);

-- Agent state: Shared memory for agent communication
CREATE TABLE IF NOT EXISTS agent_state (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workflow_id TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    state_key TEXT NOT NULL,
    state_value TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (workflow_id) REFERENCES workflows(workflow_id)
);

-- Indexes for query optimization
CREATE INDEX IF NOT EXISTS idx_tasks_user_id ON tasks(user_id);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_workflow_id ON tasks(workflow_id);
CREATE INDEX IF NOT EXISTS idx_tasks_created_at ON tasks(created_at);

CREATE INDEX IF NOT EXISTS idx_task_history_user_id ON task_history(user_id);
CREATE INDEX IF NOT EXISTS idx_task_history_workflow_id ON task_history(workflow_id);
CREATE INDEX IF NOT EXISTS idx_task_history_archived_at ON task_history(archived_at);

CREATE INDEX IF NOT EXISTS idx_agent_state_workflow_id ON agent_state(workflow_id);
CREATE INDEX IF NOT EXISTS idx_agent_state_agent_id ON agent_state(agent_id);

CREATE INDEX IF NOT EXISTS idx_workflows_user_id ON workflows(user_id);
CREATE INDEX IF NOT EXISTS idx_workflows_start_time ON workflows(start_time);

-- Insert default user for MVP
INSERT OR IGNORE INTO users (user_id, email, timezone, preferred_start_time)
VALUES ('default_user', 'user@example.com', 'UTC', 8);
