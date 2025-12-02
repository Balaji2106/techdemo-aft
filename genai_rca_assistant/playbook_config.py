"""
Enhanced Playbook Configuration System
Defines recovery strategies with metadata, fallbacks, and chaining
"""
import os
from typing import Dict, List, Optional
from dataclasses import dataclass, field

@dataclass
class PlaybookConfig:
    """Configuration for a recovery playbook"""
    # Primary action configuration
    action: str  # "retry_job", "restart_cluster", "scale_cluster", "library_fallback", "rollback_config"
    max_retries: int = 3
    timeout_seconds: int = 300
    backoff_strategy: str = "exponential"  # "exponential", "linear", "fixed"

    # Fallback configuration
    fallback_action: Optional[str] = None  # Action to try if primary fails
    chain_on_failure: Optional[str] = None  # Next error type to try if this fails

    # Health check configuration
    verify_health: bool = True
    health_check_timeout: int = 60

    # Circuit breaker configuration
    circuit_breaker_enabled: bool = True
    circuit_breaker_threshold: int = 5  # Failures before circuit opens
    circuit_breaker_timeout: int = 300  # Seconds to wait before retry

    # Rollback configuration
    enable_rollback: bool = True
    snapshot_before_action: bool = True

    # Metadata
    description: str = ""
    requires_approval: bool = False  # Future: Manual approval for risky operations
    estimated_time_seconds: int = 60


# ============================================
# DATABRICKS PLAYBOOK REGISTRY
# ============================================

DATABRICKS_PLAYBOOKS: Dict[str, PlaybookConfig] = {

    # Job Execution Errors
    "DatabricksJobExecutionError": PlaybookConfig(
        action="retry_job",
        max_retries=3,
        timeout_seconds=600,
        backoff_strategy="exponential",
        fallback_action="scale_cluster",  # If retry fails, try scaling
        verify_health=True,
        enable_rollback=False,  # Job retry doesn't need rollback
        description="Retry failed job with exponential backoff, scale cluster if retries fail"
    ),

    # Cluster Start Failures
    "DatabricksClusterStartFailure": PlaybookConfig(
        action="restart_cluster",
        max_retries=2,
        timeout_seconds=600,
        backoff_strategy="linear",
        fallback_action="recreate_cluster",  # Future: Recreate with different config
        verify_health=True,
        enable_rollback=True,
        snapshot_before_action=True,
        description="Restart cluster, recreate if restart fails"
    ),

    # Cluster Termination (Unexpected)
    "DatabricksClusterTerminated": PlaybookConfig(
        action="restart_cluster",
        max_retries=1,
        timeout_seconds=600,
        verify_health=True,
        enable_rollback=False,
        description="Restart unexpectedly terminated cluster"
    ),

    # Resource Exhaustion
    "DatabricksResourceExhausted": PlaybookConfig(
        action="scale_cluster",
        max_retries=2,
        timeout_seconds=300,
        fallback_action="restart_with_larger_nodes",  # Future enhancement
        verify_health=True,
        enable_rollback=True,
        snapshot_before_action=True,
        description="Scale up cluster workers to handle resource exhaustion"
    ),

    # Out of Memory
    "DatabricksOutOfMemoryError": PlaybookConfig(
        action="scale_cluster",
        max_retries=1,
        timeout_seconds=300,
        chain_on_failure="DatabricksJobExecutionError",  # After scaling, retry job
        verify_health=True,
        enable_rollback=True,
        description="Scale cluster due to OOM, then retry job"
    ),

    # Driver Not Responding
    "DatabricksDriverNotResponding": PlaybookConfig(
        action="restart_cluster",
        max_retries=2,
        timeout_seconds=600,
        fallback_action="scale_cluster",
        verify_health=True,
        enable_rollback=True,
        description="Restart unresponsive driver, scale if persists"
    ),

    # Library Installation Failures
    "DatabricksLibraryInstallationError": PlaybookConfig(
        action="library_fallback",
        max_retries=3,
        timeout_seconds=300,
        fallback_action="restart_cluster",  # Clean restart if library issues persist
        verify_health=True,
        enable_rollback=True,
        description="Try fallback library versions, restart cluster if all fail"
    ),

    # Configuration Errors
    "DatabricksConfigurationError": PlaybookConfig(
        action="rollback_config",
        max_retries=1,
        timeout_seconds=180,
        verify_health=True,
        enable_rollback=False,  # Rollback itself is the action
        description="Rollback to previous working configuration"
    ),

    # Timeout Errors
    "DatabricksTimeoutError": PlaybookConfig(
        action="retry_job",
        max_retries=2,
        timeout_seconds=900,  # Longer timeout for retry
        fallback_action="scale_cluster",
        verify_health=True,
        description="Retry with extended timeout, scale if persists"
    ),

    # Permission Errors
    "DatabricksPermissionDenied": PlaybookConfig(
        action="none",  # Can't auto-fix permissions
        max_retries=0,
        verify_health=False,
        circuit_breaker_enabled=False,
        description="Permission issues require manual intervention"
    ),

    # Network/Connectivity Errors
    "DatabricksNetworkError": PlaybookConfig(
        action="retry_job",
        max_retries=3,
        timeout_seconds=300,
        backoff_strategy="exponential",
        verify_health=True,
        description="Retry job after transient network issues"
    ),
}


# ============================================
# AZURE DATA FACTORY PLAYBOOK REGISTRY
# ============================================

ADF_PLAYBOOKS: Dict[str, PlaybookConfig] = {

    # Source Blob Not Exists
    "UserErrorSourceBlobNotExists": PlaybookConfig(
        action="rerun_upstream_pipeline",
        max_retries=1,
        timeout_seconds=600,
        verify_health=True,
        description="Rerun upstream pipeline to generate missing source blob"
    ),

    # Gateway Timeout
    "GatewayTimeout": PlaybookConfig(
        action="retry_pipeline",
        max_retries=3,
        timeout_seconds=300,
        backoff_strategy="exponential",
        verify_health=True,
        description="Retry pipeline after gateway timeout"
    ),

    # Connection Failed
    "HttpConnectionFailed": PlaybookConfig(
        action="retry_pipeline",
        max_retries=3,
        timeout_seconds=300,
        backoff_strategy="exponential",
        fallback_action="check_linked_service",
        verify_health=True,
        description="Retry pipeline, check linked service if persists"
    ),

    # Internal Server Error
    "InternalServerError": PlaybookConfig(
        action="retry_pipeline",
        max_retries=2,
        timeout_seconds=600,
        backoff_strategy="linear",
        verify_health=True,
        description="Retry pipeline after internal server error"
    ),

    # Throttling Error
    "ActivityThrottlingError": PlaybookConfig(
        action="retry_pipeline",
        max_retries=3,
        timeout_seconds=900,
        backoff_strategy="exponential",
        verify_health=True,
        description="Retry pipeline with exponential backoff for throttling"
    ),
}


# ============================================
# AIRFLOW PLAYBOOK REGISTRY (Future)
# ============================================

AIRFLOW_PLAYBOOKS: Dict[str, PlaybookConfig] = {
    "AirflowTaskFailure": PlaybookConfig(
        action="retry_task",
        max_retries=3,
        timeout_seconds=300,
        verify_health=True,
        description="Retry failed Airflow task"
    ),
}


# ============================================
# SPARK PLAYBOOK REGISTRY (Future)
# ============================================

SPARK_PLAYBOOKS: Dict[str, PlaybookConfig] = {
    "SparkExecutorLost": PlaybookConfig(
        action="add_executors",
        max_retries=2,
        timeout_seconds=300,
        verify_health=True,
        description="Add more Spark executors"
    ),
}


# ============================================
# UNIFIED PLAYBOOK REGISTRY
# ============================================

ALL_PLAYBOOKS: Dict[str, PlaybookConfig] = {
    **DATABRICKS_PLAYBOOKS,
    **ADF_PLAYBOOKS,
    **AIRFLOW_PLAYBOOKS,
    **SPARK_PLAYBOOKS,
}


def get_playbook(error_type: str) -> Optional[PlaybookConfig]:
    """Get playbook configuration for an error type"""
    return ALL_PLAYBOOKS.get(error_type)


def list_supported_error_types() -> List[str]:
    """List all error types with configured playbooks"""
    return list(ALL_PLAYBOOKS.keys())


def get_playbooks_by_platform(platform: str) -> Dict[str, PlaybookConfig]:
    """Get all playbooks for a specific platform"""
    platform_map = {
        "databricks": DATABRICKS_PLAYBOOKS,
        "adf": ADF_PLAYBOOKS,
        "azure_data_factory": ADF_PLAYBOOKS,
        "airflow": AIRFLOW_PLAYBOOKS,
        "spark": SPARK_PLAYBOOKS,
    }
    return platform_map.get(platform.lower(), {})


if __name__ == "__main__":
    # Test playbook retrieval
    print("🧪 Testing Playbook Configuration System\n")

    # Test 1: Get specific playbook
    playbook = get_playbook("DatabricksJobExecutionError")
    if playbook:
        print(f"✅ Found playbook: {playbook.description}")
        print(f"   Action: {playbook.action}")
        print(f"   Max Retries: {playbook.max_retries}")
        print(f"   Fallback: {playbook.fallback_action}")
        print()

    # Test 2: List all Databricks playbooks
    print("📋 Databricks Playbooks:")
    for error_type in DATABRICKS_PLAYBOOKS.keys():
        print(f"   - {error_type}")
    print()

    # Test 3: Test chaining
    oom_playbook = get_playbook("DatabricksOutOfMemoryError")
    if oom_playbook and oom_playbook.chain_on_failure:
        print(f"🔗 OOM Error chains to: {oom_playbook.chain_on_failure}")
        chained = get_playbook(oom_playbook.chain_on_failure)
        if chained:
            print(f"   Next action: {chained.action}")

    print("\n✅ Playbook configuration system ready!")
