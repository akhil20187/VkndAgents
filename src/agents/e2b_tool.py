"""
E2B Tool - Helper module for E2B sandbox integration.
Purpose: Provide a simple interface for executing code in E2B cloud sandboxes,
which is used by the code-execution skill.
"""
import asyncio
import json
import os
import sys
from typing import Optional, Dict, Any
import structlog

# Add project root to path for direct execution
if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    # Load .env file
    from dotenv import load_dotenv
    load_dotenv()

from src.config import settings

logger = structlog.get_logger()


class E2BSandbox:
    """
    E2B Sandbox wrapper for code execution.
    Purpose: Execute Python/JavaScript code safely in isolated cloud environment.
    """
    
    def __init__(self):
        """Initialize E2B sandbox helper."""
        self.api_key = getattr(settings, 'e2b_api_key', None)
        if not self.api_key:
            import os
            self.api_key = os.environ.get('E2B_API_KEY')
    
    async def execute_python(
        self,
        code: str,
        packages: Optional[list] = None,
        timeout: int = getattr(settings, 'e2b_timeout_seconds', 300)
    ) -> Dict[str, Any]:
        """
        Execute Python code in E2B sandbox.
        Purpose: Run arbitrary Python code in isolated environment.
        
        Args:
            code: Python code to execute
            packages: Optional list of pip packages to install
            timeout: Execution timeout in seconds
            
        Returns:
            Dict with stdout, stderr, and exit_code
        """
        try:
            from e2b_code_interpreter import Sandbox
        except ImportError:
            return {
                "success": False,
                "stdout": "",
                "stderr": "E2B code-interpreter not installed. Run: pip install e2b-code-interpreter",
                "exit_code": 1
            }
        
        if not self.api_key:
            return {
                "success": False,
                "stdout": "",
                "stderr": "E2B_API_KEY not set. Set the environment variable or add to .env",
                "exit_code": 1
            }
        
        try:
            # Set API key in environment (E2B SDK reads from env)
            import os
            os.environ['E2B_API_KEY'] = self.api_key
            
            # Create sandbox (synchronous in v2.x)
            sandbox = Sandbox.create(timeout=timeout)
            
            # Install packages if requested
            if packages:
                install_code = f"!pip install {' '.join(packages)}"
                sandbox.run_code(install_code)
            
            # Execute the code
            execution = sandbox.run_code(code)
            
            # Close sandbox
            sandbox.kill()
            
            logger.info("e2b_code_executed", 
                       code_length=len(code),
                       packages=packages,
                       success=not execution.error)
            
            return {
                "success": not execution.error,
                "stdout": "\n".join(execution.logs.stdout) if hasattr(execution.logs, 'stdout') else "",
                "stderr": execution.error.value if execution.error else "",
                "exit_code": 1 if execution.error else 0,
                "results": execution.results if hasattr(execution, 'results') else []
            }
            
        except Exception as e:
            logger.error("e2b_execution_error", error=str(e))
            return {
                "success": False,
                "stdout": "",
                "stderr": str(e),
                "exit_code": 1
            }
    
    async def execute_javascript(
        self,
        code: str,
        packages: Optional[list] = None
    ) -> Dict[str, Any]:
        """
        Execute JavaScript code in E2B sandbox.
        Purpose: Run JavaScript/Node.js code in isolated environment.
        """
        # E2B code-interpreter is Python-focused
        # For JS, would need different approach
        return {
            "success": False,
            "stdout": "",
            "stderr": "JavaScript execution not yet implemented. E2B code-interpreter focuses on Python.",
            "exit_code": 1
        }


class ClaudeCodeSandbox:
    """
    E2B Sandbox wrapper for Claude Code CLI execution.
    Purpose: Run Claude Agent in an isolated E2B sandbox with file sync.
    """
    
    def __init__(self, template_id: Optional[str] = None):
        """Initialize Claude Code sandbox helper."""
        self.api_key = getattr(settings, 'e2b_api_key', None) or os.environ.get('E2B_API_KEY')
        self.template_id = template_id or getattr(settings, 'e2b_claude_template_id', 'vqvrux7k1ay0yvczh8e3')
        self.project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.sandbox = None
    
    async def execute_prompt(
        self,
        prompt: str,
        task_id: Optional[str] = None,
        sync_output_dir: Optional[str] = None,
        timeout_seconds: int = getattr(settings, 'e2b_timeout_seconds', 300)
    ) -> Dict[str, Any]:
        """
        Execute a prompt using Claude Code CLI in E2B sandbox.
        Purpose: Run Claude agent tasks in isolated environment with file sync.
        
        Args:
            prompt: The task prompt for Claude
            task_id: Optional task ID to organize output in output/{task_id}/
            sync_output_dir: Local directory to sync output files to (default: output/{task_id}/ or project root)
            timeout_seconds: Execution timeout
            
        Returns:
            Dict with status, stdout, stderr, synced_files, output_dir
        """
        try:
            from e2b import Sandbox
        except ImportError:
            return {
                "success": False,
                "stdout": "",
                "stderr": "E2B SDK not installed. Run: pip install e2b",
                "exit_code": 1,
                "synced_files": []
            }
        
        if not self.api_key:
            return {
                "success": False,
                "stdout": "",
                "stderr": "E2B_API_KEY not set.",
                "exit_code": 1,
                "synced_files": []
            }
        
        # Determine output directory: output/{task_id}/ if task_id provided, else sync_output_dir, else project_root
        if task_id:
            sync_dir = os.path.join(self.project_root, "output", task_id)
        else:
            sync_dir = sync_output_dir or self.project_root
        
        # Create output directory if it doesn't exist
        os.makedirs(sync_dir, exist_ok=True)
        
        synced_files = []
        output_dir = sync_dir  # Track output dir for return value
        
        try:
            # Set API key in environment
            os.environ['E2B_API_KEY'] = self.api_key
            
            logger.info("e2b_claude_sandbox_starting", template_id=self.template_id)
            
            # Create sandbox from template with ANTHROPIC_API_KEY and ANTHROPIC_MODEL
            anthropic_key = getattr(settings, 'anthropic_api_key', None) or os.environ.get('ANTHROPIC_API_KEY')
            anthropic_model = getattr(settings, 'anthropic_model', None) or os.environ.get('ANTHROPIC_MODEL')
            
            envs = {}
            if anthropic_key:
                envs["ANTHROPIC_API_KEY"] = anthropic_key
            if anthropic_model:
                envs["ANTHROPIC_MODEL"] = anthropic_model

            self.sandbox = Sandbox.create(
                template=self.template_id, 
                timeout=timeout_seconds,
                envs=envs if envs else None
            )
            
            # Upload skills to the sandbox
            skills_dir = os.path.join(self.project_root, '.claude', 'skills')
            if os.path.exists(skills_dir):
                await self._upload_directory(skills_dir, '/home/user/.claude/skills')
                logger.info("e2b_skills_uploaded", skills_dir=skills_dir)
            
            # Escape single quotes in the prompt for shell safety
            escaped_prompt = prompt.replace("'", "'\\''")
            
            # Run Claude CLI with the prompt
            command = f"echo '{escaped_prompt}' | claude -p --dangerously-skip-permissions"
            
            logger.info("e2b_claude_executing", command_preview=command[:100])
            
            result = self.sandbox.commands.run(command, timeout=timeout_seconds)
            
            stdout = result.stdout or ""
            stderr = result.stderr or ""
            exit_code = result.exit_code
            
            logger.info("e2b_claude_executed", 
                       exit_code=exit_code, 
                       stdout_len=len(stdout),
                       stderr_len=len(stderr))
            
            # Download created files from /home/user before killing sandbox
            synced_files = await self._sync_files_from_sandbox(sync_dir)
            
            logger.info("e2b_files_synced", count=len(synced_files), files=synced_files)
            
            return {
                "success": exit_code == 0,
                "stdout": stdout,
                "stderr": stderr,
                "exit_code": exit_code,
                "synced_files": synced_files,
                "output_dir": output_dir
            }
            
        except Exception as e:
            logger.error("e2b_claude_error", error=str(e))
            return {
                "success": False,
                "stdout": "",
                "stderr": str(e),
                "exit_code": 1,
                "synced_files": synced_files
            }
        finally:
            if self.sandbox:
                try:
                    self.sandbox.kill()
                    logger.info("e2b_sandbox_killed")
                except:
                    pass
    
    async def _upload_directory(self, local_dir: str, remote_dir: str):
        """Upload a local directory to the sandbox."""
        for root, dirs, files in os.walk(local_dir):
            for file in files:
                local_path = os.path.join(root, file)
                relative_path = os.path.relpath(local_path, local_dir)
                remote_path = os.path.join(remote_dir, relative_path)
                
                # Ensure remote directory exists
                remote_parent = os.path.dirname(remote_path)
                self.sandbox.commands.run(f"mkdir -p '{remote_parent}'")
                
                # Read and upload file
                with open(local_path, 'rb') as f:
                    content = f.read()
                self.sandbox.files.write(remote_path, content)
    
    async def _sync_files_from_sandbox(self, local_dir: str) -> list:
        """
        Download files created in the sandbox to local directory.
        Purpose: Sync output files (HTML, code, etc.) back to the project.
        """
        synced = []
        
        # List files in /home/user (excluding hidden dirs like .cache, .npm)
        result = self.sandbox.commands.run("find /home/user -maxdepth 2 -type f ! -path '*/\\.*' 2>/dev/null || true")
        
        if not result.stdout:
            return synced
        
        for remote_path in result.stdout.strip().split('\n'):
            if not remote_path or remote_path.startswith('/home/user/.'):
                continue
            
            try:
                # Get file content
                content = self.sandbox.files.read(remote_path)
                
                # Determine local filename (just the basename for simplicity)
                filename = os.path.basename(remote_path)
                local_path = os.path.join(local_dir, filename)
                
                # Write to local (handle both str and bytes)
                if isinstance(content, str):
                    with open(local_path, 'w', encoding='utf-8') as f:
                        f.write(content)
                else:
                    with open(local_path, 'wb') as f:
                        f.write(content)
                
                synced.append(filename)
                logger.info("e2b_file_synced", remote=remote_path, local=local_path)
                
            except Exception as e:
                logger.warning("e2b_file_sync_failed", remote=remote_path, error=str(e))
        
        return synced


async def execute_code(
    code: str,
    language: str = "python",
    packages: Optional[list] = None
) -> Dict[str, Any]:
    """
    Convenience function to execute code in E2B.
    Purpose: Simple interface for code execution from skills or tools.
    
    Args:
        code: Code to execute
        language: 'python' or 'javascript'
        packages: Optional list of packages to install
        
    Returns:
        Execution result dict
    """
    sandbox = E2BSandbox()
    
    if language.lower() == "python":
        return await sandbox.execute_python(code, packages)
    elif language.lower() in ["javascript", "js", "node"]:
        return await sandbox.execute_javascript(code, packages)
    else:
        return {
            "success": False,
            "stdout": "",
            "stderr": f"Unsupported language: {language}. Use 'python' or 'javascript'.",
            "exit_code": 1
        }


# CLI interface for testing
if __name__ == "__main__":
    import sys
    
    code = """
import pandas as pd
import numpy as np

# Create sample data
data = {
    'product': ['A', 'B', 'C', 'D', 'E'],
    'sales': [100, 150, 200, 175, 225],
    'profit': [20, 30, 45, 35, 50]
}

df = pd.DataFrame(data)

print("Sales Analysis:")
print(f"Total Sales: ${df['sales'].sum()}")
print(f"Average Sales: ${df['sales'].mean():.2f}")
print(f"Total Profit: ${df['profit'].sum()}")
print(f"Profit Margin: {(df['profit'].sum() / df['sales'].sum() * 100):.1f}%")
print(f"\\nTop Product: {df.loc[df['sales'].idxmax(), 'product']} with ${df['sales'].max()} in sales")
"""
    
    result = asyncio.run(execute_code(code, packages=["pandas", "numpy"]))
    print(json.dumps(result, indent=2))
