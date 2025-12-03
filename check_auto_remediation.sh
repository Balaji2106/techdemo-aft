#!/bin/bash
# Quick script to check if auto-remediation is working

echo "🔍 Checking Auto-Remediation Status"
echo "===================================="

RUN_ID="110784941568888"
LOG_DIR="$HOME/Downloads/after-techd/v2/lates/genai_rca_assistant"

echo ""
echo "1️⃣ Checking if AUTO_REMEDIATION_ENABLED..."
cd "$LOG_DIR"
if [ -f .env ]; then
    AUTO_REM=$(grep "AUTO_REMEDIATION_ENABLED" .env | cut -d '=' -f2)
    echo "   AUTO_REMEDIATION_ENABLED=$AUTO_REM"
else
    echo "   ⚠️  No .env file found"
fi

echo ""
echo "2️⃣ Checking database for run $RUN_ID..."
if [ -f data/tickets.db ]; then
    sqlite3 data/tickets.db <<EOF
.mode column
.headers on
SELECT
    run_id,
    error_type,
    status,
    logic_app_run_id,
    substr(rca_result, 1, 50) as rca_snippet
FROM tickets
WHERE run_id = '$RUN_ID';
EOF
else
    echo "   ⚠️  Database not found"
fi

echo ""
echo "3️⃣ Searching logs for auto-remediation keywords..."
# Find log files
LOG_FILES=$(find . -name "*.log" -o -name "uvicorn.log" 2>/dev/null | head -5)

if [ -n "$LOG_FILES" ]; then
    echo "   Searching in: $LOG_FILES"
    echo ""
    grep -h -i "auto.*remediation\|auto_heal_possible\|retry.*job\|playbook" $LOG_FILES 2>/dev/null | tail -20
else
    echo "   ⚠️  No log files found in current directory"
    echo "   Check your terminal output where uvicorn is running"
fi

echo ""
echo "4️⃣ Check Databricks for multiple job runs..."
echo "   Go to: Databricks → Workflows → auto-rem-test → Runs"
echo "   Expected: Multiple runs with different run_ids (if auto-retry worked)"

echo ""
echo "===================================="
echo "✅ Analysis Complete"
