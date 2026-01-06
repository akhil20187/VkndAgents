"""
Main orchestrating agent implementation.
Purpose: Generate daily tasks, coordinate sub-agents, and monitor progress.
"""
from datetime import datetime
from src.agents.base_agent import BaseAgent
from src.agents.base_agent import BaseAgent
import structlog

logger = structlog.get_logger()


MAIN_AGENT_SYSTEM_PROMPT = """You are an autonomous daily task orchestrator. Your role is to:

1. **Generate valuable daily tasks**: At the start of each workflow, think about what tasks would be meaningful and valuable to accomplish today. Be creative and autonomous - you decide what matters.

2. **Create 2-4 tasks**: Generate a manageable number of tasks (2-4) that can be completed within the time window. Each task should be clear and actionable.

3. **Monitor progress**: Keep track of tasks using the query_tasks tool. Check on their status periodically.

4. **Generate final report**: At the end, summarize what was accomplished, what's in progress, and what failed.

**Available Tools:**
- create_task: Create new tasks with clear descriptions
- query_tasks: Check status of all tasks or filter by status
- query_history: Look at past tasks for context and learning
- get_current_time: Check how much time remains
- log_message: Document your reasoning

**Guidelines:**
- Be autonomous - you decide what tasks to create
- Keep tasks simple and achievable within the time window
- Task descriptions should be clear about what needs to be accomplished
- Use query_tasks regularly to monitor progress
- At the end, provide a comprehensive summary

**Important:** You are in a demo/test environment. Create simple, demonstrable tasks that can be verified quickly (e.g., "Create a sample data file", "Generate a status report", "Log system information").

Begin by generating tasks for today's workflow."""


class MainAgent(BaseAgent):
    """
    Main orchestrating agent that generates tasks and monitors execution.
    Purpose: Central coordinator for daily workflow - generates tasks and tracks progress.
    """
    
    def __init__(
        self,
        workflow_id: str,
        user_id: str,
        workflow_deadline: str,
        db_ops
    ):
        """Initialize main agent with orchestration system prompt"""
        agent_id = f"main_agent_{workflow_id}"
        
        super().__init__(
            agent_id=agent_id,
            system_prompt=MAIN_AGENT_SYSTEM_PROMPT,
            db_ops=db_ops,
            workflow_id=workflow_id,
            user_id=user_id,
            workflow_deadline=workflow_deadline
        )
        
        self.workflow_id = workflow_id
        self.user_id = user_id
    
    async def generate_tasks(self) -> Dict[str, Any]:
        """
        Generate daily tasks for the workflow.
        Purpose: Main initialization step - creates tasks for the day.
        """
        logger.info("main_agent_generating_tasks", workflow_id=self.workflow_id)
        
        message = f"""Generate the following 3 specific tasks for today's workflow (workflow_id: {self.workflow_id}):

1. Gen AI Newsletter: "Generate a comprehensive AI newsletter summarizing the latest happenings in the AI world from the last 24 hours."

2. Financial News (Gold & Silver): "Research and compile a report on financial news specifically regarding Gold and Silver. Include summaries of news, videos, and articles released either yesterday or today."

3. Model Release News: "Research and summarize any official feature releases or announcements from Claude (Anthropic), Google Gemini, and OpenAI that occurred on their official platforms in the last 24-48 hours."

Use the create_task tool to add each of these 3 tasks. Ensure the descriptions are detailed enough for the sub-agents to understand the specific requirements (timeframes, topics, etc)."""
        
        result = await self.run(user_message=message, max_iterations=8)
        return result
    
    async def generate_status_report(self) -> str:
        """
        Generate final status report at end of workflow.
        Purpose: Summarize all work completed during the workflow.
        """
        logger.info("main_agent_generating_status", workflow_id=self.workflow_id)
        
        message = """The workflow is complete. Generate a comprehensive status report.

Use query_tasks to get all tasks and their current status. Then create a formatted report showing:

**COMPLETED TASKS:**
- List each completed task with its description and output

**IN PROGRESS TASKS:**
- List tasks that started but didn't finish

**PENDING TASKS:**
- List tasks that were created but never started

**FAILED TASKS:**
- List any failed tasks with error messages

**SUMMARY:**
- Total tasks created
- Completion rate
- Key accomplishments

Format the report clearly with markdown-style headers and bullet points."""
        
        result = await self.run(user_message=message, max_iterations=5)
        return result.get("final_response", "Status report generation failed")
