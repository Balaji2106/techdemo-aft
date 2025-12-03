# Databricks Failure Test Cases

These test codes will trigger different auto-remediation scenarios in your RCA system.

---

## ✅ **RECOMMENDED: Test 1 - Simple Job Failure**
**Will trigger:** `DatabricksJobExecutionError` → **Auto-retry with exponential backoff**

### Databricks Notebook Code (Python):
```python
# TEST CASE 1: Job Execution Error (Will Auto-Retry)
print("🧪 Starting test job that will fail...")
print("This will trigger DatabricksJobExecutionError")

# This will cause a runtime error
result = 10 / 0  # Division by zero

print("This line will never execute")
```

**What happens:**
1. ❌ Job fails immediately with `ZeroDivisionError`
2. 🔔 Webhook sent to your RCA system
3. 🤖 AI analyzes the error
4. ✅ System auto-retries the job (up to 3 times with backoff)
5. 📊 If retries fail, escalates to cluster scaling

**Expected Auto-Remediation:**
- Action: `retry_job`
- Max Retries: 3
- Backoff: Exponential (30s, 60s, 120s)
- Fallback: Scale cluster if all retries fail

---

## Test 2 - Out of Memory Error
**Will trigger:** `DatabricksOutOfMemoryError` → **Scale cluster + Retry job**

### Databricks Notebook Code (Python):
```python
# TEST CASE 2: Out of Memory Error (Will Scale Cluster)
import numpy as np

print("🧪 Starting memory exhaustion test...")
print("This will trigger DatabricksOutOfMemoryError")

# Allocate massive array to exhaust memory
# Adjust size based on your cluster size (this tries to allocate 50GB)
huge_array = np.ones((10000, 10000, 500), dtype=np.float64)

print("This line will never execute")
```

**What happens:**
1. ❌ Job crashes with OOM error
2. 🔔 Webhook sent to RCA system
3. 🤖 AI detects memory exhaustion
4. ✅ System scales up cluster workers (+50%)
5. ✅ After scaling, retries the job

**Expected Auto-Remediation:**
- Action: `scale_cluster`
- Scale: +50% workers (up to max 10)
- Chain: Retry job after scaling
- Verify: Health check after scale

---

## Test 3 - Library Installation Error
**Will trigger:** `DatabricksLibraryInstallationError` → **Try fallback versions**

### Setup Required:
1. Go to your Databricks cluster settings
2. Add a library with an invalid version:
   - Library: `pandas==99.99.99` (non-existent version)
3. Start the cluster (it will fail to install)

### Or use this notebook code to simulate:
```python
# TEST CASE 3: Library Import Error (Will Try Fallback)
import sys
import subprocess

print("🧪 Starting library installation test...")
print("This will trigger DatabricksLibraryInstallationError")

# Try to install a package that will fail
result = subprocess.run(
    [sys.executable, "-m", "pip", "install", "pandas==99.99.99"],
    capture_output=True,
    text=True
)

if result.returncode != 0:
    raise RuntimeError(f"Library installation failed: {result.stderr}")

print("This line will never execute")
```

**What happens:**
1. ❌ Library installation fails
2. 🔔 Webhook sent to RCA system
3. 🤖 AI detects library error
4. ✅ System tries fallback versions (2.1.0, 2.0.3, 1.5.3)
5. ✅ If all fail, restarts cluster

**Expected Auto-Remediation:**
- Action: `library_fallback`
- Fallbacks: Try 3 older versions
- Max Retries: 3
- Fallback: Restart cluster if all fail

---

## 🎯 **BEST TEST: Test 1 (Simple Failure)**

**Why?**
- ✅ Fastest to test (fails immediately)
- ✅ Easiest to trigger repeatedly
- ✅ Clear error message
- ✅ Tests the core retry logic
- ✅ Safe (no resource exhaustion)

---

## 📋 Pre-Test Checklist

Before running the test, ensure:

1. **Enable Auto-Remediation** in `.env`:
   ```bash
   AUTO_REMEDIATION_ENABLED=true
   ENABLE_JOB_RETRY=true
   CIRCUIT_BREAKER_ENABLED=true
   HEALTH_CHECK_ENABLED=true
   ```

2. **Configure Databricks Webhook** in your job:
   - Go to Job Settings → Notifications
   - Add webhook URL: `https://your-rca-system.com/databricks-monitor`
   - Set header: `x-api-key: balaji-rca-secret-2025`

3. **Start Your RCA System**:
   ```bash
   cd genai_rca_assistant
   uvicorn main:app --host 0.0.0.0 --port 8000
   ```

4. **Configure AI Provider** (Gemini or Ollama):
   ```bash
   GEMINI_API_KEY=your-key-here
   # OR
   OLLAMA_HOST=http://localhost:11434
   ```

---

## 🔍 How to Verify Auto-Remediation

### 1. Check RCA System Logs:
```bash
# Watch for these log messages:
# ✅ "Attempting to retry Databricks job..."
# ✅ "Successfully triggered job retry. New run_id: ..."
# ✅ "Health check passed for resource..."
```

### 2. Check Databricks Job Runs:
- Go to Databricks → Workflows → Your Job → Runs
- You should see multiple runs:
  - Run 1: FAILED (original)
  - Run 2: RUNNING/FAILED (auto-retry attempt 1)
  - Run 3: RUNNING/FAILED (auto-retry attempt 2)

### 3. Check Jira Ticket:
- A ticket should be auto-created
- Ticket should show "Auto-remediation attempted: retry_job"
- Status updates as retries progress

### 4. Check Dashboard:
- Open: `http://localhost:8000/dashboard`
- Look for real-time updates via WebSocket
- Should show remediation actions

---

## 🚨 Important Notes

1. **The job will keep failing** because we're using intentional errors
   - The auto-remediation will retry 3 times
   - After 3 failures, circuit breaker opens
   - System won't retry again for 5 minutes

2. **To test successful remediation**:
   - Create a job that fails intermittently (e.g., random number check)
   - Example:
     ```python
     import random
     if random.random() < 0.7:  # 70% chance of failure
         raise Exception("Random failure for testing")
     print("Success!")
     ```

3. **Circuit Breaker Limits**:
   - After 5 consecutive failures → circuit opens
   - System waits 5 minutes before trying again
   - This prevents infinite retry loops

---

## 🎬 Quick Start Command

```bash
# 1. Enable auto-remediation
echo "AUTO_REMEDIATION_ENABLED=true" >> genai_rca_assistant/.env

# 2. Start RCA system
cd genai_rca_assistant
uvicorn main:app --host 0.0.0.0 --port 8000 &

# 3. Run Test 1 in Databricks
# Copy the "Test 1" code to a Databricks notebook and run it

# 4. Watch the logs
tail -f logs/rca_system.log
```

---

## Expected Timeline

| Time | Event |
|------|-------|
| T+0s | Job fails with error |
| T+2s | Webhook received by RCA system |
| T+5s | AI analyzes error |
| T+10s | Auto-remediation decision made |
| T+15s | First retry triggered (Run 2 created) |
| T+45s | Second retry (if Run 2 fails) |
| T+105s | Third retry (if Run 2 fails) |
| T+225s | Circuit breaker opens (if all fail) |

