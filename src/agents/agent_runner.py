#!/usr/bin/env python3
"""
Agent SDK Runner - Subprocess wrapper for Claude Agent SDK.
Purpose: Run Claude Agent SDK as a subprocess from Temporal activities,
enabling full file operations, bash, and E2B integration.
"""
import asyncio
import argparse
import json
import sys
import os
from typing import Optional

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


async def run_agent(
    prompt: str,
    system_prompt: Optional[str] = None,
    allowed_tools: Optional[list] = None,
    cwd: Optional[str] = None,
    use_skills: bool = True,
    permission_mode: str = "acceptEdits"
) -> dict:
    """
    Run Claude Agent SDK with specified configuration.
    Purpose: Execute an agent task using Claude Agent SDK's built-in capabilities.
    
    Args:
        prompt: The task to execute
        system_prompt: Optional custom system prompt
        allowed_tools: List of tools to enable (default: Read, Edit, Bash, Glob, Skill)
        cwd: Working directory for the agent
        use_skills: Whether to load skills from .claude/skills/
        permission_mode: 'acceptEdits', 'bypassPermissions', or 'default'
    
    Returns:
        Dict with status, output, and any errors
    """
    from claude_agent_sdk import query, ClaudeAgentOptions, AssistantMessage, ResultMessage
    
    # Default tools - comprehensive set for autonomous operation
    if allowed_tools is None:
        allowed_tools = ["Read", "Edit", "Bash", "Glob", "Grep", "WebSearch"]
        if use_skills:
            allowed_tools.append("Skill")
    
    # Set working directory
    working_dir = cwd or os.getcwd()
    
    # Configure options
    options = ClaudeAgentOptions(
        cwd=working_dir,
        allowed_tools=allowed_tools,
        permission_mode=permission_mode,
    )
    
    # Add system prompt if provided
    if system_prompt:
        options.system_prompt = system_prompt
    
    # Load skills from filesystem if enabled
    if use_skills:
        options.setting_sources = ["project", "user"]
    
    # Collect output
    output_parts = []
    tool_calls = []
    final_result = None
    error = None
    
    try:
        async for message in query(prompt=prompt, options=options):
            # Handle different message types
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if hasattr(block, 'text'):
                        output_parts.append(block.text)
                    elif hasattr(block, 'name'):
                        tool_calls.append({
                            "tool": block.name,
                            "input": getattr(block, 'input', None)
                        })
            elif isinstance(message, ResultMessage):
                final_result = {
                    "subtype": message.subtype,
                    "result": getattr(message, 'result', None)
                }
            # Also handle raw text/content
            elif hasattr(message, 'text'):
                output_parts.append(message.text)
            elif hasattr(message, 'content'):
                if isinstance(message.content, str):
                    output_parts.append(message.content)
                    
    except Exception as e:
        error = str(e)
    
    return {
        "status": "error" if error else "success",
        "output": "\n".join(output_parts),
        "tool_calls": tool_calls,
        "final_result": final_result,
        "error": error
    }


def main():
    """
    CLI entry point for running agent from subprocess.
    Purpose: Allow Temporal activities to spawn this script with arguments.
    """
    parser = argparse.ArgumentParser(description="Run Claude Agent SDK task")
    parser.add_argument("--prompt", required=True, help="Task prompt for the agent")
    parser.add_argument("--system-prompt", help="Custom system prompt")
    parser.add_argument("--tools", help="Comma-separated list of allowed tools")
    parser.add_argument("--cwd", help="Working directory")
    parser.add_argument("--no-skills", action="store_true", help="Disable skills loading")
    parser.add_argument("--permission-mode", default="acceptEdits", 
                       choices=["acceptEdits", "bypassPermissions", "default"])
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    
    args = parser.parse_args()
    
    # Parse tools if provided
    allowed_tools = None
    if args.tools:
        allowed_tools = [t.strip() for t in args.tools.split(",")]
    
    # Run the agent
    result = asyncio.run(run_agent(
        prompt=args.prompt,
        system_prompt=args.system_prompt,
        allowed_tools=allowed_tools,
        cwd=args.cwd,
        use_skills=not args.no_skills,
        permission_mode=args.permission_mode
    ))
    
    # Output result
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        if result["error"]:
            print(f"ERROR: {result['error']}", file=sys.stderr)
            sys.exit(1)
        print(result["output"])
        if result["final_result"]:
            print(f"\n--- Result: {result['final_result']['subtype']} ---")


if __name__ == "__main__":
    main()
