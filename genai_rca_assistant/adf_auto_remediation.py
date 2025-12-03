"""
ADF Auto-Remediation with Logic App Integration
Handles automatic pipeline retry, monitoring, and ticket updates
"""
import os
import time
import logging
import requests
from typing import Dict, Tuple
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
LOGIC_APP_WEBHOOK = os.getenv("ADF_LOGIC_APP_WEBHOOK", "")
AUTO_REMEDIATION_ENABLED = os.getenv("AUTO_REMEDIATION_ENABLED", "false").lower() == "true"
MAX_RETRIES = int(os.getenv("ADF_MAX_RETRIES", "2"))
MONITOR_INTERVAL = int(os.getenv("ADF_MONITOR_INTERVAL", "30"))
MONITOR_TIMEOUT = int(os.getenv("ADF_MONITOR_TIMEOUT", "300"))

# Auto-solvable error patterns
AUTO_SOLVABLE_ERRORS = [
    "UserErrorSourceBlobNotExists",
    "GatewayTimeout",
    "HttpConnectionFailed",
    "InternalServerError",
    "ActivityThrottlingError",
    "ServiceUnavailable",
    "TransientError"
]


def is_auto_solvable(error_message: str, error_code: str = None) -> bool:
    """Check if error is auto-solvable"""
    if error_code and error_code in AUTO_SOLVABLE_ERRORS:
        return True

    for pattern in AUTO_SOLVABLE_ERRORS:
        if pattern.lower() in error_message.lower():
            return True

    return False


def trigger_logic_app(pipeline_name: str, factory_name: str, resource_group: str) -> Tuple[bool, str, str]:
    """
    Trigger Logic App to create pipeline run
    Returns: (success, run_id, message)
    """
    if not LOGIC_APP_WEBHOOK:
        return False, None, "Logic App webhook not configured"

    try:
        payload = {
            "pipelineName": pipeline_name,
            "factoryName": factory_name,
            "resourceGroup": resource_group,
            "action": "retry"
        }

        response = requests.post(LOGIC_APP_WEBHOOK, json=payload, timeout=30)

        if response.status_code == 200:
            result = response.json()
            run_id = result.get("runId", "unknown")
            logger.info(f"Logic App triggered. Run ID: {run_id}")
            return True, run_id, "Pipeline retry triggered"
        else:
            error_msg = f"Logic App failed: {response.status_code} - {response.text}"
            logger.error(error_msg)
            return False, None, error_msg

    except Exception as e:
        error_msg = f"Failed to trigger Logic App: {str(e)}"
        logger.error(error_msg)
        return False, None, error_msg


def monitor_pipeline_status(run_id: str, pipeline_name: str) -> str:
    """
    Monitor pipeline status via Logic App
    Returns: 'Succeeded', 'Failed', 'InProgress', or 'Timeout'
    """
    if not LOGIC_APP_WEBHOOK:
        return "Unknown"

    monitor_endpoint = f"{LOGIC_APP_WEBHOOK.replace('/retry', '/status')}"
    start_time = time.time()

    while (time.time() - start_time) < MONITOR_TIMEOUT:
        try:
            payload = {"runId": run_id, "pipelineName": pipeline_name}
            response = requests.post(monitor_endpoint, json=payload, timeout=10)

            if response.status_code == 200:
                result = response.json()
                status = result.get("status", "Unknown")

                if status in ["Succeeded", "Failed", "Cancelled"]:
                    return status

                logger.info(f"Pipeline {run_id} status: {status}")
                time.sleep(MONITOR_INTERVAL)
            else:
                logger.warning(f"Status check failed: {response.status_code}")
                time.sleep(MONITOR_INTERVAL)

        except Exception as e:
            logger.error(f"Error monitoring pipeline: {str(e)}")
            time.sleep(MONITOR_INTERVAL)

    return "Timeout"


def update_ticket(ticket_id: str, status: str, message: str) -> bool:
    """Update ticket with remediation status"""
    try:
        ticket_webhook = os.getenv("TICKET_UPDATE_WEBHOOK", "")
        if not ticket_webhook:
            logger.warning("No ticket update webhook configured")
            return False

        payload = {
            "ticketId": ticket_id,
            "status": status,
            "message": message,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }

        response = requests.post(ticket_webhook, json=payload, timeout=10)
        return response.status_code == 200

    except Exception as e:
        logger.error(f"Failed to update ticket: {str(e)}")
        return False


def remediate_adf_pipeline(
    pipeline_name: str,
    factory_name: str,
    resource_group: str,
    error_message: str,
    error_code: str = None,
    ticket_id: str = None
) -> Dict:
    """
    Main auto-remediation function
    """
    result = {
        "success": False,
        "run_ids": [],
        "final_status": "not_attempted",
        "message": "",
        "ticket_updated": False
    }

    if not AUTO_REMEDIATION_ENABLED:
        result["message"] = "Auto-remediation disabled"
        return result

    # Check if error is auto-solvable
    if not is_auto_solvable(error_message, error_code):
        result["message"] = "Error not auto-solvable"
        logger.info(f"Error not auto-solvable: {error_code or error_message[:100]}")
        return result

    logger.info(f"Starting auto-remediation for pipeline: {pipeline_name}")

    # Attempt retries
    for attempt in range(1, MAX_RETRIES + 1):
        logger.info(f"Retry attempt {attempt}/{MAX_RETRIES}")

        # Trigger Logic App
        success, run_id, msg = trigger_logic_app(pipeline_name, factory_name, resource_group)

        if not success:
            result["message"] = f"Failed to trigger retry: {msg}"
            break

        result["run_ids"].append(run_id)

        # Monitor pipeline
        status = monitor_pipeline_status(run_id, pipeline_name)
        logger.info(f"Pipeline {run_id} completed with status: {status}")

        if status == "Succeeded":
            result["success"] = True
            result["final_status"] = "remediated_successfully"
            result["message"] = f"Pipeline remediated successfully on attempt {attempt}"

            if ticket_id:
                update_ticket(ticket_id, "resolved", result["message"])
                result["ticket_updated"] = True

            return result

        elif status == "Failed":
            logger.warning(f"Retry {attempt} failed")
            if attempt == MAX_RETRIES:
                # All retries exhausted
                result["final_status"] = "remediation_failed"
                result["message"] = f"Auto-remediation applied ({len(result['run_ids'])} attempts) but problem persists"

                if ticket_id:
                    update_ticket(
                        ticket_id,
                        "remediation_failed",
                        f"Auto-remediation applied ({len(result['run_ids'])} retries) but problem persists"
                    )
                    result["ticket_updated"] = True

        elif status == "Timeout":
            logger.warning(f"Monitoring timeout on attempt {attempt}")
            if attempt == MAX_RETRIES:
                result["final_status"] = "monitoring_timeout"
                result["message"] = "Pipeline monitoring timed out"

    return result


if __name__ == "__main__":
    print("ADF Auto-Remediation Test")
    print(f"Auto-remediation enabled: {AUTO_REMEDIATION_ENABLED}")
    print(f"Logic App webhook configured: {'Yes' if LOGIC_APP_WEBHOOK else 'No'}")
    print(f"Max retries: {MAX_RETRIES}")
    print(f"Monitor interval: {MONITOR_INTERVAL}s")
    print(f"Monitor timeout: {MONITOR_TIMEOUT}s")

    # Test auto-solvable detection
    test_errors = [
        ("UserErrorSourceBlobNotExists: File not found", None),
        ("GatewayTimeout occurred", "GatewayTimeout"),
        ("InvalidTemplate: Bad configuration", "InvalidTemplate")
    ]

    print("\nAuto-solvable error detection:")
    for msg, code in test_errors:
        solvable = is_auto_solvable(msg, code)
        print(f"  {code or msg[:40]}: {'✓ Auto-solvable' if solvable else '✗ Not auto-solvable'}")
