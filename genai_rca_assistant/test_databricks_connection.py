import os
import requests
from dotenv import load_dotenv

load_dotenv()

DATABRICKS_HOST = os.getenv("DATABRICKS_HOST", "").rstrip('/')
DATABRICKS_TOKEN = os.getenv("DATABRICKS_TOKEN", "")

def test_connection():
    """Test Databricks API connection"""
    if not DATABRICKS_HOST or not DATABRICKS_TOKEN:
        print("❌ ERROR: DATABRICKS_HOST or DATABRICKS_TOKEN not set in .env")
        return False
    
    # Test 1: List clusters
    print("\n🔍 Test 1: Listing clusters...")
    url = f"{DATABRICKS_HOST}/api/2.0/clusters/list"
    headers = {
        "Authorization": f"Bearer {DATABRICKS_TOKEN}",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            clusters = response.json().get("clusters", [])
            print(f"✅ SUCCESS: Found {len(clusters)} cluster(s)")
            for cluster in clusters:
                print(f"   - {cluster.get('cluster_name')} (ID: {cluster.get('cluster_id')})")
        else:
            print(f"❌ FAILED: Status {response.status_code}, Response: {response.text}")
            return False
    except Exception as e:
        print(f"❌ EXCEPTION: {e}")
        return False
    
    # Test 2: List jobs
    print("\n🔍 Test 2: Listing jobs...")
    url = f"{DATABRICKS_HOST}/api/2.1/jobs/list"
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            jobs = response.json().get("jobs", [])
            print(f"✅ SUCCESS: Found {len(jobs)} job(s)")
            for job in jobs[:5]:  # Show first 5
                settings = job.get("settings", {})
                print(f"   - {settings.get('name')} (ID: {job.get('job_id')})")
        else:
            print(f"❌ FAILED: Status {response.status_code}, Response: {response.text}")
            return False
    except Exception as e:
        print(f"❌ EXCEPTION: {e}")
        return False
    
    print("\n✅ All tests passed! Databricks connection is working.\n")
    return True

if __name__ == "__main__":
    test_connection()