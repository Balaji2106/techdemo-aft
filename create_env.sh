#!/bin/bash
# Quick script to create .env file with correct settings

ENV_FILE="$HOME/Downloads/after-techd/v2/lates/genai_rca_assistant/.env"

echo "🔧 Creating .env file for auto-remediation..."

cat > "$ENV_FILE" << 'EOF'
# ============================================
# GEMINI AI CONFIGURATION
# ============================================
GEMINI_API_KEY=AIzaSyCyHEGlLe1E7acVvqNtOYXYrQuEFqdNhsI
GEMINI_MODEL_ID=models/gemini-2.5-flash

# ============================================
# AUTO-REMEDIATION CONFIGURATION
# ============================================
AUTO_REMEDIATION_ENABLED=true
AUTO_REMEDIATION_MAX_RETRIES=3
RETRY_BASE_DELAY_SECONDS=30
RETRY_MAX_DELAY_SECONDS=300

# Auto-scaling configuration
AUTO_SCALE_ENABLED=true
MAX_CLUSTER_WORKERS=10
SCALE_UP_PERCENTAGE=50

# Auto-restart configuration
AUTO_RESTART_ENABLED=true
RESTART_TIMEOUT_MINUTES=10

# ============================================
# CIRCUIT BREAKER CONFIGURATION
# ============================================
CIRCUIT_BREAKER_FAILURE_THRESHOLD=5
CIRCUIT_BREAKER_TIMEOUT_SECONDS=300
CIRCUIT_BREAKER_ENABLED=true

# ============================================
# HEALTH CHECK CONFIGURATION
# ============================================
HEALTH_CHECK_ENABLED=true
HEALTH_CHECK_TIMEOUT_SECONDS=60
JOB_COMPLETION_TIMEOUT_SECONDS=600

# ============================================
# FEATURE FLAGS
# ============================================
ENABLE_JOB_RETRY=true
ENABLE_CLUSTER_RESTART=true
ENABLE_CLUSTER_SCALING=true
ENABLE_LIBRARY_FALLBACK=true
ENABLE_CONFIG_ROLLBACK=false

# ============================================
# DATABRICKS CONFIGURATION (UPDATE THESE!)
# ============================================
DATABRICKS_HOST=https://adb-your-workspace.azuredatabricks.net
DATABRICKS_TOKEN=dapi-your-token-here

# ============================================
# OTHER SETTINGS
# ============================================
RCA_API_KEY=balaji-rca-secret-2025
DB_TYPE=sqlite
DB_PATH=data/tickets.db
JWT_SECRET_KEY=your-secret-key-change-in-production
LOG_LEVEL=INFO
EOF

echo "✅ Created .env file at: $ENV_FILE"
echo ""
echo "📝 Please update these values in the .env file:"
echo "   - DATABRICKS_HOST (your Databricks workspace URL)"
echo "   - DATABRICKS_TOKEN (your Databricks API token)"
echo ""
echo "🔍 Current settings:"
grep -E "GEMINI_MODEL_ID|AUTO_REMEDIATION_ENABLED" "$ENV_FILE"
