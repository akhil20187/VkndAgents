# Testing Agent SDK Integration with Dashboard

## Test: Manual Task with File Operations

Create a task via dashboard that requires file operations to verify Agent SDK is working.

### Test Case
**Task Description:** "Read the README.md file and count how many times the word 'Temporal' appears"

### Expected Behavior
- Agent SDK subprocess should be spawned
- Agent should use the `Read` tool to open README.md
- Agent should count occurrences
- Result should be saved to database

### How to Test
1. Open dashboard at http://localhost:8500
2. Create new task with description above
3. Click "Start" button
4. Watch logs for "starting_agent_sdk_subprocess"
5. Verify task completes with count result

### Success Criteria
- ✅ Task status changes to "in_progress"
- ✅ Logs show "starting_agent_sdk_subprocess"
- ✅ Agent uses Read tool (visible in tool_calls)
- ✅ Task completes with accurate count
- ✅ No errors in execution
