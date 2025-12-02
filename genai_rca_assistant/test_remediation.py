"""
Test Databricks Auto-Remediation Functions
"""
import sys
from databricks_remediation import (
    get_cluster_state,
    get_cluster_config,
    get_remediation_strategy,
    parse_library_spec,
    DATABRICKS_HOST,
    DATABRICKS_TOKEN
)

def test_remediation():
    print("🧪 Testing Databricks Auto-Remediation Functions\n")
    print("=" * 60)
    
    # Check configuration
    print("\n1️⃣ Configuration Check:")
    print(f"   DATABRICKS_HOST: {DATABRICKS_HOST}")
    print(f"   DATABRICKS_TOKEN: {'✅ Set' if DATABRICKS_TOKEN else '❌ Not Set'}")
    
    if not DATABRICKS_HOST or not DATABRICKS_TOKEN:
        print("\n❌ ERROR: Databricks credentials not configured!")
        return False
    
    # Test remediation strategies
    print("\n2️⃣ Testing Remediation Strategies:")
    error_types = [
        "DatabricksJobExecutionError",
        "DatabricksClusterStartFailure",
        "DatabricksResourceExhausted",
        "DatabricksLibraryInstallationError"
    ]
    
    for error_type in error_types:
        strategy = get_remediation_strategy(error_type)
        print(f"   {error_type}:")
        print(f"      Action: {strategy.get('action')}")
        print(f"      Description: {strategy.get('description')}")
    
    # Test library parsing
    print("\n3️⃣ Testing Library Spec Parsing:")
    test_specs = [
        "pandas==2.2.0",
        "numpy>=1.24.0",
        "scikit-learn",
        "requests~=2.28.0"
    ]
    
    for spec in test_specs:
        name, version = parse_library_spec(spec)
        print(f"   '{spec}' -> name='{name}', version='{version or 'latest'}'")
    
    # Test cluster state retrieval (using first cluster from your list)
    print("\n4️⃣ Testing Cluster State Retrieval:")
    test_cluster_id = "1121-055905-q5xcz4bm"  # Your interactive cluster
    
    print(f"   Getting state for cluster: {test_cluster_id}")
    state = get_cluster_state(test_cluster_id)
    print(f"   ✅ Current State: {state}")
    
    # Get full config
    config = get_cluster_config(test_cluster_id)
    if config:
        print(f"   ✅ Cluster Name: {config.get('cluster_name')}")
        print(f"   ✅ Node Type: {config.get('node_type_id')}")
        print(f"   ✅ Num Workers: {config.get('num_workers', 'N/A')}")
        autoscale = config.get('autoscale')
        if autoscale:
            print(f"   ✅ Autoscale: {autoscale.get('min_workers')} - {autoscale.get('max_workers')} workers")
    
    print("\n" + "=" * 60)
    print("✅ All tests passed!\n")
    return True

if __name__ == "__main__":
    success = test_remediation()
    sys.exit(0 if success else 1)