"""
Base agent implementation using Anthropic Claude SDK.
Purpose: Provide base functionality for all agents including tool execution and message handling.
"""
from anthropic import AsyncAnthropic
from datetime import datetime
from typing import List, Dict, Any, Optional
import structlog
import json
from src.config import settings

logger = structlog.get_logger()


class BaseAgent:
    """
    Base class for all agents (main and sub-agents).
    Purpose: Handle Claude API interactions with direct SDK for reliability.
    """
    
    def __init__(
        self,
        agent_id: str,
        system_prompt: str,
        db_ops,
        workflow_id: str,
        user_id: str,
        workflow_deadline: str,
        model: Optional[str] = None
    ):
        """
        Initialize agent with context parameters.
        """
        self.agent_id = agent_id
        self.system_prompt = system_prompt
        self.db_ops = db_ops
        self.workflow_id = workflow_id
        self.user_id = user_id
        self.workflow_deadline = datetime.fromisoformat(workflow_deadline) if isinstance(workflow_deadline, str) else workflow_deadline
        self.model = model or settings.anthropic_model
        
        # Initialize Anthropic client
        self.client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        
        logger.info("agent_initialized", agent_id=agent_id, model=self.model)
    
    def _get_tools_definition(self) -> List[Dict[str, Any]]:
        """
        Get tool definitions for the Anthropic API.
        Purpose: Return tools in the format expected by the Anthropic messages API.
        """
        return [
            {
                "name": "create_task",
                "description": "Create a new task with a description. The task will be added to the pending queue.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "description": {
                            "type": "string",
                            "description": "Clear description of what the task should accomplish"
                        }
                    },
                    "required": ["description"]
                }
            },
            {
                "name": "update_task_status",
                "description": "Update the status of an existing task. Use this to mark tasks as completed or failed.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "task_id": {"type": "string", "description": "ID of the task to update"},
                        "status": {"type": "string", "enum": ["pending", "in_progress", "completed", "failed"]},
                        "output": {"type": "string", "description": "Optional output or result from the task"},
                        "error_message": {"type": "string", "description": "Optional error message if task failed"}
                    },
                    "required": ["task_id", "status"]
                }
            },
            {
                "name": "query_tasks",
                "description": "Query tasks, optionally filtering by status.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "status": {"type": "string", "enum": ["generated", "pending", "in_progress", "completed", "failed"]}
                    },
                    "required": []
                }
            },
            {
                "name": "query_history",
                "description": "Query historical task data from previous workflows.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "days": {"type": "integer", "description": "Number of days of history to retrieve", "default": 7}
                    },
                    "required": []
                }
            },
            {
                "name": "get_current_time",
                "description": "Get the current time and workflow deadline information.",
                "input_schema": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },
            {
                "name": "log_message",
                "description": "Log a message for debugging or tracking purposes.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "message": {"type": "string", "description": "The message to log"},
                        "level": {"type": "string", "enum": ["info", "warning", "error"], "default": "info"}
                    },
                    "required": ["message"]
                }
            }
        ]
    
    async def _execute_tool(self, tool_name: str, tool_input: Dict[str, Any]) -> str:
        """
        Execute a tool and return the result as a string.
        Purpose: Bridge between Claude's tool calls and our database operations.
        """
        import uuid
        
        try:
            if tool_name == "create_task":
                task_id = f"task_{uuid.uuid4().hex[:8]}"
                await self.db_ops.create_task(
                    task_id=task_id,
                    user_id=self.user_id,
                    workflow_id=self.workflow_id,
                    description=tool_input["description"],
                    status="pending"
                )
                return json.dumps({"success": True, "task_id": task_id, "status": "pending"})
            
            elif tool_name == "update_task_status":
                await self.db_ops.update_task_status(
                    task_id=tool_input["task_id"],
                    status=tool_input["status"],
                    output=tool_input.get("output"),
                    error_message=tool_input.get("error_message")
                )
                return json.dumps({"success": True, "task_id": tool_input["task_id"], "new_status": tool_input["status"]})
            
            elif tool_name == "query_tasks":
                tasks = await self.db_ops.get_tasks_for_workflow(
                    self.workflow_id,
                    status=tool_input.get("status")
                )
                return json.dumps({"tasks": tasks})
            
            elif tool_name == "query_history":
                days = tool_input.get("days", 7)
                history = await self.db_ops.get_task_history(self.user_id, days=days)
                return json.dumps({"history": history})
            
            elif tool_name == "get_current_time":
                # Ensure we have timezone-aware current time matching the deadline
                if self.workflow_deadline.tzinfo:
                    now = datetime.now(self.workflow_deadline.tzinfo)
                else:
                    now = datetime.now()
                    
                remaining = (self.workflow_deadline - now).total_seconds() / 60
                return json.dumps({
                    "current_time": now.isoformat(),
                    "deadline": self.workflow_deadline.isoformat(),
                    "minutes_remaining": round(remaining, 1)
                })
            
            elif tool_name == "log_message":
                level = tool_input.get("level", "info")
                message = tool_input["message"]
                if level == "warning":
                    logger.warning("agent_log", agent_id=self.agent_id, message=message)
                elif level == "error":
                    logger.error("agent_log", agent_id=self.agent_id, message=message)
                else:
                    logger.info("agent_log", agent_id=self.agent_id, message=message)
                return json.dumps({"logged": True, "level": level, "message": message})
            
            else:
                return json.dumps({"error": f"Unknown tool: {tool_name}"})
                
        except Exception as e:
            logger.error("tool_execution_error", tool=tool_name, error=str(e))
            return json.dumps({"error": str(e)})
    
    async def run(
        self,
        user_message: str,
        max_iterations: int = 15
    ) -> Dict[str, Any]:
        """
        Run the agent with an agentic tool-use loop.
        Purpose: Process user request, execute tools as needed, return final response.
        """
        try:
            messages = [{"role": "user", "content": user_message}]
            tools = self._get_tools_definition()
            iterations = 0
            
            while iterations < max_iterations:
                iterations += 1
                
                try:
                    response = await self.client.messages.create(
                        model=self.model,
                        max_tokens=4096,
                        system=self.system_prompt,
                        tools=tools,
                        messages=messages
                    )
                except Exception as e:
                    logger.error("api_call_failed", agent_id=self.agent_id, error=str(e))
                    return {
                        "agent_id": self.agent_id,
                        "final_response": f"API Error: {str(e)}",
                        "iterations": iterations,
                        "conversation_length": len(messages)
                    }
                
                # Check if model wants to use tools
                if response.stop_reason == "tool_use":
                    # Add assistant message with tool use
                    messages.append({"role": "assistant", "content": response.content})
                    
                    # Process each tool use
                    tool_results = []
                    for block in response.content:
                        if block.type == "tool_use":
                            result = await self._execute_tool(block.name, block.input)
                            tool_results.append({
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": result
                            })
                    
                    # Add tool results
                    messages.append({"role": "user", "content": tool_results})
                    
                elif response.stop_reason == "end_turn":
                    # Extract final text response
                    final_text = ""
                    for block in response.content:
                        if hasattr(block, 'text'):
                            final_text += block.text
                    
                    logger.info("agent_completed", agent_id=self.agent_id, iterations=iterations)
                    
                    return {
                        "agent_id": self.agent_id,
                        "final_response": final_text or "Task completed.",
                        "iterations": iterations,
                        "conversation_length": len(messages)
                    }
                
                else:
                    # Unexpected stop reason
                    final_text = ""
                    for block in response.content:
                        if hasattr(block, 'text'):
                            final_text += block.text
                    
                    return {
                        "agent_id": self.agent_id,
                        "final_response": final_text or f"Stopped: {response.stop_reason}",
                        "iterations": iterations,
                        "conversation_length": len(messages)
                    }
            
            # Max iterations reached
            logger.warning("max_iterations_reached", agent_id=self.agent_id)
            return {
                "agent_id": self.agent_id,
                "final_response": "Max iterations reached without completion.",
                "iterations": iterations,
                "conversation_length": len(messages)
            }
            
        except Exception as e:
            import traceback
            with open("debug_agent_error.log", "w") as f:
                f.write(f"Error in BaseAgent.run: {str(e)}\n")
                f.write(traceback.format_exc())
            raise e
