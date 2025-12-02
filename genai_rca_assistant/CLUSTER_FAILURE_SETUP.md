# Cluster Failure Detection - Setup Guide

## 🎯 Goal

Enable your RCA system to detect and auto-recover from **cluster failures**, not just job failures.

---

## 🔍 What's the Difference?

| Failure Type | What Happens | Current Detection | Auto-Recovery |
|--------------|--------------|-------------------|---------------|
| **Job Failure** | Databricks job fails due to code error | ✅ Webhook already configured | ✅ Retry job |
| **Cluster Failure** | Underlying cluster crashes/terminates | ⚠️ Needs setup | ✅ Restart cluster, scale up |

**Example Scenarios:**
- ❌ Driver becomes unreachable → **Cluster Failure**
- ❌ Cloud provider shuts down instances → **Cluster Failure**
- ❌ Out of memory causes cluster termination → **Cluster Failure**
- ✅ Python code throws exception → **Job Failure** (already handled)

---

## 🚀 Setup Methods

We'll use **IDEA 4 (Quick Win)** + **IDEA 1 (Proper Setup)** from our analysis.

---

## Method 1: Quick Win (TODAY) - Job-Based Detection ⚡

**No configuration needed!** This is already implemented.

### How it works:

When a job failure webhook arrives:
1. System fetches job details from Databricks API
2. Extracts `cluster_id` from run data
3. Calls `enrich_run_data_with_cluster_info()` function
4. Checks if cluster has termination reason
5. If cluster failed → classifies as cluster error (not job error)
6. Applies cluster-specific recovery (restart, not retry job)

### What you get:

✅ Detects cluster failures that cause job failures
✅ Zero configuration
✅ Works immediately with existing webhooks

### Limitations:

❌ Only detects cluster failures that cause job failures
❌ Misses standalone cluster failures (e.g., driver crash without job running)

---

## Method 2: Proper Setup (THIS WEEK) - Databricks Event Delivery 🎯

**Requires: Databricks workspace admin access**

### Step 1: Create Webhook in Databricks

#### Option A: Using Databricks UI

1. Go to your Databricks workspace
2. Navigate to **Admin Console** → **Webhook Subscriptions**
3. Click **Create Webhook**
4. Configure:
   - **URL:** `https://your-domain.com/databricks-monitor`
   - **Events to subscribe:**
     - `cluster.terminated`
     - `cluster.failed_to_start`
     - `cluster.restarting`
   - **Headers:**
     ```
     x-api-key: balaji-rca-secret-2025
     Content-Type: application/json
     ```
5. **Save**

#### Option B: Using Databricks CLI

```bash
# Install Databricks CLI
pip install databricks-cli

# Configure authentication
databricks configure --token

# Create webhook subscription
databricks workspace import-dir ./webhook-config /Shared/webhooks

# webhook-config.json:
{
  "url": "https://your-domain.com/databricks-monitor",
  "events": [
    "cluster.terminated",
    "cluster.failed_to_start"
  ],
  "headers": {
    "x-api-key": "balaji-rca-secret-2025"
  }
}
```

#### Option C: Using Databricks REST API

```bash
curl -X POST \
  https://YOUR_DATABRICKS_HOST/api/2.0/webhooks \
  -H "Authorization: Bearer $DATABRICKS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "events": ["cluster.terminated", "cluster.failed_to_start"],
    "url": "https://your-domain.com/databricks-monitor",
    "config": {
      "headers": {
        "x-api-key": "balaji-rca-secret-2025"
      }
    }
  }'
```

### Step 2: Test the Webhook

Create a test cluster and manually terminate it:

```bash
# Create a test cluster
databricks clusters create --json-file test-cluster.json

# Get cluster ID from response
CLUSTER_ID="your-cluster-id"

# Manually terminate it (will trigger webhook)
databricks clusters delete --cluster-id $CLUSTER_ID
```

### Step 3: Verify in Your RCA System

Check your logs:
```bash
tail -f logs/rca-system.log | grep "Databricks Cluster"
```

You should see:
```
✓ Databricks Cluster Extractor: cluster=test-cluster, id=abc123, event=cluster.terminated
🔴 Detected underlying cluster failure: DatabricksClusterTerminated
📋 Found playbook: Restart unexpectedly terminated cluster
🚀 Executing enhanced playbook for DatabricksClusterTerminated
✅ Cluster test-cluster is healthy!
```

---

## Method 3: Background Monitoring (OPTIONAL) - Polling 🔄

For extra safety, add a background task that polls for cluster issues.

### Add to `main.py`:

```python
import asyncio
from databricks_api_utils import get_cluster_details, classify_cluster_error

async def poll_all_clusters():
    """Background task to check cluster health every 5 minutes"""
    from databricks_remediation import get_all_clusters  # You'll need to implement this

    while True:
        try:
            clusters = await asyncio.to_thread(get_all_clusters)

            for cluster in clusters:
                cluster_id = cluster.get("cluster_id")
                state = cluster.get("state")

                if state in ["TERMINATED", "ERROR"]:
                    termination_reason = cluster.get("termination_reason", {})

                    # Check if it's a failure (not user-initiated)
                    if termination_reason.get("type") != "SUCCESS":
                        logger.warning(f"⚠️ Found failed cluster: {cluster_id}")

                        # Create RCA ticket
                        error_type = classify_cluster_error(cluster_id, termination_reason)
                        # ... trigger auto-recovery ...

        except Exception as e:
            logger.error(f"Cluster polling error: {e}")

        await asyncio.sleep(300)  # Wait 5 minutes


@app.on_event("startup")
async def start_background_tasks():
    """Start background monitoring tasks"""
    asyncio.create_task(poll_all_clusters())
```

---

## 🧪 Testing Cluster Failure Detection

### Test 1: Simulate Driver Crash

```python
# test_cluster_failure.py
import requests

payload = {
    "event": "cluster.terminated",
    "cluster": {
        "cluster_id": "test-cluster-123",
        "cluster_name": "Test Cluster",
        "state": "TERMINATED",
        "termination_reason": {
            "code": "DRIVER_UNREACHABLE",
            "type": "CLIENT_ERROR",
            "parameters": {
                "driver_id": "driver-abc"
            }
        }
    }
}

response = requests.post(
    "http://localhost:8000/databricks-monitor",
    json=payload,
    headers={"x-api-key": "balaji-rca-secret-2025"}
)

print(response.json())
```

Expected output:
```json
{
  "status": "success",
  "ticket_id": "RCA-20250102-001",
  "error_type": "DatabricksDriverNotResponding",
  "recovery_status": "in_progress",
  "actions_taken": ["restart_cluster"],
  "message": "Cluster restart initiated"
}
```

### Test 2: Simulate Resource Exhaustion

```python
payload = {
    "event": "cluster.terminated",
    "cluster": {
        "cluster_id": "test-cluster-456",
        "cluster_name": "Analytics Cluster",
        "state": "TERMINATED",
        "termination_reason": {
            "code": "INSUFFICIENT_INSTANCE_CAPACITY",
            "type": "CLOUD_FAILURE",
            "parameters": {
                "region": "eastus2"
            }
        }
    }
}
```

Expected recovery:
- Error type: `DatabricksResourceExhausted`
- Action: `scale_cluster` or `restart_with_different_instance_type`

---

## 📊 Monitoring Cluster Failures

### Dashboard Queries

Add these to your monitoring dashboard:

```sql
-- Cluster failures in last 24 hours
SELECT
    COUNT(*) as cluster_failures,
    error_type,
    AVG(ack_seconds) as avg_resolution_time
FROM tickets
WHERE error_type LIKE 'DatabricksCluster%'
  AND timestamp > datetime('now', '-1 day')
GROUP BY error_type;
```

### Alerts

Set up alerts for:
1. **High cluster failure rate** (>5 failures/hour)
2. **Circuit breaker opened** for cluster errors
3. **Auto-recovery failures** (manual intervention needed)

---

## 🔧 Cluster Error Type Mapping

Our system automatically maps Databricks termination codes to error types:

| Termination Code | Error Type | Recovery Action |
|-----------------|------------|-----------------|
| `DRIVER_UNREACHABLE` | `DatabricksDriverNotResponding` | Restart cluster |
| `CLOUD_PROVIDER_SHUTDOWN` | `DatabricksClusterTerminated` | Restart cluster |
| `CLOUD_PROVIDER_LAUNCH_FAILURE` | `DatabricksClusterStartFailure` | Restart with retry |
| `INSUFFICIENT_INSTANCE_CAPACITY` | `DatabricksResourceExhausted` | Scale cluster or change instance type |
| `SPARK_STARTUP_FAILURE` | `DatabricksClusterStartFailure` | Restart cluster |
| `INVALID_ARGUMENT` | `DatabricksConfigurationError` | Rollback config |
| `BOOTSTRAP_TIMEOUT` | `DatabricksClusterStartFailure` | Restart with longer timeout |

See `databricks_api_utils.py:421-438` for the complete mapping.

---

## ⚠️ Common Issues

### Issue 1: Webhook not receiving cluster events

**Check:**
1. Webhook is created for correct workspace
2. URL is publicly accessible (not localhost)
3. API key matches `RCA_API_KEY` in your `.env`
4. Firewall allows Databricks IPs

**Debug:**
```bash
# Test webhook endpoint
curl -X POST http://your-domain.com/databricks-monitor \
  -H "x-api-key: balaji-rca-secret-2025" \
  -H "Content-Type: application/json" \
  -d '{"event": "test"}'
```

### Issue 2: Cluster detected but recovery not triggered

**Check:**
1. `AUTO_REMEDIATION_ENABLED=true` in `.env`
2. Error type has playbook configured in `playbook_config.py`
3. Circuit breaker is not open for this error type
4. Databricks credentials are set (`DATABRICKS_HOST`, `DATABRICKS_TOKEN`)

**Debug:**
```python
# Check playbook configuration
from playbook_config import get_playbook

playbook = get_playbook("DatabricksClusterTerminated")
print(playbook.action if playbook else "No playbook configured")
```

### Issue 3: Health check fails after cluster restart

**Possible causes:**
1. Cluster is still starting (increase `health_check_timeout`)
2. Cluster started but libraries not installed yet
3. Cluster configuration issue

**Fix:**
```python
# In playbook_config.py, increase timeout:
"DatabricksClusterTerminated": PlaybookConfig(
    action="restart_cluster",
    timeout_seconds=900,  # Increase from 600 to 900
    health_check_timeout=120  # Increase from 60 to 120
)
```

---

## ✅ Verification Checklist

Use this checklist to verify your setup:

- [ ] Databricks webhook created (Method 2)
- [ ] Test cluster termination triggers webhook
- [ ] RCA system receives and parses cluster event
- [ ] System detects cluster failure (not job failure)
- [ ] Correct error type assigned (e.g., `DatabricksDriverNotResponding`)
- [ ] Playbook found for error type
- [ ] Circuit breaker allows recovery
- [ ] Recovery action executed (restart/scale)
- [ ] Health check passes
- [ ] Ticket status updated to "closed" or "in_progress"
- [ ] Slack notification sent (if configured)
- [ ] Audit trail logged

---

## 📚 Related Documentation

- **`ENHANCED_RECOVERY_INTEGRATION.md`** - Main integration guide
- **`playbook_config.py`** - Configure recovery actions for cluster errors
- **`databricks_api_utils.py:356-528`** - Cluster failure detection code
- **`health_checks.py`** - Health verification implementation

---

## 🎉 Success!

Once set up, your system will:

✅ **Detect cluster failures automatically**
✅ **Distinguish cluster vs job failures**
✅ **Apply appropriate recovery** (restart vs retry)
✅ **Verify recovery with health checks**
✅ **Prevent cascading failures** with circuit breakers

**No more manual cluster restarts!** 🚀
