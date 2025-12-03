"""
ADF Auto-Remediation Handler
Manages the complete auto-remediation flow for Azure Data Factory failures
"""
import logging
import time
from typing import Dict, Optional
from adf_remediation import (
    retry_adf_pipeline,
    ADF_MAX_RETRIES,
    ADF_RETRY_DELAY_SECONDS
)

logger = logging.getLogger("adf_auto_remediation_handler")


def handle_adf_auto_remediation(
    pipeline_name: str,
    run_id: str,
    ticket_id: str,
    error_type: str,
    original_error: str
) -> Dict[str, any]:
    """
    Handle complete auto-remediation flow for ADF pipeline failures

    This function:
    1. Retries the pipeline up to MAX_RETRIES times
    2. Waits between retries to allow pipeline to complete
    3. Checks if same error occurs (placeholder for now)
    4. Returns remediation results

    Args:
        pipeline_name: Name of the failed pipeline
        run_id: Original run ID that failed
        ticket_id: RCA system ticket ID
        error_type: Classified error type from AI
        original_error: Original error message

    Returns:
        Dict with remediation results:
        {
            "success": bool,
            "attempts": int,
            "retry_run_ids": [str],
            "final_status": "resolved" | "retried" | "failed",
            "message": str,
            "should_close_ticket": bool
        }
    """
    logger.info("="*80)
    logger.info(f"🔄 Starting ADF Auto-Remediation")
    logger.info(f"   Pipeline: {pipeline_name}")
    logger.info(f"   Original Run ID: {run_id}")
    logger.info(f"   Ticket ID: {ticket_id}")
    logger.info(f"   Error Type: {error_type}")
    logger.info("="*80)

    results = {
        "success": False,
        "attempts": 0,
        "retry_run_ids": [],
        "final_status": "failed",
        "message": "",
        "should_close_ticket": False,
        "remediation_actions": []
    }

    # Attempt retries
    for attempt in range(1, ADF_MAX_RETRIES + 1):
        results["attempts"] = attempt

        logger.info(f"\n🔄 Retry Attempt {attempt}/{ADF_MAX_RETRIES}")
        logger.info(f"   Triggering pipeline: {pipeline_name}")

        # Trigger retry via Logic App
        success, new_run_id, message = retry_adf_pipeline(
            pipeline_name=pipeline_name,
            attempt=attempt
        )

        action = {
            "attempt": attempt,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "action": "retry_pipeline",
            "success": success,
            "run_id": new_run_id,
            "message": message
        }
        results["remediation_actions"].append(action)

        if not success:
            logger.error(f"❌ Attempt {attempt} failed to trigger: {message}")
            results["message"] = f"Failed to trigger retry on attempt {attempt}: {message}"
            break

        results["retry_run_ids"].append(new_run_id)
        logger.info(f"✅ Retry triggered successfully")
        logger.info(f"   New Run ID: {new_run_id}")

        # Wait before next attempt (except on last attempt)
        if attempt < ADF_MAX_RETRIES:
            logger.info(f"⏳ Waiting {ADF_RETRY_DELAY_SECONDS}s before next retry...")
            time.sleep(ADF_RETRY_DELAY_SECONDS)

    # Determine final status
    if results["retry_run_ids"]:
        results["success"] = True
        results["final_status"] = "retried"

        # Note: In a full implementation, you would:
        # 1. Check each retry_run_id to see if it succeeded
        # 2. If any succeeded, set should_close_ticket = True
        # 3. If all failed with same error, escalate

        results["message"] = (
            f"Pipeline '{pipeline_name}' retried {results['attempts']} time(s). "
            f"New run IDs: {', '.join(results['retry_run_ids'])}. "
            f"Manual verification required to confirm resolution."
        )

        # Placeholder: Assume success if we got this far
        # In production, implement actual status checking
        logger.info("⚠️  Note: Automatic status verification not implemented.")
        logger.info("   Run IDs created, but success/failure verification requires Azure Data Factory SDK.")

    else:
        results["final_status"] = "failed"
        results["message"] = f"All {ADF_MAX_RETRIES} retry attempts failed to trigger"

    logger.info("="*80)
    logger.info(f"🏁 ADF Auto-Remediation Complete")
    logger.info(f"   Final Status: {results['final_status']}")
    logger.info(f"   Retry Run IDs: {results['retry_run_ids']}")
    logger.info(f"   Message: {results['message']}")
    logger.info("="*80)

    return results


def should_retry_adf_error(error_type: str) -> bool:
    """
    Determine if this ADF error type should trigger auto-retry

    Args:
        error_type: Classified error type

    Returns:
        True if should retry, False otherwise
    """
    # Errors that should be retried
    retryable_errors = {
        "UserErrorSourceBlobNotExists",  # Upstream dependency issue
        "GatewayTimeout",                # Temporary network issue
        "HttpConnectionFailed",          # Connectivity issue
        "InternalServerError",           # Azure service issue
        "ActivityThrottlingError",       # Rate limiting, retry helps
    }

    # Errors that should NOT be retried (require manual fix)
    non_retryable_errors = {
        "InvalidTemplate",               # Configuration error
        "ResourceNotFound",              # Missing resource
        "AuthorizationFailed",           # Permission issue
    }

    if error_type in non_retryable_errors:
        logger.info(f"❌ Error type '{error_type}' is not retryable (requires manual intervention)")
        return False

    if error_type in retryable_errors:
        logger.info(f"✅ Error type '{error_type}' is retryable")
        return True

    # Default: if AI marked it as auto_heal_possible, allow retry
    logger.info(f"⚠️  Error type '{error_type}' not in known list, but AI marked as auto-healable")
    return True


if __name__ == "__main__":
    # Test the handler
    print("🧪 Testing ADF Auto-Remediation Handler")
    print("="*80)

    test_result = handle_adf_auto_remediation(
        pipeline_name="test_pipeline",
        run_id="test_run_123",
        ticket_id="ADF-TEST-001",
        error_type="GatewayTimeout",
        original_error="Gateway timeout after 60 seconds"
    )

    print("\n📊 Test Results:")
    print(f"   Success: {test_result['success']}")
    print(f"   Attempts: {test_result['attempts']}")
    print(f"   Status: {test_result['final_status']}")
    print(f"   Message: {test_result['message']}")
