"""
Sub-agent implementation for executing specific tasks.
Purpose: Execute individual tasks assigned by the main agent.
"""
from src.agents.base_agent import BaseAgent
from src.agents.base_agent import BaseAgent
from typing import Dict, Any
import structlog

logger = structlog.get_logger()


def get_sub_agent_system_prompt(task_description: str) -> str:
    """
    Generate system prompt for sub-agent based on task.
    Purpose: Provide task-specific instructions to sub-agent.
    """
    return f"""You are a sub-agent responsible for executing a specific task. Your task is:

**TASK:** {task_description}

**Your responsibilities:**
1. Execute the task as described
2. Update the task status to 'in_progress' when you start
3. Complete the task and update status to 'completed' with output
4. If you encounter errors, update status to 'failed' with error message

**Available Tools:**
- update_task_status: Update your task's status and provide output
- log_message: Log your progress and reasoning
- get_current_time: Check time remaining

**Guidelines:**
- For this demo, keep execution simple and quick
- Provide clear output describing what you accomplished
- If the task is unclear or impossible, mark it as failed with explanation
- Always update the task status when done

**Important:** Since this is a demo environment, interpret tasks creatively but simply. For file/data tasks, describe what you would create. For analysis tasks, provide sample insights.

Begin executing the task now."""


class SubAgent(BaseAgent):
    """
    Sub-agent that executes a specific task.
    Purpose: Task executor - takes a task assignment and completes it.
    """
    
    def __init__(
        self,
        task_id: str,
        task_description: str,
        workflow_id: str,
        user_id: str,
        workflow_deadline: str,
        db_ops
    ):
        """Initialize sub-agent for specific task"""
        agent_id = f"sub_agent_{task_id}"
        system_prompt = get_sub_agent_system_prompt(task_description)
        
        super().__init__(
            agent_id=agent_id,
            system_prompt=system_prompt,
            db_ops=db_ops,
            workflow_id=workflow_id,
            user_id=user_id,
            workflow_deadline=workflow_deadline
        )
        
        self.task_id = task_id
        self.task_description = task_description
        self.workflow_id = workflow_id
    
    async def execute_task(self) -> Dict[str, Any]:
        """
        Execute the assigned task.
        Purpose: Main execution method - performs task and reports results.
        """
        logger.info(
            "sub_agent_executing",
            agent_id=self.agent_id,
            task_id=self.task_id,
            description=self.task_description
        )
        
        message = f"""Execute the task: "{self.task_description}"

Steps:
1. First, update task status to 'in_progress' (task_id: {self.task_id})
2. Execute the task (interpret creatively for demo purposes)
3. Update task status to 'completed' with your output, OR 'failed' with error message

Be specific about what you accomplished in the output."""
        
        result = await self.run(user_message=message, max_iterations=6)
        
        logger.info(
            "sub_agent_completed",
            agent_id=self.agent_id,
            task_id=self.task_id
        )
        
        return result
