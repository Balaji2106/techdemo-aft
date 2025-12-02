"""
Health Check System for Post-Recovery Verification
Verifies that recovery actions were successful
"""
import os
import time
import logging
import requests
from typing import Tuple, Dict, Optional
from datetime import datetime, timedelta

logger = logging.getLogger("health_checks")

# Load configuration
DATABRICKS_HOST = os.getenv("DATABRICKS_HOST", "").rstrip('/')
DATABRICKS_TOKEN = os.getenv("DATABRICKS_TOKEN", "")

def _get_headers() -> dict:
    """Get Databricks API headers"""
    return {
        "Authorization": f"Bearer {DATABRICKS_TOKEN}",
        "Content-Type": "application/json"
    }


# ============================================
# CLUSTER HEALTH CHECKS
# ============================================

def check_cluster_health(cluster_id: str, timeout_seconds: int = 60) -> Tuple[bool, str, Dict]:
    """
    Comprehensive cluster health check

    Returns:
        (is_healthy, message, health_metrics)
    """
    if not DATABRICKS_HOST or not DATABRICKS_TOKEN:
        return False, "Databricks credentials not configured", {}

    logger.info(f"🏥 Running health check for cluster {cluster_id}...")

    health_metrics = {
        "cluster_id": cluster_id,
        "check_time": datetime.utcnow().isoformat(),
        "state": None,
        "is_running": False,
        "driver_healthy": False,
        "workers_healthy": False,
        "last_activity": None,
        "uptime_seconds": None,
    }

    try:
        # Get cluster details
        url = f"{DATABRICKS_HOST}/api/2.0/clusters/get"
        response = requests.get(url, headers=_get_headers(), params={"cluster_id": cluster_id}, timeout=10)

        if response.status_code != 200:
            return False, f"Failed to fetch cluster details: {response.status_code}", health_metrics

        cluster = response.json()
        state = cluster.get("state")
        health_metrics["state"] = state

        # Check 1: Cluster is running
        if state != "RUNNING":
            return False, f"Cluster is not running. Current state: {state}", health_metrics

        health_metrics["is_running"] = True

        # Check 2: No termination reason (shouldn't exist for running cluster)
        termination_reason = cluster.get("termination_reason")
        if termination_reason:
            return False, f"Cluster has termination reason: {termination_reason}", health_metrics

        # Check 3: Driver is healthy
        driver = cluster.get("driver", {})
        driver_node_id = driver.get("node_id")
        driver_private_ip = driver.get("private_ip")

        if driver_node_id and driver_private_ip:
            health_metrics["driver_healthy"] = True
        else:
            return False, "Driver node not healthy (missing node_id or IP)", health_metrics

        # Check 4: Workers are present (if not single-node cluster)
        num_workers = cluster.get("num_workers", 0)
        executors = cluster.get("executors", [])

        if num_workers > 0:
            if len(executors) < num_workers:
                return False, f"Not enough workers: {len(executors)}/{num_workers}", health_metrics
            health_metrics["workers_healthy"] = True
        else:
            # Single-node cluster
            health_metrics["workers_healthy"] = True

        # Check 5: Recent activity (cluster is responsive)
        last_activity_time = cluster.get("last_activity_time")
        if last_activity_time:
            last_activity_dt = datetime.fromtimestamp(last_activity_time / 1000)  # Convert from ms
            health_metrics["last_activity"] = last_activity_dt.isoformat()

            # If no activity in last 5 minutes, might be idle (still healthy)
            time_since_activity = datetime.utcnow() - last_activity_dt
            if time_since_activity > timedelta(hours=1):
                logger.warning(f"⚠️ Cluster {cluster_id} has been idle for {time_since_activity}")

        # Calculate uptime
        start_time = cluster.get("start_time")
        if start_time:
            start_dt = datetime.fromtimestamp(start_time / 1000)
            uptime = datetime.utcnow() - start_dt
            health_metrics["uptime_seconds"] = int(uptime.total_seconds())

        # Check 6: Cluster events (recent errors?)
        recent_events = get_cluster_events(cluster_id, last_n=5)
        if recent_events:
            error_events = [e for e in recent_events if "error" in e.get("type", "").lower()]
            if error_events:
                logger.warning(f"⚠️ Found {len(error_events)} recent error events for cluster {cluster_id}")
                health_metrics["recent_errors"] = len(error_events)

        # All checks passed
        logger.info(f"✅ Cluster {cluster_id} is healthy!")
        return True, "Cluster is healthy and running", health_metrics

    except Exception as e:
        logger.error(f"❌ Health check failed: {e}")
        return False, f"Health check exception: {str(e)}", health_metrics


def get_cluster_events(cluster_id: str, last_n: int = 10) -> list:
    """Get recent cluster events"""
    if not DATABRICKS_HOST or not DATABRICKS_TOKEN:
        return []

    try:
        url = f"{DATABRICKS_HOST}/api/2.0/clusters/events"
        payload = {
            "cluster_id": cluster_id,
            "order": "DESC",
            "limit": last_n
        }
        response = requests.post(url, headers=_get_headers(), json=payload, timeout=10)

        if response.status_code == 200:
            return response.json().get("events", [])
    except Exception as e:
        logger.error(f"Failed to fetch cluster events: {e}")

    return []


# ============================================
# JOB HEALTH CHECKS
# ============================================

def check_job_run_health(run_id: str) -> Tuple[bool, str, Dict]:
    """
    Check if a job run completed successfully

    Returns:
        (is_healthy, message, health_metrics)
    """
    if not DATABRICKS_HOST or not DATABRICKS_TOKEN:
        return False, "Databricks credentials not configured", {}

    logger.info(f"🏥 Running health check for job run {run_id}...")

    health_metrics = {
        "run_id": run_id,
        "check_time": datetime.utcnow().isoformat(),
        "life_cycle_state": None,
        "result_state": None,
        "is_successful": False,
    }

    try:
        url = f"{DATABRICKS_HOST}/api/2.1/jobs/runs/get"
        response = requests.get(url, headers=_get_headers(), params={"run_id": run_id}, timeout=10)

        if response.status_code != 200:
            return False, f"Failed to fetch run details: {response.status_code}", health_metrics

        run = response.json()
        state = run.get("state", {})

        life_cycle_state = state.get("life_cycle_state")
        result_state = state.get("result_state")

        health_metrics["life_cycle_state"] = life_cycle_state
        health_metrics["result_state"] = result_state

        # Check if run is still running
        if life_cycle_state in ["PENDING", "RUNNING", "TERMINATING"]:
            return False, f"Run is not yet complete: {life_cycle_state}", health_metrics

        # Check if run succeeded
        if life_cycle_state == "TERMINATED" and result_state == "SUCCESS":
            health_metrics["is_successful"] = True
            logger.info(f"✅ Job run {run_id} completed successfully!")
            return True, "Job run completed successfully", health_metrics

        # Run failed or was cancelled
        error_message = state.get("state_message", "Unknown error")
        return False, f"Job run failed: {error_message}", health_metrics

    except Exception as e:
        logger.error(f"❌ Health check failed: {e}")
        return False, f"Health check exception: {str(e)}", health_metrics


def wait_for_job_completion(run_id: str, timeout_seconds: int = 600, poll_interval: int = 10) -> Tuple[bool, str]:
    """
    Wait for a job run to complete (with timeout)

    Returns:
        (success, message)
    """
    logger.info(f"⏳ Waiting for job run {run_id} to complete (timeout: {timeout_seconds}s)...")

    start_time = time.time()

    while (time.time() - start_time) < timeout_seconds:
        is_healthy, message, metrics = check_job_run_health(run_id)

        life_cycle_state = metrics.get("life_cycle_state")

        # If run is complete (success or failure)
        if life_cycle_state in ["TERMINATED", "SKIPPED", "INTERNAL_ERROR"]:
            if is_healthy:
                elapsed = int(time.time() - start_time)
                return True, f"Job completed successfully in {elapsed} seconds"
            else:
                return False, message

        # Still running, wait and check again
        logger.info(f"   Job state: {life_cycle_state}, waiting {poll_interval}s...")
        time.sleep(poll_interval)

    # Timeout reached
    elapsed = int(time.time() - start_time)
    return False, f"Job run timeout after {elapsed} seconds"


# ============================================
# LIBRARY HEALTH CHECKS
# ============================================

def check_library_status(cluster_id: str, library_name: str) -> Tuple[bool, str]:
    """
    Check if a library is successfully installed on a cluster

    Returns:
        (is_installed, status_message)
    """
    if not DATABRICKS_HOST or not DATABRICKS_TOKEN:
        return False, "Databricks credentials not configured"

    logger.info(f"🏥 Checking library {library_name} on cluster {cluster_id}...")

    try:
        url = f"{DATABRICKS_HOST}/api/2.0/libraries/cluster-status"
        response = requests.get(url, headers=_get_headers(), params={"cluster_id": cluster_id}, timeout=10)

        if response.status_code != 200:
            return False, f"Failed to fetch library status: {response.status_code}"

        data = response.json()
        library_statuses = data.get("library_statuses", [])

        # Search for the library
        for lib_status in library_statuses:
            library = lib_status.get("library", {})
            pypi = library.get("pypi", {})
            package = pypi.get("package", "")

            # Check if this is our library (handle version in package name)
            if library_name in package or package in library_name:
                status = lib_status.get("status")

                if status == "INSTALLED":
                    logger.info(f"✅ Library {library_name} is installed")
                    return True, f"Library {library_name} is installed"
                elif status == "PENDING":
                    return False, f"Library {library_name} installation is pending"
                elif status == "FAILED":
                    messages = lib_status.get("messages", [])
                    error = messages[0] if messages else "Unknown error"
                    return False, f"Library {library_name} installation failed: {error}"
                else:
                    return False, f"Library {library_name} status: {status}"

        # Library not found in status list
        return False, f"Library {library_name} not found in cluster libraries"

    except Exception as e:
        logger.error(f"❌ Library check failed: {e}")
        return False, f"Library check exception: {str(e)}"


# ============================================
# COMPREHENSIVE HEALTH CHECK
# ============================================

def comprehensive_health_check(
    cluster_id: Optional[str] = None,
    run_id: Optional[str] = None,
    check_type: str = "auto"
) -> Tuple[bool, str, Dict]:
    """
    Run comprehensive health check based on what needs to be verified

    Args:
        cluster_id: Cluster to check
        run_id: Job run to check
        check_type: "cluster", "job", "both", or "auto"

    Returns:
        (is_healthy, message, all_metrics)
    """
    logger.info("🏥 Running comprehensive health check...")

    all_metrics = {}
    all_checks_passed = True
    messages = []

    # Determine what to check
    should_check_cluster = (check_type in ["cluster", "both", "auto"]) and cluster_id
    should_check_job = (check_type in ["job", "both", "auto"]) and run_id

    # Check cluster health
    if should_check_cluster:
        cluster_healthy, cluster_msg, cluster_metrics = check_cluster_health(cluster_id)
        all_metrics["cluster"] = cluster_metrics

        if not cluster_healthy:
            all_checks_passed = False
            messages.append(f"Cluster: {cluster_msg}")
        else:
            messages.append("Cluster: Healthy")

    # Check job health
    if should_check_job:
        job_healthy, job_msg, job_metrics = check_job_run_health(run_id)
        all_metrics["job"] = job_metrics

        if not job_healthy:
            all_checks_passed = False
            messages.append(f"Job: {job_msg}")
        else:
            messages.append("Job: Healthy")

    # Combine results
    if all_checks_passed:
        final_message = "All health checks passed: " + ", ".join(messages)
        logger.info(f"✅ {final_message}")
        return True, final_message, all_metrics
    else:
        final_message = "Health check failures: " + ", ".join(messages)
        logger.error(f"❌ {final_message}")
        return False, final_message, all_metrics


if __name__ == "__main__":
    # Test health checks
    print("🧪 Testing Health Check System\n")

    # Note: These tests require valid Databricks credentials and cluster/run IDs
    print("✅ Health check system ready!")
    print("\nExample usage:")
    print("  is_healthy, msg, metrics = check_cluster_health('cluster-id')")
    print("  is_healthy, msg, metrics = check_job_run_health('run-id')")
    print("  success, msg = wait_for_job_completion('run-id', timeout_seconds=600)")
