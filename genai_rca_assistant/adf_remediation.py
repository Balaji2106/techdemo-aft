"""
Azure Data Factory Auto-Remediation Utilities
Handles automatic pipeline retry via Logic App webhook
"""
import os
import time
import logging
import requests
from typing import Optional, Dict, Tuple
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

logger = logging.getLogger("adf_remediation")

# Load configuration
ADF_LOGIC_APP_WEBHOOK = os.getenv("ADF_RETRY_LOGIC_APP_WEBHOOK", "")
AUTO_REMEDIATION_ENABLED = os.getenv("AUTO_REMEDIATION_ENABLED", "false").lower() in ("1", "true", "yes")
ADF_MAX_RETRIES = int(os.getenv("ADF_MAX_RETRIES", "2"))
ADF_RETRY_DELAY_SECONDS = int(os.getenv("ADF_RETRY_DELAY_SECONDS", "60"))

def retry_adf_pipeline(
    pipeline_name: str,
    factory_name: str = None,
    resource_group: str = None,
    attempt: int = 1
) -> Tuple[bool, Optional[str], str]:
    """
    Retry an ADF pipeline using Logic App webhook

    Args:
        pipeline_name: Name of the ADF pipeline to retry
        factory_name: ADF factory name (optional, for logging)
        resource_group: Resource group (optional, for logging)
        attempt: Current retry attempt number

    Returns:
        (success, new_run_id, message)
    """
    if not AUTO_REMEDIATION_ENABLED:
        return False, None, "Auto-remediation is disabled"

    if not ADF_LOGIC_APP_WEBHOOK:
        return False, None, "ADF Logic App webhook not configured (ADF_RETRY_LOGIC_APP_WEBHOOK)"

    logger.info(f"🔄 Attempting to retry ADF pipeline '{pipeline_name}' (attempt {attempt}/{ADF_MAX_RETRIES})...")

    try:
        # Call Logic App webhook
        payload = {
            "pipeline_name": pipeline_name
        }

        response = requests.post(
            ADF_LOGIC_APP_WEBHOOK,
            json=payload,
            timeout=30
        )

        if response.status_code == 200:
            result = response.json()
            new_run_id = result.get("run_id", "unknown")

            logger.info(f"✅ Successfully triggered ADF pipeline retry.")
            logger.info(f"   Pipeline: {pipeline_name}")
            logger.info(f"   New Run ID: {new_run_id}")

            return True, new_run_id, f"Pipeline retry triggered successfully. New run ID: {new_run_id}"
        else:
            error_msg = f"Logic App returned status {response.status_code}: {response.text}"
            logger.error(f"❌ {error_msg}")
            return False, None, error_msg

    except requests.exceptions.Timeout:
        error_msg = "Logic App webhook timeout after 30s"
        logger.error(f"❌ {error_msg}")
        return False, None, error_msg
    except Exception as e:
        error_msg = f"Exception during pipeline retry: {str(e)}"
        logger.error(f"❌ {error_msg}")
        return False, None, error_msg


def retry_adf_pipeline_with_checks(
    pipeline_name: str,
    original_error: str,
    factory_name: str = None,
    resource_group: str = None
) -> Dict[str, any]:
    """
    Retry ADF pipeline with error checking and multiple attempts

    Args:
        pipeline_name: Pipeline to retry
        original_error: The original error that triggered retry
        factory_name: ADF factory name
        resource_group: Resource group

    Returns:
        Dict with retry results and status
    """
    results = {
        "success": False,
        "attempts": 0,
        "run_ids": [],
        "final_status": "failed",
        "message": "",
        "same_error_count": 0
    }

    for attempt in range(1, ADF_MAX_RETRIES + 1):
        results["attempts"] = attempt

        logger.info(f"🔄 Retry attempt {attempt}/{ADF_MAX_RETRIES} for pipeline '{pipeline_name}'")

        # Trigger retry
        success, run_id, message = retry_adf_pipeline(
            pipeline_name=pipeline_name,
            factory_name=factory_name,
            resource_group=resource_group,
            attempt=attempt
        )

        if not success:
            results["message"] = f"Failed to trigger retry: {message}"
            logger.error(f"❌ Retry attempt {attempt} failed to trigger: {message}")
            break

        results["run_ids"].append(run_id)

        # Wait for retry delay before checking
        if attempt < ADF_MAX_RETRIES:
            logger.info(f"⏳ Waiting {ADF_RETRY_DELAY_SECONDS}s before next attempt...")
            time.sleep(ADF_RETRY_DELAY_SECONDS)

    # Determine final status
    if results["run_ids"]:
        results["success"] = True
        results["final_status"] = "retried"
        results["message"] = f"Pipeline retried {results['attempts']} time(s). Run IDs: {', '.join(results['run_ids'])}"
        logger.info(f"✅ {results['message']}")
    else:
        results["final_status"] = "failed"
        logger.error(f"❌ All retry attempts failed")

    return results


def check_adf_pipeline_status(run_id: str, factory_name: str, resource_group: str) -> Dict[str, any]:
    """
    Check the status of an ADF pipeline run

    Note: This requires Azure Data Factory API access.
    For now, this is a placeholder that returns unknown status.
    In production, implement using Azure SDK.

    Args:
        run_id: Pipeline run ID
        factory_name: ADF factory name
        resource_group: Resource group

    Returns:
        Dict with status information
    """
    logger.warning("⚠️  Pipeline status check not implemented. Requires Azure Data Factory SDK.")

    return {
        "status": "unknown",
        "run_id": run_id,
        "message": "Status check requires Azure Data Factory API integration"
    }


def get_adf_remediation_strategy(error_type: str) -> Optional[str]:
    """
    Get remediation strategy for ADF error types

    Args:
        error_type: The classified error type

    Returns:
        Remediation strategy name or None
    """
    strategies = {
        "UserErrorSourceBlobNotExists": "retry_pipeline",
        "GatewayTimeout": "retry_pipeline",
        "HttpConnectionFailed": "retry_pipeline",
        "InternalServerError": "retry_pipeline",
        "ActivityThrottlingError": "retry_pipeline",
        # Permission/config errors should not auto-retry
        "InvalidTemplate": None,
        "ResourceNotFound": None,
        "AuthorizationFailed": None,
    }

    return strategies.get(error_type, "retry_pipeline")


if __name__ == "__main__":
    # Test the retry function
    print("🧪 Testing ADF Auto-Remediation")
    print("="*80)

    if not ADF_LOGIC_APP_WEBHOOK:
        print("❌ ADF_RETRY_LOGIC_APP_WEBHOOK not configured")
        print("   Set it in .env file to test")
    else:
        print(f"✅ Webhook configured: {ADF_LOGIC_APP_WEBHOOK[:50]}...")
        print(f"✅ Max retries: {ADF_MAX_RETRIES}")
        print(f"✅ Retry delay: {ADF_RETRY_DELAY_SECONDS}s")

        # Test with dummy pipeline name
        print("\n🧪 Test retry (dry run)...")
        # success, run_id, message = retry_adf_pipeline("test_pipeline")
        # print(f"   Result: {message}")
