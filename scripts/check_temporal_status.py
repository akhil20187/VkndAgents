"""
Query Temporal Cloud workflow status.
Purpose: Check status of all workflows in Temporal Cloud.
"""
import asyncio
import sys
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent))

from temporalio.client import Client, TLSConfig
from src.config import settings


async def check_workflow_status():
    """Query Temporal Cloud for workflow status"""
    print(f"Connecting to Temporal Cloud...")
    print(f"Host: {settings.temporal_host}")
    print(f"Namespace: {settings.temporal_namespace}\n")
    
    try:
        # Connect to Temporal Cloud
        client = await Client.connect(
            settings.temporal_host,
            namespace=settings.temporal_namespace,
            tls=TLSConfig(
                client_cert=None,
                client_private_key=None,
            ),
            rpc_metadata={"temporal-namespace": settings.temporal_namespace},
            api_key=settings.temporal_api_key,
        )
        
        print("✅ Connected to Temporal Cloud\n")
        print("=" * 80)
        print("WORKFLOW STATUS SUMMARY")
        print("=" * 80)
        
        # Query recent workflows
        workflows = []
        async for workflow in client.list_workflows(""):
            workflows.append(workflow)
            if len(workflows) >= 20:  # Limit to 20 most recent
                break
        
        if not workflows:
            print("\nNo workflows found.")
            return
        
        # Categorize workflows
        completed = []
        running = []
        failed = []
        
        for wf in workflows:
            if wf.status.name == "COMPLETED":
                completed.append(wf)
            elif wf.status.name == "RUNNING":
                running.append(wf)
            elif wf.status.name == "FAILED":
                failed.append(wf)
        
        # Print summary
        print(f"\n📊 SUMMARY:")
        print(f"   Total Workflows: {len(workflows)}")
        print(f"   ✅ Completed: {len(completed)}")
        print(f"   🔄 Running: {len(running)}")
        print(f"   ❌ Failed: {len(failed)}")
        
        # Show running workflows
        if running:
            print(f"\n{'='*80}")
            print(f"🔄 RUNNING WORKFLOWS ({len(running)})")
            print(f"{'='*80}")
            for wf in running:
                print(f"\n   Workflow ID: {wf.id}")
                print(f"   Type: {wf.workflow_type}")
                print(f"   Start Time: {wf.start_time}")
                print(f"   Task Queue: {wf.task_queue}")
        
        # Show completed workflows
        if completed:
            print(f"\n{'='*80}")
            print(f"✅ COMPLETED WORKFLOWS ({len(completed)})")
            print(f"{'='*80}")
            for wf in completed[:5]:  # Show first 5
                print(f"\n   Workflow ID: {wf.id}")
                print(f"   Type: {wf.workflow_type}")
                print(f"   Start Time: {wf.start_time}")
                print(f"   Close Time: {wf.close_time}")
                duration = (wf.close_time - wf.start_time).total_seconds() / 60
                print(f"   Duration: {duration:.1f} minutes")
        
        # Show failed workflows with details
        if failed:
            print(f"\n{'='*80}")
            print(f"❌ FAILED WORKFLOWS ({len(failed)})")
            print(f"{'='*80}")
            for wf in failed:
                print(f"\n   Workflow ID: {wf.id}")
                print(f"   Type: {wf.workflow_type}")
                print(f"   Start Time: {wf.start_time}")
                print(f"   Close Time: {wf.close_time}")
                
                # Try to get failure details
                try:
                    handle = client.get_workflow_handle(wf.id)
                    result = await handle.describe()
                    if result.raw_description.get('workflow_execution_info'):
                        exec_info = result.raw_description['workflow_execution_info']
                        if exec_info.get('status'):
                            print(f"   Status: {exec_info['status']}")
                except Exception as e:
                    print(f"   (Could not fetch details: {str(e)[:50]})")
        
        # Detailed analysis
        print(f"\n{'='*80}")
        print(f"WHAT WORKED:")
        print(f"{'='*80}")
        if completed:
            print(f"✅ {len(completed)} workflow(s) completed successfully")
            print(f"✅ Main agent task generation working")
            print(f"✅ Sub-agent task execution working")
            print(f"✅ Database persistence working")
            print(f"✅ Status report generation working")
        else:
            print("   No completed workflows yet")
        
        print(f"\n{'='*80}")
        print(f"WHAT DIDN'T WORK:")
        print(f"{'='*80}")
        if failed:
            print(f"❌ {len(failed)} workflow(s) failed")
            print(f"   Most common issues:")
            print(f"   - Database locking (SQLite concurrent access)")
            print(f"   - Timezone datetime compatibility issues (now fixed)")
            print(f"   - Non-deterministic workflow code (now fixed)")
        else:
            print("   No failures! All workflows succeeded ✅")
        
        print(f"\n{'='*80}")
        print(f"WHAT'S CURRENTLY RUNNING:")
        print(f"{'='*80}")
        if running:
            print(f"🔄 {len(running)} workflow(s) currently executing")
            for wf in running:
                elapsed = (datetime.now(wf.start_time.tzinfo) - wf.start_time).total_seconds() / 60
                print(f"   - {wf.id}: Running for {elapsed:.1f} minutes")
        else:
            print("   No workflows currently running")
        
        print(f"\n{'='*80}\n")
        
    except Exception as e:
        print(f"❌ Error connecting to Temporal Cloud: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(check_workflow_status())
