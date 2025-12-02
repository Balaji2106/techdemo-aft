"""
Databricks Auto-Remediation Utilities
Handles automatic recovery for Databricks job/cluster failures
"""
import os
import time
import logging
import requests
from typing import Optional, Dict, List, Tuple
from datetime import datetime

logger = logging.getLogger("databricks_remediation")

# Load configuration
DATABRICKS_HOST = os.getenv("DATABRICKS_HOST", "").rstrip('/')
DATABRICKS_TOKEN = os.getenv("DATABRICKS_TOKEN", "")
AUTO_REMEDIATION_ENABLED = os.getenv("AUTO_REMEDIATION_ENABLED", "false").lower() in ("1", "true", "yes")
AUTO_REMEDIATION_MAX_RETRIES = int(os.getenv("AUTO_REMEDIATION_MAX_RETRIES", "3"))
RETRY_BASE_DELAY_SECONDS = int(os.getenv("RETRY_BASE_DELAY_SECONDS", "30"))
RETRY_MAX_DELAY_SECONDS = int(os.getenv("RETRY_MAX_DELAY_SECONDS", "300"))
AUTO_SCALE_ENABLED = os.getenv("AUTO_SCALE_ENABLED", "true").lower() in ("1", "true", "yes")
MAX_CLUSTER_WORKERS = int(os.getenv("MAX_CLUSTER_WORKERS", "10"))
SCALE_UP_PERCENTAGE = int(os.getenv("SCALE_UP_PERCENTAGE", "50"))
AUTO_RESTART_ENABLED = os.getenv("AUTO_RESTART_ENABLED", "true").lower() in ("1", "true", "yes")
RESTART_TIMEOUT_MINUTES = int(os.getenv("RESTART_TIMEOUT_MINUTES", "10"))

# Library version fallbacks
LIBRARY_VERSION_FALLBACKS = {
    "pandas": ["2.1.0", "2.0.3", "1.5.3"],
    "numpy": ["1.24.3", "1.23.5", "1.22.4"],
    "scikit-learn": ["1.3.0", "1.2.2", "1.1.3"],
    "matplotlib": ["3.7.2", "3.6.3", "3.5.3"],
    "requests": ["2.31.0", "2.28.2", "2.27.1"],
    "pyspark": ["3.4.0", "3.3.2", "3.3.1"],
}

def _get_headers() -> dict:
    """Get Databricks API headers"""
    return {
        "Authorization": f"Bearer {DATABRICKS_TOKEN}",
        "Content-Type": "application/json"
    }


# ============================================
# 1. JOB RETRY FUNCTIONS
# ============================================

def retry_databricks_job(job_id: str, reason: str = "Auto-remediation") -> Tuple[bool, Optional[str], str]:
    """
    Retry a failed Databricks job
    
    Returns:
        (success, new_run_id, message)
    """
    if not AUTO_REMEDIATION_ENABLED:
        return False, None, "Auto-remediation is disabled"
    
    if not DATABRICKS_HOST or not DATABRICKS_TOKEN:
        return False, None, "Databricks credentials not configured"
    
    logger.info(f"🔄 Attempting to retry Databricks job {job_id}...")
    
    url = f"{DATABRICKS_HOST}/api/2.1/jobs/run-now"
    headers = _get_headers()
    payload = {"job_id": int(job_id)}
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            new_run_id = data.get("run_id")
            logger.info(f"✅ Successfully triggered job retry. New run_id: {new_run_id}")
            return True, str(new_run_id), f"Job retry successful. New run: {new_run_id}"
        else:
            error_msg = f"Failed to retry job. Status: {response.status_code}, Response: {response.text}"
            logger.error(f"❌ {error_msg}")
            return False, None, error_msg
            
    except Exception as e:
        error_msg = f"Exception during job retry: {str(e)}"
        logger.error(f"❌ {error_msg}")
        return False, None, error_msg


def retry_databricks_job_with_backoff(
    job_id: str, 
    attempt: int = 1, 
    max_attempts: int = None
) -> Tuple[bool, Optional[str], str]:
    """
    Retry a Databricks job with exponential backoff
    
    Args:
        job_id: The Databricks job ID
        attempt: Current retry attempt number
        max_attempts: Maximum number of retries (defaults to AUTO_REMEDIATION_MAX_RETRIES)
    
    Returns:
        (success, new_run_id, message)
    """
    if max_attempts is None:
        max_attempts = AUTO_REMEDIATION_MAX_RETRIES
    
    if attempt > max_attempts:
        return False, None, f"Max retry attempts ({max_attempts}) exceeded"
    
    # Calculate backoff delay (exponential: 30s, 60s, 120s, ...)
    delay = min(RETRY_BASE_DELAY_SECONDS * (2 ** (attempt - 1)), RETRY_MAX_DELAY_SECONDS)
    
    logger.info(f"⏳ Waiting {delay} seconds before retry attempt {attempt}/{max_attempts}...")
    time.sleep(delay)
    
    return retry_databricks_job(job_id, f"Auto-remediation attempt {attempt}/{max_attempts}")


# ============================================
# 2. CLUSTER SCALING FUNCTIONS
# ============================================

def get_cluster_config(cluster_id: str) -> Optional[Dict]:
    """Get current cluster configuration"""
    if not DATABRICKS_HOST or not DATABRICKS_TOKEN:
        return None
    
    url = f"{DATABRICKS_HOST}/api/2.0/clusters/get"
    headers = _get_headers()
    params = {"cluster_id": cluster_id}
    
    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        if response.status_code == 200:
            return response.json()
        else:
            logger.error(f"Failed to get cluster config: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        logger.error(f"Exception getting cluster config: {e}")
        return None


def scale_cluster(cluster_id: str, new_num_workers: int) -> Tuple[bool, str]:
    """
    Scale a Databricks cluster to a new number of workers
    
    Returns:
        (success, message)
    """
    if not AUTO_SCALE_ENABLED:
        return False, "Auto-scaling is disabled"
    
    if not DATABRICKS_HOST or not DATABRICKS_TOKEN:
        return False, "Databricks credentials not configured"
    
    logger.info(f"📊 Scaling cluster {cluster_id} to {new_num_workers} workers...")
    
    url = f"{DATABRICKS_HOST}/api/2.0/clusters/resize"
    headers = _get_headers()
    payload = {
        "cluster_id": cluster_id,
        "num_workers": new_num_workers
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        
        if response.status_code == 200:
            logger.info(f"✅ Successfully scaled cluster to {new_num_workers} workers")
            return True, f"Cluster scaled to {new_num_workers} workers"
        else:
            error_msg = f"Failed to scale cluster. Status: {response.status_code}, Response: {response.text}"
            logger.error(f"❌ {error_msg}")
            return False, error_msg
            
    except Exception as e:
        error_msg = f"Exception during cluster scaling: {str(e)}"
        logger.error(f"❌ {error_msg}")
        return False, error_msg


def auto_scale_cluster_on_failure(cluster_id: str) -> Tuple[bool, str]:
    """
    Automatically scale up a cluster after resource exhaustion failure
    
    Returns:
        (success, message)
    """
    # Get current cluster configuration
    config = get_cluster_config(cluster_id)
    
    if not config:
        return False, "Could not retrieve cluster configuration"
    
    current_workers = config.get("num_workers", 0)
    
    # Check if cluster has autoscaling
    autoscale = config.get("autoscale")
    if autoscale:
        current_workers = autoscale.get("min_workers", current_workers)
        max_workers = autoscale.get("max_workers", current_workers * 2)
    else:
        max_workers = MAX_CLUSTER_WORKERS
    
    # Calculate new worker count (increase by SCALE_UP_PERCENTAGE)
    new_workers = int(current_workers * (1 + SCALE_UP_PERCENTAGE / 100))
    new_workers = min(new_workers, max_workers)
    
    if new_workers <= current_workers:
        return False, f"Cluster already at max capacity ({current_workers} workers)"
    
    logger.info(f"🚀 Auto-scaling cluster from {current_workers} to {new_workers} workers")
    
    return scale_cluster(cluster_id, new_workers)


# ============================================
# 3. CLUSTER RESTART FUNCTIONS
# ============================================

def get_cluster_state(cluster_id: str) -> str:
    """Get current state of a Databricks cluster"""
    config = get_cluster_config(cluster_id)
    if config:
        return config.get("state", "UNKNOWN")
    return "UNKNOWN"


def restart_cluster(cluster_id: str) -> Tuple[bool, str]:
    """
    Restart a Databricks cluster
    
    Returns:
        (success, message)
    """
    if not AUTO_RESTART_ENABLED:
        return False, "Auto-restart is disabled"
    
    if not DATABRICKS_HOST or not DATABRICKS_TOKEN:
        return False, "Databricks credentials not configured"
    
    logger.info(f"🔄 Attempting to restart cluster {cluster_id}...")
    
    # Check current state
    current_state = get_cluster_state(cluster_id)
    logger.info(f"Current cluster state: {current_state}")
    
    # If already running, no need to restart
    if current_state == "RUNNING":
        return False, "Cluster is already running"
    
    # If pending, wait for it
    if current_state == "PENDING":
        return False, "Cluster is already starting"
    
    # Restart the cluster
    url = f"{DATABRICKS_HOST}/api/2.0/clusters/start"
    headers = _get_headers()
    payload = {"cluster_id": cluster_id}
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        
        if response.status_code == 200:
            logger.info(f"✅ Successfully initiated cluster restart")
            
            # Wait for cluster to start (with timeout)
            timeout = RESTART_TIMEOUT_MINUTES * 60  # Convert to seconds
            start_time = time.time()
            
            while (time.time() - start_time) < timeout:
                time.sleep(10)  # Check every 10 seconds
                state = get_cluster_state(cluster_id)
                
                logger.info(f"Cluster state: {state}")
                
                if state == "RUNNING":
                    elapsed = int(time.time() - start_time)
                    logger.info(f"✅ Cluster started successfully in {elapsed} seconds")
                    return True, f"Cluster restarted successfully in {elapsed} seconds"
                elif state == "ERROR":
                    return False, "Cluster failed to start (ERROR state)"
                elif state == "TERMINATING":
                    return False, "Cluster is terminating"
            
            return False, f"Cluster restart timeout after {RESTART_TIMEOUT_MINUTES} minutes"
        else:
            error_msg = f"Failed to restart cluster. Status: {response.status_code}, Response: {response.text}"
            logger.error(f"❌ {error_msg}")
            return False, error_msg
            
    except Exception as e:
        error_msg = f"Exception during cluster restart: {str(e)}"
        logger.error(f"❌ {error_msg}")
        return False, error_msg


# ============================================
# 4. LIBRARY VERSION FALLBACK
# ============================================

def parse_library_spec(library_spec: str) -> Tuple[str, Optional[str]]:
    """
    Parse library specification to get name and version
    
    Examples:
        "pandas==2.2.0" -> ("pandas", "2.2.0")
        "pandas>=2.0.0" -> ("pandas", None)
        "pandas" -> ("pandas", None)
    """
    for operator in ["==", ">=", "<=", ">", "<", "~="]:
        if operator in library_spec:
            parts = library_spec.split(operator)
            return parts[0].strip(), parts[1].strip() if len(parts) > 1 else None
    
    return library_spec.strip(), None


def install_library_on_cluster(
    cluster_id: str, 
    library_name: str, 
    version: Optional[str] = None
) -> Tuple[bool, str]:
    """
    Install a library on a Databricks cluster
    
    Returns:
        (success, message)
    """
    if not DATABRICKS_HOST or not DATABRICKS_TOKEN:
        return False, "Databricks credentials not configured"
    
    package_spec = f"{library_name}=={version}" if version else library_name
    logger.info(f"📦 Installing library {package_spec} on cluster {cluster_id}...")
    
    url = f"{DATABRICKS_HOST}/api/2.0/libraries/install"
    headers = _get_headers()
    payload = {
        "cluster_id": cluster_id,
        "libraries": [
            {"pypi": {"package": package_spec}}
        ]
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        
        if response.status_code == 200:
            logger.info(f"✅ Successfully initiated library installation: {package_spec}")
            return True, f"Library {package_spec} installation initiated"
        else:
            error_msg = f"Failed to install library. Status: {response.status_code}, Response: {response.text}"
            logger.error(f"❌ {error_msg}")
            return False, error_msg
            
    except Exception as e:
        error_msg = f"Exception during library installation: {str(e)}"
        logger.error(f"❌ {error_msg}")
        return False, error_msg


def retry_library_with_fallback(
    cluster_id: str, 
    library_spec: str, 
    failed_version: Optional[str] = None
) -> Tuple[bool, Optional[str], str]:
    """
    Retry library installation with fallback versions
    
    Returns:
        (success, installed_version, message)
    """
    library_name, _ = parse_library_spec(library_spec)
    
    fallback_versions = LIBRARY_VERSION_FALLBACKS.get(library_name, [])
    
    if not fallback_versions:
        return False, None, f"No fallback versions configured for {library_name}"
    
    logger.info(f"🔄 Trying fallback versions for {library_name}: {fallback_versions}")
    
    for version in fallback_versions:
        # Skip the version that just failed
        if version == failed_version:
            logger.info(f"⏭️  Skipping failed version: {version}")
            continue
        
        logger.info(f"📦 Attempting to install {library_name}=={version}...")
        
        success, message = install_library_on_cluster(cluster_id, library_name, version)
        
        if success:
            logger.info(f"✅ Successfully installed {library_name}=={version}")
            return True, version, f"Successfully installed {library_name}=={version}"
        else:
            logger.warning(f"❌ Failed to install {library_name}=={version}: {message}")
    
    return False, None, f"All fallback versions failed for {library_name}"


# ============================================
# 5. CONFIGURATION ROLLBACK (BONUS)
# ============================================

def get_cluster_edit_history(cluster_id: str, limit: int = 10) -> List[Dict]:
    """
    Get cluster edit history (Note: This requires Databricks Audit Logs API)
    Simplified version - in production, you'd use audit logs
    """
    # This is a simplified version. In production, you'd query audit logs
    logger.info("⚠️  Configuration rollback requires audit logs API")
    return []


def rollback_cluster_config(cluster_id: str, previous_config: Dict) -> Tuple[bool, str]:
    """
    Rollback cluster to previous configuration
    
    Returns:
        (success, message)
    """
    if not DATABRICKS_HOST or not DATABRICKS_TOKEN:
        return False, "Databricks credentials not configured"
    
    logger.info(f"⏮️  Rolling back cluster {cluster_id} to previous configuration...")
    
    url = f"{DATABRICKS_HOST}/api/2.0/clusters/edit"
    headers = _get_headers()
    
    # Prepare payload with previous config
    payload = {
        "cluster_id": cluster_id,
        **previous_config
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        
        if response.status_code == 200:
            logger.info(f"✅ Successfully rolled back cluster configuration")
            return True, "Cluster configuration rolled back successfully"
        else:
            error_msg = f"Failed to rollback configuration. Status: {response.status_code}, Response: {response.text}"
            logger.error(f"❌ {error_msg}")
            return False, error_msg
            
    except Exception as e:
        error_msg = f"Exception during configuration rollback: {str(e)}"
        logger.error(f"❌ {error_msg}")
        return False, error_msg


# ============================================
# 6. HELPER FUNCTIONS
# ============================================

def get_remediation_strategy(error_type: str) -> Dict:
    """
    Get the appropriate remediation strategy for an error type
    
    Returns:
        Dictionary with remediation details
    """
    strategies = {
        "DatabricksJobExecutionError": {
            "action": "retry",
            "max_retries": 3,
            "backoff_enabled": True,
            "description": "Retry job with exponential backoff"
        },
        "DatabricksClusterStartFailure": {
            "action": "restart",
            "timeout_minutes": 10,
            "description": "Restart cluster"
        },
        "DatabricksResourceExhausted": {
            "action": "scale_up",
            "scale_percentage": 50,
            "description": "Scale up cluster workers"
        },
        "DatabricksLibraryInstallationError": {
            "action": "library_fallback",
            "description": "Try fallback library versions"
        },
        "DatabricksDriverNotResponding": {
            "action": "restart",
            "timeout_minutes": 10,
            "description": "Restart cluster"
        },
        "DatabricksTimeoutError": {
            "action": "retry",
            "max_retries": 2,
            "backoff_enabled": True,
            "description": "Retry with increased timeout"
        },
    }
    
    return strategies.get(error_type, {
        "action": "none",
        "description": "No auto-remediation available"
    })


if __name__ == "__main__":
    # Test the functions
    print("🧪 Testing Databricks Remediation Functions...\n")
    
    # Test 1: Get remediation strategy
    print("Test 1: Get remediation strategy")
    strategy = get_remediation_strategy("DatabricksJobExecutionError")
    print(f"Strategy: {strategy}\n")
    
    # Test 2: Parse library spec
    print("Test 2: Parse library specifications")
    test_specs = ["pandas==2.2.0", "numpy>=1.24.0", "scikit-learn"]
    for spec in test_specs:
        name, version = parse_library_spec(spec)
        print(f"  '{spec}' -> name='{name}', version='{version}'")
    
    print("\n✅ Basic tests completed!")