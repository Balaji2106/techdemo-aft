#!/usr/bin/env python3
"""
Quick diagnostic to check if AI is returning auto_heal_possible=true
"""
import sqlite3
import json
import sys

# Database path
DB_PATH = "data/tickets.db"

def check_run(run_id):
    """Check what AI decided for a specific run_id"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, run_id, error_type, status, rca_result
            FROM tickets
            WHERE run_id = ?
        """, (run_id,))

        row = cursor.fetchone()
        if not row:
            print(f"❌ No ticket found for run_id: {run_id}")
            return

        ticket_id, run_id, error_type, status, rca_result = row

        print("="*80)
        print(f"🎫 Ticket ID: {ticket_id}")
        print(f"📋 Run ID: {run_id}")
        print(f"🔴 Error Type: {error_type}")
        print(f"📊 Status: {status}")
        print("="*80)

        # Parse RCA to check auto_heal_possible
        try:
            rca_json = json.loads(rca_result)
            auto_heal = rca_json.get('auto_heal_possible', False)

            print(f"\n🔍 AI Analysis:")
            print(f"   Root Cause: {rca_json.get('root_cause', 'N/A')[:200]}...")
            print(f"   Severity: {rca_json.get('severity', 'N/A')}")
            print(f"   Priority: {rca_json.get('priority', 'N/A')}")
            print(f"\n{'✅' if auto_heal else '❌'} AUTO_HEAL_POSSIBLE: {auto_heal}")

            if auto_heal:
                print("\n🎉 SUCCESS! AI marked this as AUTO-HEALABLE!")
                print(f"   This should trigger auto-remediation for error type: {error_type}")
            else:
                print("\n⚠️  AI marked this as NOT auto-healable")
                print("   Reasons could be:")
                print("   - AI thinks it's a code bug")
                print("   - AI thinks it requires manual intervention")
                print("   - AI prompt needs more specific guidance")

        except json.JSONDecodeError:
            print(f"\n⚠️  RCA is not valid JSON:")
            print(rca_result[:500])

        conn.close()

    except Exception as e:
        print(f"❌ Error: {e}")

def check_latest():
    """Check the latest ticket"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, run_id, error_type, status, timestamp
            FROM tickets
            ORDER BY timestamp DESC
            LIMIT 5
        """)

        rows = cursor.fetchall()
        print("\n📊 Latest 5 Tickets:")
        print("="*80)
        for row in rows:
            ticket_id, run_id, error_type, status, timestamp = row
            print(f"{timestamp} | {ticket_id} | {error_type} | Status: {status}")
        print("="*80)

        if rows:
            latest_run_id = rows[0][1]
            print(f"\n🔍 Checking latest ticket (run_id: {latest_run_id})...")
            check_run(latest_run_id)

        conn.close()

    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Check specific run_id
        run_id = sys.argv[1]
        check_run(run_id)
    else:
        # Check latest
        check_latest()
