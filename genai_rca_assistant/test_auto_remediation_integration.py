"""
Test Auto-Remediation Integration
"""
import asyncio
from databricks_remediation import (
    get_remediation_strategy,
    AUTO_REMEDIATION_ENABLED
)

def test_integration():
    print("🧪 Testing Auto-Remediation Integration\n")
    print("=" * 60)
    
    # Test 1: Check if auto-remediation is enabled
    print("\n1️⃣ Auto-Remediation Status:")
    print(f"   Enabled: {'✅ YES' if AUTO_REMEDIATION_ENABLED else '❌ NO'}")
    
    if not AUTO_REMEDIATION_ENABLED:
        print("\n⚠️ WARNING: Auto-remediation is disabled!")
        print("   Set AUTO_REMEDIATION_ENABLED=true in .env to enable")
    
    # Test 2: Test remediation strategies
    print("\n2️⃣ Testing Error Type Mappings:")
    
    test_errors = [
        {
            "error_type": "DatabricksJobExecutionError",
            "expected_action": "retry"
        },
        {
            "error_type": "DatabricksClusterStartFailure",
            "expected_action": "restart"
        },
        {
            "error_type": "DatabricksResourceExhausted",
            "expected_action": "scale_up"
        },
        {
            "error_type": "DatabricksLibraryInstallationError",
            "expected_action": "library_fallback"
        },
    ]
    
    for test in test_errors:
        error_type = test["error_type"]
        expected = test["expected_action"]
        
        strategy = get_remediation_strategy(error_type)
        actual = strategy.get("action")
        
        if actual == expected:
            print(f"   ✅ {error_type}: {actual}")
        else:
            print(f"   ❌ {error_type}: expected '{expected}', got '{actual}'")
    
    # Test 3: Simulate metadata structure
    print("\n3️⃣ Testing Metadata Structure:")
    
    sample_metadata = {
        "job_id": "12345",
        "run_id": "67890",
        "cluster_id": "1121-055905-q5xcz4bm",
        "job_name": "Test ETL Job",
        "error_message": "Job execution failed",
        "error_type": "DatabricksJobExecutionError",
        "is_cluster_failure": False
    }
    
    print("   Sample metadata for remediation:")
    for key, value in sample_metadata.items():
        print(f"      {key}: {value}")
    
    print("\n" + "=" * 60)
    print("✅ Integration test completed!\n")
    
    if AUTO_REMEDIATION_ENABLED:
        print("🚀 Auto-remediation is READY!")
        print("   Next: Test with a real Databricks failure")
    else:
        print("⚠️  Auto-remediation is DISABLED")
        print("   Enable in .env to start auto-healing")

if __name__ == "__main__":
    test_integration()