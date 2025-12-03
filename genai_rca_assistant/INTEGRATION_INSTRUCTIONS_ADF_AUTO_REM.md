# ADF Auto-Remediation Integration Instructions

## Overview
This document explains how to integrate ADF auto-remediation into your main.py file.

## Step 1: Add .env Configuration

Add these lines to your `.env` file:

```bash
# ============================================
# ADF AUTO-REMEDIATION CONFIGURATION
# ============================================

# Logic App webhook URL for ADF pipeline retry
ADF_RETRY_LOGIC_APP_WEBHOOK=https://prod-23.northcentralus.logic.azure.com:443/workflows/9f5c447ccfc74affab26171632db289e/triggers/When_RCA_sends_auto_remediation_request/paths/invoke?api-version=2016-10-01&sp=%2Ftriggers%2FWhen_RCA_sends_auto_remediation_request%2Frun&sv=1.0&sig=5H0Bea-2LWJKtDkv34Ej5CSZ5TJ3redDxdcBj4N0rbw

# Maximum retry attempts for ADF pipelines
ADF_MAX_RETRIES=2

# Delay between retry attempts (seconds)
ADF_RETRY_DELAY_SECONDS=60
```

## Step 2: Add Import to main.py

At the top of main.py, add this import (around line 35, with other imports):

```python
# ADF Auto-Remediation
from adf_auto_remediation_handler import (
    handle_adf_auto_remediation,
    should_retry_adf_error
)
```

## Step 3: Replace ADF Auto-Remediation Section

In the `@app.post("/azure-monitor")` function, find this section (around line 1058-1073):

```python
# Auto-Remediation (if enabled and AI deems it possible)
remediation_run_id = None
if AUTO_REMEDIATION_ENABLED and rca.get("auto_heal_possible"):
    error_type = rca.get("error_type")

    remediation_run_id = await asyncio.to_thread(
        execute_playbook, error_type, pipeline, runid, tid
    )

    if remediation_run_id:
        logger.info(f"Auto-remediation playbook triggered for {error_type}. Run ID: {remediation_run_id}")
        # Mark ticket as in-progress during remediation
        ticket_data["status"] = "in_progress"
        ticket_data["logic_app_run_id"] = remediation_run_id
    else:
        logger.warning(f"No playbook or failed to trigger playbook for {error_type}. Keeping status: open.")
```

**Replace it with:**

```python
# Auto-Remediation (if enabled and AI deems it possible)
remediation_run_id = None
remediation_results = None

if AUTO_REMEDIATION_ENABLED and rca.get("auto_heal_possible"):
    error_type = rca.get("error_type")

    # Check if this is an ADF error that should be retried
    if should_retry_adf_error(error_type):
        logger.info(f"🔄 ADF error '{error_type}' eligible for auto-remediation")

        # Execute ADF auto-remediation with retry logic
        remediation_results = await asyncio.to_thread(
            handle_adf_auto_remediation,
            pipeline_name=pipeline,
            run_id=runid,
            ticket_id=tid,
            error_type=error_type,
            original_error=desc
        )

        if remediation_results.get("success"):
            logger.info(f"✅ ADF auto-remediation completed")
            logger.info(f"   Attempts: {remediation_results['attempts']}")
            logger.info(f"   Retry Run IDs: {remediation_results['retry_run_ids']}")

            # Update ticket status
            ticket_data["status"] = "in_progress"
            ticket_data["logic_app_run_id"] = ", ".join(remediation_results["retry_run_ids"])

            # Store remediation info in recommendations
            remediation_note = f"Auto-remediation attempted: {remediation_results['message']}"
            current_recs = rca.get("recommendations", [])
            current_recs.insert(0, remediation_note)
            ticket_data["recommendations"] = json.dumps(current_recs)

        else:
            logger.error(f"❌ ADF auto-remediation failed: {remediation_results.get('message')}")
            ticket_data["status"] = "open"
    else:
        logger.info(f"ℹ️  Error type '{error_type}' not eligible for ADF auto-remediation")
```

## Step 4: Add Slack Notification for Remediation

After the database insert (around line 1130), add this code to send Slack notifications:

```python
# Send Slack notification if remediation was attempted
if remediation_results:
    slack_color = "good" if remediation_results.get("success") else "danger"
    slack_title = "✅ ADF Auto-Remediation Completed" if remediation_results.get("success") else "⚠️ ADF Auto-Remediation Failed"

    slack_fields = [
        {"title": "Pipeline", "value": pipeline, "short": True},
        {"title": "Original Run ID", "value": runid, "short": True},
        {"title": "Retry Attempts", "value": str(remediation_results["attempts"]), "short": True},
        {"title": "Retry Run IDs", "value": ", ".join(remediation_results["retry_run_ids"]) if remediation_results["retry_run_ids"] else "None", "short": True},
        {"title": "Status", "value": remediation_results["final_status"], "short": True},
        {"title": "Message", "value": remediation_results["message"], "short": False}
    ]

    await asyncio.to_thread(
        send_slack_alert,
        title=slack_title,
        description=f"Auto-remediation attempted for {pipeline}",
        fields=slack_fields,
        color=slack_color
    )
```

## Step 5: Test the Integration

### 5.1 Verify Configuration

```bash
python check_env.py
```

Should show:
```
✅ ADF_RETRY_LOGIC_APP_WEBHOOK: https://prod-23.northcentralus...
✅ ADF_MAX_RETRIES: 2
✅ ADF_RETRY_DELAY_SECONDS: 60
```

### 5.2 Test ADF Remediation Module

```bash
python adf_remediation.py
```

### 5.3 Trigger Test Failure

Trigger an ADF pipeline failure (e.g., by having a source blob not exist), and check:

1. **Uvicorn logs** for:
   ```
   🔄 ADF error 'UserErrorSourceBlobNotExists' eligible for auto-remediation
   🔄 Retry Attempt 1/2
   ✅ Retry triggered successfully
   🔄 Retry Attempt 2/2
   ✅ ADF auto-remediation completed
   ```

2. **Logic App runs** in Azure portal - you should see 2 new runs

3. **Slack channel** - should receive notification about auto-remediation

4. **Dashboard** - ticket should show status "in_progress" with retry run IDs

## Architecture Flow

```
ADF Pipeline Fails
       ↓
Azure Monitor Alert
       ↓
RCA System Webhook (/azure-monitor)
       ↓
AI Analyzes Error (auto_heal_possible: true)
       ↓
Check if Error is Retryable
       ↓
handle_adf_auto_remediation()
       ↓
┌─────────────────┐
│ Retry Loop      │
│  ├─ Attempt 1   │ → Logic App → ADF Pipeline Run 1
│  ├─ Wait 60s    │
│  ├─ Attempt 2   │ → Logic App → ADF Pipeline Run 2
│  └─ Complete    │
└─────────────────┘
       ↓
Update Ticket Status (in_progress)
       ↓
Send Slack Notification
       ↓
Log Audit Trail
```

## Troubleshooting

### Issue: "ADF_RETRY_LOGIC_APP_WEBHOOK not configured"
**Solution:** Add the webhook URL to your .env file

### Issue: "Logic App returned status 401"
**Solution:** Check that your Logic App webhook URL includes the correct `sig` parameter

### Issue: Retries triggered but no new pipeline runs
**Solution:**
- Verify Logic App is receiving the webhook calls
- Check Logic App run history in Azure portal
- Ensure ADF connection in Logic App is authorized

### Issue: Same error occurs after retry
**Solution:**
- Current implementation doesn't check if same error recurs
- To implement: Add Azure Data Factory SDK to check pipeline run status
- Compare error messages between runs
- Only close ticket if new run succeeds

## Future Enhancements

1. **Status Verification**
   - Install `azure-mgmt-datafactory` SDK
   - After each retry, poll for completion
   - Check if new run succeeded or failed
   - Auto-close ticket if succeeded

2. **Error Comparison**
   - After retry completes, fetch its error (if any)
   - Compare with original error
   - If same error occurs twice, stop retrying

3. **Dashboard Integration**
   - Show retry timeline in dashboard
   - Display retry run IDs as clickable links to ADF portal
   - Real-time status updates via WebSocket

4. **Metrics & Analytics**
   - Track retry success rate by error type
   - Average time to resolution
   - Most common failure types

## Configuration Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `ADF_RETRY_LOGIC_APP_WEBHOOK` | None | Logic App webhook URL |
| `ADF_MAX_RETRIES` | 2 | Maximum retry attempts |
| `ADF_RETRY_DELAY_SECONDS` | 60 | Seconds to wait between retries |
| `AUTO_REMEDIATION_ENABLED` | false | Master switch for auto-remediation |
