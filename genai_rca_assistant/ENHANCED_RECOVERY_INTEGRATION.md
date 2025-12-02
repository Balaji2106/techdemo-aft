# Enhanced Auto-Recovery System - Integration Guide

## 🎉 What's New?

We've implemented **Option 2: Enhanced Playbook Registry with Direct API calls** - NO Logic Apps needed!

### New Components:

1. **`playbook_config.py`** - Centralized playbook registry with metadata
2. **`health_checks.py`** - Post-recovery verification system
3. **`circuit_breaker.py`** - Prevents infinite retry loops
4. **`playbook_executor.py`** - Orchestrates recovery with fallbacks and chaining
5. **Enhanced `databricks_api_utils.py`** - Cluster failure detection

---

## 📋 Features Implemented

✅ **Extended Playbook Registry** with metadata (retry logic, timeouts, fallbacks)
✅ **Direct API Calls** - No Logic Apps required for Databricks
✅ **Circuit Breakers** - Prevents infinite retry loops
✅ **Health Checks** - Verifies recovery success
✅ **Playbook Chaining** - Execute multiple recovery steps
✅ **Fallback Strategies** - Try alternative recovery if primary fails
✅ **Cluster Failure Detection** - Distinguishes cluster vs job failures
✅ **Snapshot & Rollback** - Save state before recovery (foundation)

---

## 🔧 Integration Steps

### Step 1: Update main.py Imports

Add these imports at the top of `main.py`:

```python
# NEW: Enhanced Auto-Recovery Imports
from playbook_executor import execute_playbook_with_config, PlaybookExecutionResult
from playbook_config import get_playbook, list_supported_error_types
from databricks_api_utils import (
    enrich_run_data_with_cluster_info,  # NEW: Detect cluster failures
    is_cluster_failure,
    classify_cluster_error
)
from circuit_breaker import get_circuit_manager
```

### Step 2: Replace Old execute_playbook Function

**OLD CODE (main.py:666-702):**
```python
def execute_playbook(error_type: str, pipeline_name: str, run_id: str, ticket_id: str) -> Optional[str]:
    """Execute the corresponding external playbook (e.g., Logic App) based on error type."""
    logic_app_url = PLAYBOOK_REGISTRY.get(error_type)
    # ... calls Logic App ...
```

**NEW CODE:**
```python
async def execute_playbook_enhanced(
    error_type: str,
    ticket_id: str,
    metadata: Dict
) -> Tuple[bool, str, Dict]:
    """
    Execute enhanced playbook with circuit breakers, health checks, and fallbacks

    Args:
        error_type: Error type (e.g., "DatabricksJobExecutionError")
        ticket_id: RCA ticket ID
        metadata: Dictionary with job_id, cluster_id, run_id, error_message, etc.

    Returns:
        (success, message, result_metadata)
    """
    from playbook_executor import execute_playbook_with_config

    logger.info(f"🚀 Executing enhanced playbook for {error_type}")

    # Execute playbook with full orchestration
    result = await execute_playbook_with_config(
        error_type=error_type,
        metadata=metadata,
        ticket_id=ticket_id
    )

    # Log result to audit trail
    if result.success:
        log_audit(
            ticket_id=ticket_id,
            action="Auto-Recovery Success",
            details=f"{result.message}. Actions: {', '.join(result.actions_taken)}",
            time_taken_seconds=result.execution_time_seconds
        )
    else:
        log_audit(
            ticket_id=ticket_id,
            action="Auto-Recovery Failed",
            details=f"{result.message}. Circuit breaker: {result.circuit_breaker_status.get('state', 'N/A')}",
            time_taken_seconds=result.execution_time_seconds
        )

    return result.success, result.message, result.metadata
```

### Step 3: Update Databricks Webhook Handler

**Enhance the `/databricks-monitor` endpoint (around line 1650-1750):**

```python
@app.post("/databricks-monitor")
async def databricks_monitor(request: Request, x_api_key: str = Header(None)):
    # ... existing authentication code ...

    # Extract event using existing DatabricksExtractor
    job_name, run_id, event_type, error_message, metadata_from_webhook = DatabricksExtractor.extract(payload)

    # **NEW: Enrich with Databricks API for detailed errors**
    if run_id:
        run_details = await asyncio.to_thread(fetch_databricks_run_details, run_id)

        if run_details:
            # **NEW: Detect if this is a cluster failure**
            run_details = enrich_run_data_with_cluster_info(run_details)

            if run_details.get("cluster_failure_detected"):
                # This is a CLUSTER failure, not just a job failure!
                error_type = run_details.get("cluster_error_type", "DatabricksClusterFailure")
                error_message = run_details.get("cluster_error_message", error_message)
                logger.info(f"🔴 Detected underlying cluster failure: {error_type}")
            else:
                # Normal job failure
                error_type = rca.get("error_type", "DatabricksJobExecutionError")

            # Update metadata with cluster info
            metadata_from_webhook["cluster_id"] = run_details.get("cluster_instance", {}).get("cluster_id")
            metadata_from_webhook["cluster_failure"] = run_details.get("cluster_failure_detected", False)

    # ... existing RCA generation code ...

    # **NEW: Use enhanced playbook executor**
    if AUTO_REMEDIATION_ENABLED and rca.get("auto_heal_possible"):
        recovery_metadata = {
            "job_id": metadata_from_webhook.get("job_id"),
            "cluster_id": metadata_from_webhook.get("cluster_id"),
            "run_id": run_id,
            "error_message": error_message,
            "library_name": metadata_from_webhook.get("library_name"),
        }

        success, message, result_metadata = await execute_playbook_enhanced(
            error_type=rca.get("error_type"),
            ticket_id=tid,
            metadata=recovery_metadata
        )

        if success:
            logger.info(f"✅ Auto-recovery succeeded: {message}")
            ticket_data["status"] = "closed"  # Or "in_progress" if you want manual verification

            # Broadcast success
            await manager.broadcast({
                "event": "auto_remediation_success",
                "ticket_id": tid,
                "message": message,
                "actions": result_metadata.get("actions_taken", [])
            })
        else:
            logger.error(f"❌ Auto-recovery failed: {message}")
            ticket_data["status"] = "open"  # Requires manual intervention

    # ... rest of existing code ...
```

### Step 4: Add Circuit Breaker Status Endpoint

Add this new endpoint to view circuit breaker status:

```python
@app.get("/api/circuit-breakers")
async def get_circuit_breakers(current_user: dict = Depends(get_current_user)):
    """Get status of all circuit breakers"""
    from circuit_breaker import get_circuit_manager

    manager = get_circuit_manager()
    all_circuits = manager.get_all_circuits_status()
    open_circuits = manager.get_open_circuits()

    return {
        "total_circuits": len(all_circuits),
        "open_circuits": open_circuits,
        "circuits": all_circuits
    }


@app.post("/api/circuit-breakers/{circuit_name}/reset")
async def reset_circuit_breaker(circuit_name: str, current_user: dict = Depends(get_current_user)):
    """Manually reset a circuit breaker"""
    from circuit_breaker import get_circuit_manager

    manager = get_circuit_manager()
    manager.reset_circuit(circuit_name)

    return {
        "status": "success",
        "message": f"Circuit breaker '{circuit_name}' has been reset"
    }
```

### Step 5: Add Supported Error Types Endpoint

```python
@app.get("/api/supported-error-types")
async def get_supported_error_types():
    """Get list of all error types with configured playbooks"""
    from playbook_config import list_supported_error_types, get_playbook

    error_types = list_supported_error_types()

    playbooks = []
    for error_type in error_types:
        playbook = get_playbook(error_type)
        if playbook:
            playbooks.append({
                "error_type": error_type,
                "action": playbook.action,
                "description": playbook.description,
                "max_retries": playbook.max_retries,
                "fallback": playbook.fallback_action,
                "verify_health": playbook.verify_health
            })

    return {
        "total_playbooks": len(playbooks),
        "playbooks": playbooks
    }
```

---

## 🧪 Testing

### Test Script

Create `test_enhanced_recovery.py`:

```python
import asyncio
from playbook_executor import execute_playbook_with_config

async def test_job_retry():
    """Test job retry playbook"""
    metadata = {
        "job_id": "YOUR_JOB_ID",
        "run_id": "YOUR_FAILED_RUN_ID",
        "error_message": "Job failed with error X"
    }

    result = await execute_playbook_with_config(
        "DatabricksJobExecutionError",
        metadata
    )

    print(f"Success: {result.success}")
    print(f"Message: {result.message}")
    print(f"Actions Taken: {result.actions_taken}")
    print(f"Health Check: {'✅' if result.health_check_passed else '❌'}")
    print(f"Execution Time: {result.execution_time_seconds}s")

if __name__ == "__main__":
    asyncio.run(test_job_retry())
```

---

## 📊 Monitoring

### View Circuit Breaker Status

```bash
curl -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  http://localhost:8000/api/circuit-breakers
```

### View Supported Error Types

```bash
curl http://localhost:8000/api/supported-error-types
```

### Reset a Circuit Breaker

```bash
curl -X POST \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  http://localhost:8000/api/circuit-breakers/DatabricksJobExecutionError:job-123/reset
```

---

## 🔧 Configuration

### Environment Variables (Add to .env)

```bash
# Auto-Recovery Configuration (existing)
AUTO_REMEDIATION_ENABLED=true
AUTO_REMEDIATION_MAX_RETRIES=3
RETRY_BASE_DELAY_SECONDS=30
RETRY_MAX_DELAY_SECONDS=300

# Circuit Breaker Configuration (NEW)
CIRCUIT_BREAKER_FAILURE_THRESHOLD=5
CIRCUIT_BREAKER_TIMEOUT_SECONDS=300

# Health Check Configuration (NEW)
HEALTH_CHECK_ENABLED=true
HEALTH_CHECK_TIMEOUT_SECONDS=60
```

---

## 🎯 Key Improvements Over Old System

| Feature | Old System | New System |
|---------|-----------|------------|
| **Logic Apps Needed** | ❌ Yes | ✅ No (Direct API) |
| **Circuit Breaker** | ❌ No | ✅ Yes |
| **Health Checks** | ❌ No | ✅ Yes |
| **Fallback Strategy** | ❌ No | ✅ Yes |
| **Playbook Chaining** | ❌ No | ✅ Yes |
| **Cluster Failure Detection** | ⚠️ Partial | ✅ Full |
| **Retry Logic** | ✅ Basic | ✅ Advanced (exponential backoff) |
| **Configuration** | ⚠️ Hardcoded | ✅ Centralized (playbook_config.py) |
| **Monitoring** | ⚠️ Limited | ✅ Circuit breaker status, health metrics |

---

## 📝 Next Steps

1. **Integrate code changes** from steps above into `main.py`
2. **Test with real failures** using the test script
3. **Monitor circuit breakers** via the new API endpoints
4. **Add custom playbooks** for your specific error types in `playbook_config.py`
5. **Set up Databricks webhooks** for cluster failure alerts (see CLUSTER_FAILURE_SETUP.md)

---

## 🐛 Troubleshooting

### Issue: Circuit breaker keeps opening

**Solution:** Check the `circuit_breaker_threshold` in `playbook_config.py` and increase it if failures are transient.

### Issue: Health checks always fail

**Solution:** Increase `health_check_timeout` in playbook configuration.

### Issue: Cluster failures not detected

**Solution:** Ensure `DATABRICKS_HOST` and `DATABRICKS_TOKEN` are set correctly for API calls.

---

## 📚 Additional Documentation

- **`CLUSTER_FAILURE_SETUP.md`** - How to set up cluster failure alerts
- **`PLAYBOOK_CUSTOMIZATION.md`** - How to add custom playbooks
- **`CIRCUIT_BREAKER_GUIDE.md`** - Understanding circuit breaker patterns

---

## ✅ Summary

You now have a production-ready auto-recovery system with:

✅ No Logic Apps required (Direct API calls)
✅ Intelligent circuit breakers
✅ Health verification
✅ Fallback strategies
✅ Cluster failure detection
✅ Comprehensive monitoring

**All implemented with Option 2: Enhanced Playbook Registry!** 🎉
