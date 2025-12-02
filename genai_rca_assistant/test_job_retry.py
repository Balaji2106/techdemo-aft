"""
Test Auto-Remediation: Job Retry
Simulates a Databricks job failure and watches auto-remediation
"""
import requests
import json
import time

# Your FastAPI endpoint
BASE_URL = "http://localhost:8000"

# Test payload: Databricks job failure
payload = {
    "event": "job.run.failed",
    "job": {
        "job_id": "652043121296891",  # Use one of your actual job IDs
        "settings": {
            "name": "Test Auto-Remediation Job"
        }
    },
    "run": {
        "run_id": "test-auto-remediation-" + str(int(time.time())),
        "job_id": "652043121296891",
        "run_name": "Test Auto-Remediation Job",
        "state": {
            "life_cycle_state": "TERMINATED",
            "result_state": "FAILED",
            "state_message": "Task failed with exception: Connection timeout after 30 seconds"
        },
        "cluster_instance": {
            "cluster_id": "1121-055905-q5xcz4bm"
        }
    }
}

def test_job_retry():
    print("=" * 80)
    print("🧪 TEST 1: Job Retry Auto-Remediation")
    print("=" * 80)
    
    print("\n📤 Step 1: Sending Databricks job failure webhook...")
    print(f"   Endpoint: {BASE_URL}/databricks-monitor")
    print(f"   Job ID: {payload['job']['job_id']}")
    print(f"   Run ID: {payload['run']['run_id']}")
    
    try:
        response = requests.post(
            f"{BASE_URL}/databricks-monitor",
            json=payload,
            timeout=30
        )
        
        print(f"\n✅ Response Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            ticket_id = data.get("ticket_id")
            
            print(f"✅ Ticket Created: {ticket_id}")
            print(f"✅ Status: {data.get('status')}")
            
            print("\n⏳ Step 2: Waiting for auto-remediation to trigger...")
            print("   (This may take 30-60 seconds due to backoff delay)")
            
            time.sleep(5)
            
            print("\n📊 Step 3: Check audit trail for auto-remediation events:")
            print(f"   Dashboard: {BASE_URL}/dashboard")
            print(f"   Look for these audit events:")
            print(f"      - 'Auto-Remediation Triggered'")
            print(f"      - 'Auto-Remediation Success' or 'Auto-Remediation Failed'")
            
            print("\n✅ TEST COMPLETED!")
            print(f"\n🔍 To verify:")
            print(f"   1. Open dashboard: {BASE_URL}/dashboard")
            print(f"   2. Go to 'Audit Trail' tab")
            print(f"   3. Look for ticket: {ticket_id}")
            print(f"   4. Check Databricks UI for new job run")
            
        else:
            print(f"❌ Error: {response.status_code}")
            print(f"   Response: {response.text}")
    
    except Exception as e:
        print(f"❌ Exception: {e}")
    
    print("\n" + "=" * 80)

if __name__ == "__main__":
    test_job_retry()