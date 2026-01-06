import asyncio
import os
from claude_agent_sdk import ClaudeSDKClient, tool
from pydantic import BaseModel, Field

# Mock setting env var if not present (assuming it's loaded in main app)
# os.environ["ANTHROPIC_API_KEY"] = "your-key" 

class AddInput(BaseModel):
    a: int = Field(..., description="First number")
    b: int = Field(..., description="Second number")

@tool("add_numbers", input_schema=AddInput, description="Add two numbers together")
async def add_numbers(input: AddInput) -> int:
    return input.a + input.b

async def main():
    try:
        # Just checking instantiation and tool registration logic
        # We might not be able to actually make calls without a real key/network here depending on the env
        # but we want to see if the classes exist and take arguments as expected.
        
        # Note: The SDK might require specific initialization
        client = ClaudeSDKClient()
        print("✅ ClaudeSDKClient instantiated")
        print(f"Methods: {dir(client)}")
        
        # Verify tool decorator works
        print(f"✅ Tool 'add_numbers' defined: {add_numbers}")
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
