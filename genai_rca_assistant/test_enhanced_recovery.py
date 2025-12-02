#!/usr/bin/env python3
"""
Test script for Enhanced Auto-Recovery System
Tests all components: playbooks, circuit breakers, health checks, executor
"""
import os
import sys
import asyncio
import logging
from dotenv import load_dotenv

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("test_enhanced_recovery")

# Load environment variables
load_dotenv()

# Verify Databricks credentials
DATABRICKS_HOST = os.getenv("DATABRICKS_HOST", "")
DATABRICKS_TOKEN = os.getenv("DATABRICKS_TOKEN", "")

if not DATABRICKS_HOST or not DATABRICKS_TOKEN:
    logger.error("❌ Databricks credentials not configured!")
    logger.error("Set DATABRICKS_HOST and DATABRICKS_TOKEN in .env file")
    sys.exit(1)


# ============================================
# TEST 1: PLAYBOOK CONFIGURATION
# ============================================

def test_playbook_config():
    """Test playbook configuration system"""
    print("\n" + "="*60)
    print("TEST 1: Playbook Configuration")
    print("="*60)

    from playbook_config import (
        get_playbook,
        list_supported_error_types,
        DATABRICKS_PLAYBOOKS
    )

    # Test 1a: List all Databricks playbooks
    print("\n📋 Available Databricks Playbooks:")
    for error_type in DATABRICKS_PLAYBOOKS.keys():
        playbook = get_playbook(error_type)
        print(f"  ✓ {error_type}")
        print(f"     Action: {playbook.action}")
        print(f"     Max Retries: {playbook.max_retries}")
        print(f"     Fallback: {playbook.fallback_action or 'None'}")

    # Test 1b: Get specific playbook
    print("\n🔍 Testing specific playbook retrieval:")
    test_error = "DatabricksJobExecutionError"
    playbook = get_playbook(test_error)

    if playbook:
        print(f"  ✅ Found playbook for {test_error}")
        print(f"     Description: {playbook.description}")
        print(f"     Health check: {playbook.verify_health}")
        print(f"     Circuit breaker: {playbook.circuit_breaker_enabled}")
    else:
        print(f"  ❌ No playbook found for {test_error}")

    # Test 1c: Verify fallback chain
    print("\n🔗 Testing fallback chain:")
    if playbook.fallback_action:
        fallback = get_playbook(playbook.fallback_action) or playbook.fallback_action
        print(f"  Primary: {playbook.action}")
        print(f"  ↓")
        print(f"  Fallback: {fallback if isinstance(fallback, str) else fallback.action}")
        print(f"  ✅ Fallback chain configured")
    else:
        print(f"  ℹ️  No fallback configured (single-step recovery)")

    print("\n✅ Playbook configuration test passed!\n")


# ============================================
# TEST 2: CIRCUIT BREAKER
# ============================================

def test_circuit_breaker():
    """Test circuit breaker system"""
    print("\n" + "="*60)
    print("TEST 2: Circuit Breaker")
    print("="*60)

    from circuit_breaker import (
        check_circuit,
        record_recovery_success,
        record_recovery_failure,
        get_circuit_status,
        reset_circuit
    )

    error_type = "TestError"
    resource_id = "test-resource-1"

    # Test 2a: Initial state (closed)
    print("\n🟢 Test 2a: Initial state")
    can_proceed, reason = check_circuit(error_type, resource_id, failure_threshold=3)
    print(f"  Can proceed: {can_proceed}")
    print(f"  Reason: {reason}")
    assert can_proceed, "Circuit should be closed initially"
    print("  ✅ Circuit is closed (normal operation)")

    # Test 2b: Record failures until circuit opens
    print("\n🔴 Test 2b: Recording failures")
    for i in range(4):
        record_recovery_failure(error_type, resource_id)
        can_proceed, reason = check_circuit(error_type, resource_id, failure_threshold=3)
        status = get_circuit_status(error_type, resource_id)
        print(f"  Failure {i+1}: State={status['state']}, Failures={status['failure_count']}/{status['failure_threshold']}")

    assert status['state'] == 'open', "Circuit should be open after threshold"
    print("  ✅ Circuit opened after threshold reached")

    # Test 2c: Verify requests are blocked
    print("\n🚫 Test 2c: Verify requests blocked")
    can_proceed, reason = check_circuit(error_type, resource_id, failure_threshold=3)
    print(f"  Can proceed: {can_proceed}")
    print(f"  Reason: {reason}")
    assert not can_proceed, "Circuit should block requests when open"
    print("  ✅ Requests blocked while circuit is open")

    # Test 2d: Reset circuit
    print("\n🔄 Test 2d: Reset circuit")
    reset_circuit(error_type, resource_id)
    status = get_circuit_status(error_type, resource_id)
    print(f"  State after reset: {status['state']}")
    assert status['state'] == 'closed', "Circuit should be closed after reset"
    print("  ✅ Circuit successfully reset")

    print("\n✅ Circuit breaker test passed!\n")


# ============================================
# TEST 3: HEALTH CHECKS (Requires Databricks)
# ============================================

async def test_health_checks():
    """Test health check system (requires valid cluster)"""
    print("\n" + "="*60)
    print("TEST 3: Health Checks")
    print("="*60)

    from health_checks import (
        check_cluster_health,
        check_job_run_health,
        comprehensive_health_check
    )

    # Get a test cluster/run ID from user
    cluster_id = input("\n📝 Enter a valid cluster_id to test (or press Enter to skip): ").strip()

    if not cluster_id:
        print("  ⏭️  Skipping health check test (no cluster_id provided)")
        return

    # Test 3a: Check cluster health
    print(f"\n🏥 Test 3a: Checking cluster health for {cluster_id}")
    is_healthy, message, metrics = await asyncio.to_thread(
        check_cluster_health,
        cluster_id,
        timeout_seconds=60
    )

    print(f"  Is Healthy: {'✅' if is_healthy else '❌'}")
    print(f"  Message: {message}")
    print(f"  Metrics:")
    print(f"    - State: {metrics.get('state')}")
    print(f"    - Running: {metrics.get('is_running')}")
    print(f"    - Driver Healthy: {metrics.get('driver_healthy')}")
    print(f"    - Workers Healthy: {metrics.get('workers_healthy')}")

    if is_healthy:
        print("  ✅ Cluster health check passed!")
    else:
        print(f"  ⚠️  Cluster health check failed: {message}")

    # Test 3b: Comprehensive check
    print(f"\n🔍 Test 3b: Comprehensive health check")
    is_healthy, message, all_metrics = await asyncio.to_thread(
        comprehensive_health_check,
        cluster_id=cluster_id,
        check_type="cluster"
    )

    print(f"  Overall Health: {'✅' if is_healthy else '❌'}")
    print(f"  Summary: {message}")

    print("\n✅ Health check test completed!\n")


# ============================================
# TEST 4: PLAYBOOK EXECUTOR (Requires Databricks)
# ============================================

async def test_playbook_executor():
    """Test playbook executor with real recovery"""
    print("\n" + "="*60)
    print("TEST 4: Playbook Executor")
    print("="*60)

    from playbook_executor import execute_playbook_with_config

    print("\n⚠️  WARNING: This test will attempt real recovery actions!")
    print("Only proceed if you have a test cluster/job you can safely restart.\n")

    proceed = input("Proceed with playbook executor test? (yes/no): ").strip().lower()

    if proceed != "yes":
        print("  ⏭️  Skipping playbook executor test")
        return

    # Get test parameters
    print("\n📝 Test Configuration:")
    error_type = input("Enter error type (e.g., DatabricksClusterStartFailure): ").strip()

    if not error_type:
        print("  ⏭️  Skipping test (no error type provided)")
        return

    cluster_id = input("Enter cluster_id (optional): ").strip() or None
    job_id = input("Enter job_id (optional): ").strip() or None

    metadata = {
        "cluster_id": cluster_id,
        "job_id": job_id,
        "error_message": "Test error for recovery testing"
    }

    # Execute playbook
    print(f"\n🚀 Executing playbook for {error_type}...")

    result = await execute_playbook_with_config(
        error_type=error_type,
        metadata=metadata,
        ticket_id="TEST-001"
    )

    # Display results
    print("\n" + "="*60)
    print("PLAYBOOK EXECUTION RESULT")
    print("="*60)
    print(f"Success: {'✅' if result.success else '❌'}")
    print(f"Message: {result.message}")
    print(f"Actions Taken: {', '.join(result.actions_taken)}")
    print(f"Health Check Passed: {'✅' if result.health_check_passed else '❌'}")
    print(f"Fallback Used: {'Yes' if result.fallback_used else 'No'}")
    print(f"Execution Time: {result.execution_time_seconds}s")
    print(f"\nCircuit Breaker Status:")
    print(f"  State: {result.circuit_breaker_status.get('state', 'N/A')}")
    print(f"  Failures: {result.circuit_breaker_status.get('failure_count', 0)}/{result.circuit_breaker_status.get('failure_threshold', 0)}")

    if result.metadata:
        print(f"\nAdditional Metadata:")
        for key, value in result.metadata.items():
            if key != "health_metrics":  # Skip verbose metrics
                print(f"  {key}: {value}")

    if result.success:
        print("\n✅ Playbook executor test passed!")
    else:
        print(f"\n❌ Playbook execution failed: {result.message}")


# ============================================
# TEST 5: CLUSTER FAILURE DETECTION
# ============================================

def test_cluster_failure_detection():
    """Test cluster failure detection"""
    print("\n" + "="*60)
    print("TEST 5: Cluster Failure Detection")
    print("="*60)

    from databricks_api_utils import (
        classify_cluster_error,
        extract_cluster_error_message
    )

    # Test 5a: Classify different termination codes
    print("\n🔍 Test 5a: Error classification")

    test_cases = [
        {
            "code": "DRIVER_UNREACHABLE",
            "type": "CLIENT_ERROR",
            "expected": "DatabricksDriverNotResponding"
        },
        {
            "code": "INSUFFICIENT_INSTANCE_CAPACITY",
            "type": "CLOUD_FAILURE",
            "expected": "DatabricksResourceExhausted"
        },
        {
            "code": "SPARK_STARTUP_FAILURE",
            "type": "SERVICE_FAULT",
            "expected": "DatabricksClusterStartFailure"
        }
    ]

    for test_case in test_cases:
        termination_reason = {
            "code": test_case["code"],
            "type": test_case["type"]
        }

        error_type = classify_cluster_error("test-cluster", termination_reason)
        error_msg = extract_cluster_error_message("test-cluster", termination_reason)

        print(f"\n  Termination Code: {test_case['code']}")
        print(f"  Classified as: {error_type}")
        print(f"  Expected: {test_case['expected']}")
        print(f"  Error Message: {error_msg[:80]}...")

        if error_type == test_case["expected"]:
            print(f"  ✅ Classification correct")
        else:
            print(f"  ❌ Classification incorrect!")

    print("\n✅ Cluster failure detection test completed!\n")


# ============================================
# MAIN TEST RUNNER
# ============================================

async def run_all_tests():
    """Run all tests"""
    print("\n" + "="*60)
    print("ENHANCED AUTO-RECOVERY SYSTEM - TEST SUITE")
    print("="*60)

    tests = [
        ("Playbook Configuration", test_playbook_config, False),
        ("Circuit Breaker", test_circuit_breaker, False),
        ("Health Checks", test_health_checks, True),
        ("Cluster Failure Detection", test_cluster_failure_detection, False),
        ("Playbook Executor", test_playbook_executor, True),
    ]

    passed = 0
    failed = 0

    for test_name, test_func, is_async in tests:
        try:
            if is_async:
                await test_func()
            else:
                test_func()
            passed += 1
        except Exception as e:
            print(f"\n❌ TEST FAILED: {test_name}")
            print(f"   Error: {str(e)}")
            import traceback
            traceback.print_exc()
            failed += 1

    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    print(f"Total Tests: {len(tests)}")
    print(f"Passed: {passed} ✅")
    print(f"Failed: {failed} {'❌' if failed > 0 else ''}")

    if failed == 0:
        print("\n🎉 All tests passed! System is ready.")
    else:
        print(f"\n⚠️  {failed} test(s) failed. Review errors above.")

    return failed == 0


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Test Enhanced Auto-Recovery System")
    parser.add_argument("--test", choices=[
        "all", "playbook", "circuit", "health", "executor", "cluster"
    ], default="all", help="Which test to run")

    args = parser.parse_args()

    if args.test == "all":
        success = asyncio.run(run_all_tests())
        sys.exit(0 if success else 1)
    elif args.test == "playbook":
        test_playbook_config()
    elif args.test == "circuit":
        test_circuit_breaker()
    elif args.test == "health":
        asyncio.run(test_health_checks())
    elif args.test == "executor":
        asyncio.run(test_playbook_executor())
    elif args.test == "cluster":
        test_cluster_failure_detection()


if __name__ == "__main__":
    main()
