#!/usr/bin/env python3
"""
Debug Auto-Remediation - Check why AI isn't marking errors as auto-healable
"""
import os
import sys
from dotenv import load_dotenv

# Load environment
load_dotenv()

# Import the AI provider system
from ai_providers import get_ai_manager

def test_rca_for_error(error_message, source="DATABRICKS"):
    """Test RCA generation for a specific error"""
    print(f"\n{'='*80}")
    print(f"Testing Error: {error_message[:100]}...")
    print(f"{'='*80}\n")

    # Get AI manager
    ai_manager = get_ai_manager()

    # Generate RCA
    metadata = {
        "job_id": "test-job",
        "run_id": "test-run",
        "cluster_id": "test-cluster"
    }

    result = ai_manager.generate_rca_with_fallback(
        error_message=error_message,
        source=source,
        metadata=metadata
    )

    rca = result.get("rca")
    provider_used = result.get("provider_used", "unknown")
    error_msg = result.get("error", "")
    success = rca is not None

    if not success:
        print(f"   ❌ Error: {error_msg}")

    if success and rca:
        print(f"✅ RCA Generated Successfully")
        print(f"   Provider: {provider_used}")
        print(f"\n📋 RCA Details:")
        print(f"   Error Type: {rca.get('error_type', 'N/A')}")
        print(f"   Severity: {rca.get('severity', 'N/A')}")
        print(f"   Priority: {rca.get('priority', 'N/A')}")
        print(f"   Auto-Heal Possible: {rca.get('auto_heal_possible', 'N/A')} {'✅' if rca.get('auto_heal_possible') else '❌'}")
        print(f"   Root Cause: {rca.get('root_cause', 'N/A')[:200]}...")

        if not rca.get('auto_heal_possible'):
            print(f"\n⚠️  WHY NOT AUTO-HEALABLE?")
            print(f"   The AI decided this error cannot be auto-healed.")
            print(f"   This might be because:")
            print(f"   - AI thinks it's an application/code error")
            print(f"   - Error message doesn't match known patterns")
            print(f"   - AI is being too conservative")
    else:
        print(f"❌ RCA Generation Failed")
        print(f"   Provider: {provider_used}")

    return rca if success else None


if __name__ == "__main__":
    print("🔍 Auto-Remediation Diagnostic Tool")
    print("="*80)

    # Test different error scenarios
    test_cases = [
        {
            "name": "Generic Python Exception (Current Test)",
            "error": "Exception: Cluster connection timeout: Unable to reach driver node after 30 seconds. This may be a temporary network issue."
        },
        {
            "name": "Databricks Native Timeout Error",
            "error": "org.apache.spark.SparkException: Job aborted due to stage failure: Task cannot be executed because driver is not responsive. Driver may have failed."
        },
        {
            "name": "Databricks Network Error",
            "error": "com.databricks.backend.common.rpc.DatabricksExceptions$SQLExecutionException: Databricks driver is unavailable. This typically indicates network connectivity issues or driver node failure."
        },
        {
            "name": "Spark Executor Lost",
            "error": "org.apache.spark.SparkException: Job aborted due to stage failure: Task 0 in stage 3.0 failed 4 times, most recent failure: ExecutorLostFailure (executor 2 exited caused by one of the running tasks) Reason: Remote RPC client disassociated. Likely due to containers exceeding thresholds, or network issues."
        },
        {
            "name": "Out of Memory",
            "error": "java.lang.OutOfMemoryError: GC overhead limit exceeded at org.apache.spark.executor.Executor$TaskRunner.run"
        }
    ]

    results = []
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n\n🧪 Test Case {i}/{len(test_cases)}: {test_case['name']}")
        rca = test_rca_for_error(test_case['error'])
        results.append({
            "name": test_case['name'],
            "auto_heal": rca.get('auto_heal_possible') if rca else False
        })

    print(f"\n\n{'='*80}")
    print(f"📊 SUMMARY")
    print(f"{'='*80}")

    for result in results:
        status = "✅ AUTO-HEAL" if result['auto_heal'] else "❌ NO AUTO-HEAL"
        print(f"   {status}: {result['name']}")

    auto_heal_count = sum(1 for r in results if r['auto_heal'])
    print(f"\n   Total: {auto_heal_count}/{len(results)} marked as auto-healable")

    if auto_heal_count == 0:
        print(f"\n⚠️  WARNING: No errors marked as auto-healable!")
        print(f"   This suggests the AI prompt needs improvement.")
        print(f"   The AI is not recognizing infrastructure errors as auto-healable.")
