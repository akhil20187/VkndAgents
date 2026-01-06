"""
Test script for hybrid Agent SDK + E2B integration.
Purpose: Verify all components work together correctly.
"""
import asyncio
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.agents.e2b_tool import execute_code


async def test_e2b_execution():
    """Test E2B code execution."""
    print("=" * 60)
    print("TEST 1: E2B Code Execution")
    print("=" * 60)
    
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
    
    result = await execute_code(code, language="python", packages=["pandas", "numpy"])
    
    print(f"\nStatus: {'✅ SUCCESS' if result['success'] else '❌ FAILED'}")
    print(f"\nOutput:\n{result['stdout']}")
    if result['stderr']:
        print(f"\nErrors:\n{result['stderr']}")
    
    return result['success']


async def test_agent_sdk_file_ops():
    """Test Agent SDK file operations."""
    print("\n" + "=" * 60)
    print("TEST 2: Agent SDK File Operations")
    print("=" * 60)
    
    # This will be tested via agent_runner.py
    import subprocess
    
    cmd = [
        "./venv/bin/python",
        "src/agents/agent_runner.py",
        "--prompt", "List all Python files in the src/agents directory",
        "--cwd", os.getcwd(),
        "--tools", "Bash,Glob,Read",
        "--no-skills",
        "--json"
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    
    if result.returncode == 0:
        import json
        data = json.loads(result.stdout)
        print(f"\nStatus: ✅ SUCCESS")
        print(f"\nAgent Output:\n{data.get('output', '')[:500]}...")
        print(f"\nTools Used: {len(data.get('tool_calls', []))} tool calls")
        return True
    else:
        print(f"\nStatus: ❌ FAILED")
        print(f"\nError: {result.stderr}")
        return False


async def test_skills_integration():
    """Test Skills integration."""
    print("\n" + "=" * 60)
    print("TEST 3: Skills Integration")
    print("=" * 60)
    
    import subprocess
    
    cmd = [
        "./venv/bin/python",
        "src/agents/agent_runner.py",
        "--prompt", "What skills are available?",
        "--cwd", os.getcwd(),
        "--json"
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    
    if result.returncode == 0:
        import json
        data = json.loads(result.stdout)
        print(f"\nStatus: ✅ SUCCESS")
        print(f"\nAgent Response:\n{data.get('output', '')[:800]}...")
        return True
    else:
        print(f"\nStatus: ❌ FAILED")
        print(f"\nError: {result.stderr}")
        return False


async def main():
    """Run all tests."""
    print("\n🧪 HYBRID AGENT SDK + E2B INTEGRATION TESTS\n")
    
    results = []
    
    # Test 1: E2B
    try:
        results.append(("E2B Code Execution", await test_e2b_execution()))
    except Exception as e:
        print(f"\n❌ E2B Test Failed: {e}")
        results.append(("E2B Code Execution", False))
    
    # Test 2: Agent SDK File Ops
    try:
        results.append(("Agent SDK File Ops", await test_agent_sdk_file_ops()))
    except Exception as e:
        print(f"\n❌ Agent SDK Test Failed: {e}")
        results.append(("Agent SDK File Ops", False))
    
    # Test 3: Skills
    try:
        results.append(("Skills Integration", await test_skills_integration()))
    except Exception as e:
        print(f"\n❌ Skills Test Failed: {e}")
        results.append(("Skills Integration", False))
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{test_name:.<40} {status}")
    
    total = len(results)
    passed = sum(1 for _, p in results if p)
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed! Hybrid system is working correctly.")
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Check output above for details.")


if __name__ == "__main__":
    asyncio.run(main())
