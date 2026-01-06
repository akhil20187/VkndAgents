import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from temporalio.client import Client, TLSConfig
from src.config import settings

async def main():
    client = await Client.connect(
        settings.temporal_host,
        namespace=settings.temporal_namespace,
        tls=TLSConfig(client_cert=None, client_private_key=None),
        api_key=settings.temporal_api_key,
    )
    
    print("Searching for recent failed workflows...")
    async for wf in client.list_workflows("ExecutionStatus='Failed'"):
        print(f"\nWorkflow ID: {wf.id}")
        print(f"Run ID: {wf.run_id}")
        print(f"End Time: {wf.close_time}")
        
        # Get history to find the error
        handle = client.get_workflow_handle(wf.id, run_id=wf.run_id)
        desc = await handle.describe()
        print(f"Status: {desc.status}")
        
        # Print failure info if available
        # The Temporal Python SDK Structure varies, let's look for known fields
        # Note: desc is a WorkflowExecutionDescription
        if hasattr(desc, 'info'):
             print(f"Info: {desc.info}")
        else:
             print(f"Items in desc: {dir(desc)}")
             
        # Try to look for closure info
        if hasattr(desc, 'raw_info'): # Sometimes raw_info or similar holds the proto
             print(f"Raw Info: {desc.raw_info}")
             
        # Also print history events (the last one usually has the error)
        print("\nLast 3 History Events:")
        async for event in handle.fetch_history_events():
             # We want the last ones, but this iterator creates a list
             pass
        
        # Better: just iterate and keep last 3
        events = []
        async for event in handle.fetch_history_events():
             events.append(event)
        
        for event in events[-3:]:
             print(f"Event: {event.event_type}")
             if event.workflow_execution_failed_event_attributes:
                  print(f"FAILURE DETAILS: {event.workflow_execution_failed_event_attributes}")
             if event.workflow_execution_timed_out_event_attributes:
                  print(f"TIMEOUT DETAILS: {event.workflow_execution_timed_out_event_attributes}")

if __name__ == "__main__":
    asyncio.run(main())
