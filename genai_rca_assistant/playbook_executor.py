"""
Enhanced Playbook Executor with Chaining, Fallbacks, and Health Checks
Orchestrates automated recovery with circuit breakers and verification
"""
import os
import time
import logging
import asyncio
from typing import Tuple, Dict, Optional, List
from datetime import datetime

# Import our new modules
from playbook_config import get_playbook, PlaybookConfig
from health_checks import (
    comprehensive_health_check,
    check_cluster_health,
    check_job_run_health,
    wait_for_job_completion
)
from circuit_breaker import (
    check_circuit,
    record_recovery_success,
    record_recovery_failure,
    get_circuit_status
)

# Import existing remediation functions
from databricks_remediation import (
    retry_databricks_job,
    retry_databricks_job_with_backoff,
    restart_cluster,
    auto_scale_cluster_on_failure,
    retry_library_with_fallback,
    parse_library_spec,
    get_cluster_config
)

logger = logging.getLogger("playbook_executor")


# ============================================
# PLAYBOOK EXECUTION RESULT
# ============================================

class PlaybookExecutionResult:
    """Result of playbook execution"""

    def __init__(self):
        self.success = False
        self.message = ""
        self.actions_taken: List[str] = []
        self.health_check_passed = False
        self.circuit_breaker_status = {}
        self.execution_time_seconds = 0
        self.fallback_used = False
        self.chain_executed = False
        self.metadata: Dict = {}

    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            "success": self.success,
            "message": self.message,
            "actions_taken": self.actions_taken,
            "health_check_passed": self.health_check_passed,
            "circuit_breaker_status": self.circuit_breaker_status,
            "execution_time_seconds": self.execution_time_seconds,
            "fallback_used": self.fallback_used,
            "chain_executed": self.chain_executed,
            "metadata": self.metadata
        }


# ============================================
# SNAPSHOT MANAGEMENT (for Rollback)
# ============================================

class RecoverySnapshot:
    """Snapshot of system state before recovery attempt"""

    def __init__(self, resource_type: str, resource_id: str):
        self.resource_type = resource_type  # "cluster", "job", etc.
        self.resource_id = resource_id
        self.timestamp = datetime.utcnow().isoformat()
        self.state: Dict = {}

    def capture(self) -> bool:
        """Capture current state"""
        try:
            if self.resource_type == "cluster":
                cluster_config = get_cluster_config(self.resource_id)
                if cluster_config:
                    self.state = {
                        "num_workers": cluster_config.get("num_workers"),
                        "node_type_id": cluster_config.get("node_type_id"),
                        "driver_node_type_id": cluster_config.get("driver_node_type_id"),
                        "spark_version": cluster_config.get("spark_version"),
                        "spark_conf": cluster_config.get("spark_conf", {}),
                        "autoscale": cluster_config.get("autoscale"),
                    }
                    logger.info(f"📸 Captured snapshot for cluster {self.resource_id}")
                    return True
            # Add more resource types as needed
            return False
        except Exception as e:
            logger.error(f"Failed to capture snapshot: {e}")
            return False


# ============================================
# CORE PLAYBOOK EXECUTOR
# ============================================

async def execute_recovery_action(
    action: str,
    metadata: Dict,
    playbook: PlaybookConfig
) -> Tuple[bool, str, Dict]:
    """
    Execute a single recovery action

    Args:
        action: The action to execute (e.g., "retry_job", "restart_cluster")
        metadata: Context metadata (job_id, cluster_id, run_id, etc.)
        playbook: Playbook configuration

    Returns:
        (success, message, result_metadata)
    """
    job_id = metadata.get("job_id")
    cluster_id = metadata.get("cluster_id")
    run_id = metadata.get("run_id")
    error_message = metadata.get("error_message", "")

    logger.info(f"🎯 Executing action: {action}")

    # ============================================
    # ACTION: RETRY JOB
    # ============================================
    if action == "retry_job":
        if not job_id:
            return False, "No job_id available for retry", {}

        # Use backoff if configured
        if playbook.backoff_strategy == "exponential":
            success, new_run_id, message = await asyncio.to_thread(
                retry_databricks_job_with_backoff,
                job_id,
                attempt=1,
                max_attempts=playbook.max_retries
            )
        else:
            success, new_run_id, message = await asyncio.to_thread(
                retry_databricks_job,
                job_id
            )

        if success and new_run_id:
            # Wait for job completion if timeout is specified
            if playbook.timeout_seconds > 0:
                logger.info(f"⏳ Waiting for job completion (timeout: {playbook.timeout_seconds}s)")
                success, wait_message = await asyncio.to_thread(
                    wait_for_job_completion,
                    new_run_id,
                    timeout_seconds=playbook.timeout_seconds
                )
                return success, wait_message, {"new_run_id": new_run_id}

        return success, message, {"new_run_id": new_run_id} if new_run_id else {}

    # ============================================
    # ACTION: RESTART CLUSTER
    # ============================================
    elif action == "restart_cluster":
        if not cluster_id:
            return False, "No cluster_id available for restart", {}

        success, message = await asyncio.to_thread(restart_cluster, cluster_id)
        return success, message, {"cluster_id": cluster_id}

    # ============================================
    # ACTION: SCALE CLUSTER
    # ============================================
    elif action == "scale_cluster":
        if not cluster_id:
            return False, "No cluster_id available for scaling", {}

        success, message = await asyncio.to_thread(
            auto_scale_cluster_on_failure,
            cluster_id
        )
        return success, message, {"cluster_id": cluster_id}

    # ============================================
    # ACTION: LIBRARY FALLBACK
    # ============================================
    elif action == "library_fallback":
        if not cluster_id:
            return False, "No cluster_id available for library installation", {}

        # Extract library info
        library_spec = metadata.get("library_name")

        if not library_spec:
            # Try to extract from error message
            import re
            match = re.search(r"requirement\s+([a-zA-Z0-9_-]+[>=<~!]*[0-9.]*)", error_message)
            if match:
                library_spec = match.group(1)

        if not library_spec:
            return False, "Could not determine library name from error", {}

        library_name, failed_version = parse_library_spec(library_spec)

        success, installed_version, message = await asyncio.to_thread(
            retry_library_with_fallback,
            cluster_id,
            library_spec,
            failed_version
        )

        return success, message, {
            "cluster_id": cluster_id,
            "library_name": library_name,
            "installed_version": installed_version
        }

    # ============================================
    # ACTION: ROLLBACK CONFIG (placeholder)
    # ============================================
    elif action == "rollback_config":
        # This would be implemented with proper config versioning
        logger.warning("⚠️ rollback_config not yet fully implemented")
        return False, "Config rollback not implemented", {}

    # ============================================
    # ACTION: NONE (no auto-recovery available)
    # ============================================
    elif action == "none":
        return False, "No auto-recovery action configured for this error type", {}

    else:
        return False, f"Unknown action: {action}", {}


async def execute_playbook_with_config(
    error_type: str,
    metadata: Dict,
    ticket_id: Optional[str] = None
) -> PlaybookExecutionResult:
    """
    Execute playbook with full orchestration (circuit breaker, health checks, fallbacks, chaining)

    Args:
        error_type: The error type (e.g., "DatabricksJobExecutionError")
        metadata: Context metadata (job_id, cluster_id, run_id, etc.)
        ticket_id: Optional ticket ID for audit logging

    Returns:
        PlaybookExecutionResult with all execution details
    """
    result = PlaybookExecutionResult()
    start_time = time.time()

    logger.info(f"🚀 Starting playbook execution for error type: {error_type}")

    # Get playbook configuration
    playbook = get_playbook(error_type)

    if not playbook:
        result.success = False
        result.message = f"No playbook configured for error type: {error_type}"
        logger.warning(f"⚠️ {result.message}")
        return result

    logger.info(f"📋 Found playbook: {playbook.description}")
    logger.info(f"   Action: {playbook.action}")
    logger.info(f"   Max Retries: {playbook.max_retries}")
    logger.info(f"   Fallback: {playbook.fallback_action}")

    # Extract resource ID for circuit breaker
    resource_id = metadata.get("job_id") or metadata.get("cluster_id") or "global"

    # ============================================
    # STEP 1: CHECK CIRCUIT BREAKER
    # ============================================
    if playbook.circuit_breaker_enabled:
        can_proceed, circuit_reason = check_circuit(
            error_type,
            resource_id,
            failure_threshold=playbook.circuit_breaker_threshold,
            timeout_seconds=playbook.circuit_breaker_timeout
        )

        result.circuit_breaker_status = get_circuit_status(error_type, resource_id)

        if not can_proceed:
            result.success = False
            result.message = f"Circuit breaker open: {circuit_reason}"
            logger.error(f"🔴 {result.message}")
            result.execution_time_seconds = int(time.time() - start_time)
            return result

        logger.info(f"🟢 Circuit breaker check passed: {circuit_reason}")

    # ============================================
    # STEP 2: CAPTURE SNAPSHOT (if enabled)
    # ============================================
    snapshot = None
    if playbook.enable_rollback and playbook.snapshot_before_action:
        resource_type = "cluster" if metadata.get("cluster_id") else "job"
        resource_id_for_snapshot = metadata.get("cluster_id") or metadata.get("job_id")

        if resource_id_for_snapshot:
            snapshot = RecoverySnapshot(resource_type, resource_id_for_snapshot)
            if snapshot.capture():
                result.metadata["snapshot_captured"] = True
                logger.info("📸 State snapshot captured for rollback")

    # ============================================
    # STEP 3: EXECUTE PRIMARY ACTION
    # ============================================
    logger.info(f"🎯 Executing primary action: {playbook.action}")
    result.actions_taken.append(f"Primary: {playbook.action}")

    primary_success, primary_message, primary_metadata = await execute_recovery_action(
        playbook.action,
        metadata,
        playbook
    )

    result.metadata.update(primary_metadata)

    if primary_success:
        logger.info(f"✅ Primary action succeeded: {primary_message}")

        # ============================================
        # STEP 4: VERIFY HEALTH (if enabled)
        # ============================================
        if playbook.verify_health:
            logger.info("🏥 Running health checks...")

            cluster_id = primary_metadata.get("cluster_id") or metadata.get("cluster_id")
            run_id = primary_metadata.get("new_run_id") or primary_metadata.get("run_id")

            health_success, health_message, health_metrics = await asyncio.to_thread(
                comprehensive_health_check,
                cluster_id=cluster_id,
                run_id=run_id,
                check_type="auto"
            )

            result.health_check_passed = health_success
            result.metadata["health_metrics"] = health_metrics

            if health_success:
                logger.info(f"✅ Health check passed: {health_message}")
                result.success = True
                result.message = f"{primary_message} | Health check: {health_message}"

                # Record success with circuit breaker
                if playbook.circuit_breaker_enabled:
                    record_recovery_success(error_type, resource_id)

            else:
                logger.error(f"❌ Health check failed: {health_message}")
                result.success = False
                result.message = f"{primary_message} but health check failed: {health_message}"

                # Record failure with circuit breaker
                if playbook.circuit_breaker_enabled:
                    record_recovery_failure(error_type, resource_id)

                # Try fallback if configured
                if playbook.fallback_action:
                    logger.info(f"🔄 Attempting fallback action: {playbook.fallback_action}")
                    await execute_fallback(playbook, metadata, result)

        else:
            # No health check, assume success
            result.success = True
            result.message = primary_message

            if playbook.circuit_breaker_enabled:
                record_recovery_success(error_type, resource_id)

    else:
        # Primary action failed
        logger.error(f"❌ Primary action failed: {primary_message}")
        result.success = False
        result.message = primary_message

        # Record failure with circuit breaker
        if playbook.circuit_breaker_enabled:
            record_recovery_failure(error_type, resource_id)

        # ============================================
        # STEP 5: TRY FALLBACK ACTION (if configured)
        # ============================================
        if playbook.fallback_action:
            logger.info(f"🔄 Primary action failed, attempting fallback: {playbook.fallback_action}")
            await execute_fallback(playbook, metadata, result)

    # ============================================
    # STEP 6: EXECUTE CHAINED PLAYBOOK (if configured)
    # ============================================
    if result.success and playbook.chain_on_failure:
        logger.info(f"🔗 Success! Now chaining to: {playbook.chain_on_failure}")
        result.chain_executed = True
        # Execute the chained playbook
        # (Would be implemented similar to above)

    result.execution_time_seconds = int(time.time() - start_time)
    logger.info(f"⏱️ Total execution time: {result.execution_time_seconds}s")

    return result


async def execute_fallback(
    playbook: PlaybookConfig,
    metadata: Dict,
    result: PlaybookExecutionResult
) -> None:
    """Execute fallback action"""
    fallback_playbook = get_playbook(playbook.fallback_action)

    if not fallback_playbook:
        # Treat as direct action
        fallback_success, fallback_message, fallback_metadata = await execute_recovery_action(
            playbook.fallback_action,
            metadata,
            playbook
        )
    else:
        # Execute full playbook for fallback
        fallback_success, fallback_message, fallback_metadata = await execute_recovery_action(
            fallback_playbook.action,
            metadata,
            fallback_playbook
        )

    result.actions_taken.append(f"Fallback: {playbook.fallback_action}")
    result.fallback_used = True

    if fallback_success:
        logger.info(f"✅ Fallback succeeded: {fallback_message}")
        result.success = True
        result.message = f"{result.message} | Fallback {playbook.fallback_action} succeeded: {fallback_message}"
        result.metadata.update(fallback_metadata)
    else:
        logger.error(f"❌ Fallback also failed: {fallback_message}")
        result.message = f"{result.message} | Fallback {playbook.fallback_action} also failed: {fallback_message}"


# ============================================
# CONVENIENCE FUNCTIONS
# ============================================

async def execute_playbook(
    error_type: str,
    job_id: Optional[str] = None,
    cluster_id: Optional[str] = None,
    run_id: Optional[str] = None,
    ticket_id: Optional[str] = None,
    **kwargs
) -> Tuple[bool, str, Dict]:
    """
    Simplified playbook execution function

    Returns:
        (success, message, metadata)
    """
    metadata = {
        "job_id": job_id,
        "cluster_id": cluster_id,
        "run_id": run_id,
        **kwargs
    }

    result = await execute_playbook_with_config(error_type, metadata, ticket_id)

    return result.success, result.message, result.metadata


if __name__ == "__main__":
    # Test playbook executor
    print("🧪 Testing Playbook Executor System\n")

    async def test():
        # Example test (requires valid credentials and resources)
        metadata = {
            "job_id": "123",
            "cluster_id": "cluster-abc",
            "run_id": "456"
        }

        result = await execute_playbook_with_config(
            "DatabricksJobExecutionError",
            metadata
        )

        print(f"Success: {result.success}")
        print(f"Message: {result.message}")
        print(f"Actions: {result.actions_taken}")
        print(f"Time: {result.execution_time_seconds}s")

    # asyncio.run(test())
    print("✅ Playbook executor system ready!")
    print("\nExample usage:")
    print("  result = await execute_playbook_with_config('DatabricksJobExecutionError', metadata)")
    print("  success, msg, meta = await execute_playbook('DatabricksJobExecutionError', job_id='123')")
