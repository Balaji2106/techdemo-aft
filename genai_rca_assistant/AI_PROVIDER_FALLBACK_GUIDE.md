# AI Provider Fallback System - Integration Guide

## 🎯 Overview

Your RCA system now supports **multiple AI providers with automatic fallback**:
- **Primary:** Google Gemini API
- **Fallback:** Ollama (self-hosted/local)
- **Last Resort:** Basic fallback RCA

If Gemini fails or is unavailable, the system automatically switches to Ollama, ensuring **zero downtime** for RCA generation.

---

## ✨ Features

✅ **Automatic Fallback:** Gemini fails → Try Ollama → Basic RCA
✅ **Zero Downtime:** Application keeps working even if Gemini is down
✅ **Cost Optimization:** Use free Ollama for development/testing
✅ **Flexibility:** Use local Ollama when internet is unreliable
✅ **Monitoring:** Track which provider is being used

---

## 🚀 Quick Start

### Step 1: Configure Providers

Add to your `.env` file:

```bash
# PRIMARY: Google Gemini (recommended for production)
GEMINI_API_KEY=your-api-key
GEMINI_MODEL_ID=models/gemini-2.0-flash-exp

# FALLBACK: Ollama (self-hosted)
OLLAMA_HOST=http://172.190.86.69:11434
OLLAMA_MODEL=deepseek-r1:latest
OLLAMA_TIMEOUT=120
```

**Note:** You need **at least one** provider configured.

### Step 2: Update main.py

Replace the old RCA generation code with the new AI provider system.

#### OLD CODE (main.py ~line 350-450):

```python
import google.generativeai as genai

def call_ai_for_rca(error_message, source="adf"):
    # ... old Gemini-only code ...
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel(MODEL_ID)
    # ...
```

#### NEW CODE:

```python
# At the top of main.py, add import
from ai_providers import generate_rca, get_ai_manager

def call_ai_for_rca(error_message, source="adf", metadata=None):
    """
    Generate RCA using AI providers with automatic fallback

    Args:
        error_message: The error to analyze
        source: Source system (databricks, adf, etc.)
        metadata: Additional context (optional)

    Returns:
        Dictionary with RCA results
    """
    logger.info(f"🤖 Generating RCA for {source} error...")

    # Use the new AI provider system with automatic fallback
    rca = generate_rca(
        error_message=error_message,
        source=source,
        metadata=metadata or {}
    )

    # Log which provider was used
    provider = rca.get("ai_provider", "unknown")
    fallback_used = rca.get("provider_fallback_used", False)

    if fallback_used:
        logger.warning(f"⚠️  Primary provider failed, used fallback: {provider}")
    else:
        logger.info(f"✅ RCA generated using: {provider}")

    return rca
```

### Step 3: Test the System

```bash
# Test AI provider configuration
python ai_providers.py

# Expected output:
# ✅ Primary AI provider: Gemini
# ✅ Fallback AI provider: Ollama
# 🤖 Total AI providers available: 2
```

---

## 📊 How It Works

### Fallback Flow:

```
┌──────────────────────────────────────────────┐
│ RCA Request: Analyze error message          │
└────────────────┬─────────────────────────────┘
                 │
                 ↓
┌────────────────────────────────────────────────────┐
│ TRY PROVIDER 1: Gemini                             │
│ - Check if API key configured                      │
│ - Call Gemini API                                  │
│ - Parse response                                   │
└────────┬───────────────────────────────────────────┘
         │
         ├─ ✅ Success → Return RCA
         │
         ├─ ❌ Failed (API error, timeout, etc.)
         │
         ↓
┌────────────────────────────────────────────────────┐
│ TRY PROVIDER 2: Ollama                             │
│ - Check if Ollama server reachable                 │
│ - Call Ollama API                                  │
│ - Parse response                                   │
└────────┬───────────────────────────────────────────┘
         │
         ├─ ✅ Success → Return RCA (with fallback flag)
         │
         ├─ ❌ Failed
         │
         ↓
┌────────────────────────────────────────────────────┐
│ LAST RESORT: Basic Fallback RCA                    │
│ - Generate basic RCA from error text               │
│ - Mark as low confidence                           │
│ - Require manual review                            │
└────────────────────────────────────────────────────┘
```

---

## 🔧 Configuration Options

### Provider Priority

Providers are tried in this order:
1. **Gemini** (if `GEMINI_API_KEY` is set)
2. **Ollama** (if `OLLAMA_HOST` is set)
3. **Fallback** (always available)

### Ollama Setup

#### Option A: Use Existing Ollama Server

```bash
# Your Ollama is already running at:
OLLAMA_HOST=http://172.190.86.69:11434
OLLAMA_MODEL=deepseek-r1:latest
```

#### Option B: Install Ollama Locally

```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Pull a model
ollama pull deepseek-r1:latest
# or
ollama pull llama2
ollama pull mistral

# Configure in .env
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=deepseek-r1:latest
```

### Recommended Models for RCA

| Model | Size | Speed | Quality | Use Case |
|-------|------|-------|---------|----------|
| **deepseek-r1:latest** | 14GB | Fast | High | Best overall |
| **llama2** | 7GB | Fast | Good | Quick analysis |
| **mistral** | 7GB | Fast | Good | Balanced |
| **codellama** | 7GB | Fast | Good | Code errors |

---

## 📡 Monitoring & Troubleshooting

### Check Provider Status

Add this endpoint to `main.py`:

```python
@app.get("/api/ai-providers")
async def get_ai_provider_status():
    """Get status of all AI providers"""
    from ai_providers import get_ai_manager

    manager = get_ai_manager()
    return manager.get_provider_status()
```

**Usage:**
```bash
curl http://localhost:8000/api/ai-providers
```

**Response:**
```json
{
  "total_providers": 2,
  "available_providers": ["Gemini", "Ollama"],
  "providers": [
    {
      "name": "Gemini",
      "available": true,
      "config": {"model": "models/gemini-2.0-flash-exp"}
    },
    {
      "name": "Ollama",
      "available": true,
      "config": {
        "host": "http://172.190.86.69:11434",
        "model": "deepseek-r1:latest"
      }
    }
  ]
}
```

### Track Provider Usage

The RCA result includes provider metadata:

```python
rca = generate_rca("Some error", source="databricks")

print(f"Provider used: {rca['ai_provider']}")  # "Gemini" or "Ollama"
print(f"Fallback used: {rca['provider_fallback_used']}")  # True/False
```

### Common Issues

#### Issue 1: Both providers unavailable

**Symptoms:**
```
❌ No AI providers available! Configure GEMINI_API_KEY or OLLAMA_HOST
```

**Solution:**
```bash
# Configure at least one provider in .env
GEMINI_API_KEY=your-key
# OR
OLLAMA_HOST=http://localhost:11434
```

#### Issue 2: Ollama connection refused

**Symptoms:**
```
❌ Ollama: Connection failed: Connection refused
```

**Solution:**
```bash
# Check if Ollama is running
curl http://172.190.86.69:11434/api/tags

# If not running, start it:
ollama serve

# Or check firewall allows port 11434
```

#### Issue 3: Ollama model not found

**Symptoms:**
```
⚠️ Ollama: Model 'deepseek-r1:latest' not found
```

**Solution:**
```bash
# Pull the model
ollama pull deepseek-r1:latest

# List available models
ollama list
```

#### Issue 4: Ollama timeout

**Symptoms:**
```
❌ Ollama: Request timeout after 120s
```

**Solution:**
```bash
# Increase timeout in .env
OLLAMA_TIMEOUT=300  # 5 minutes

# Or use a smaller/faster model
OLLAMA_MODEL=llama2  # Faster than deepseek-r1
```

---

## 🧪 Testing

### Test 1: Check Provider Availability

```python
python ai_providers.py

# Expected output:
# ✅ Primary AI provider: Gemini
# ✅ Fallback AI provider: Ollama
# 🤖 Total AI providers available: 2
```

### Test 2: Generate Test RCA

```python
from ai_providers import generate_rca

rca = generate_rca(
    "Job failed: OutOfMemoryError",
    source="databricks",
    metadata={"job_id": "123"}
)

print(f"Provider: {rca['ai_provider']}")
print(f"Error Type: {rca['error_type']}")
print(f"Root Cause: {rca['root_cause']}")
```

### Test 3: Simulate Gemini Failure

```bash
# Temporarily remove Gemini key
unset GEMINI_API_KEY

# Run RCA generation - should use Ollama
python -c "from ai_providers import generate_rca; print(generate_rca('test error')['ai_provider'])"

# Expected: "Ollama"
```

---

## 📊 Performance Comparison

| Provider | Avg Response Time | Cost | Availability | Quality |
|----------|------------------|------|--------------|---------|
| **Gemini** | 2-5 seconds | $$ (API calls) | 99.9% | Excellent |
| **Ollama (local)** | 5-15 seconds | Free | 100% (if server up) | Very Good |
| **Ollama (remote)** | 10-30 seconds | Free | Depends on network | Very Good |
| **Fallback** | <1 second | Free | 100% | Basic |

---

## 💡 Best Practices

### 1. Use Both Providers

Configure both Gemini and Ollama for maximum reliability:

```bash
# Production setup
GEMINI_API_KEY=your-key      # Primary (fast, high quality)
OLLAMA_HOST=http://...       # Fallback (free, reliable)
```

### 2. Monitor Provider Usage

Track which provider is being used:

```python
# In main.py, log provider usage
if rca.get('provider_fallback_used'):
    log_audit(
        ticket_id=ticket_id,
        action="AI Provider Fallback",
        details=f"Primary provider failed, used: {rca['ai_provider']}"
    )
```

### 3. Set Up Alerts

Alert when fallback is used frequently:

```sql
-- Query: Count fallback usage in last 24h
SELECT COUNT(*)
FROM audit_trail
WHERE action = 'AI Provider Fallback'
  AND timestamp > datetime('now', '-1 day');
```

If count > 10, investigate Gemini API issues.

### 4. Ollama Performance Tuning

For faster Ollama responses:

```bash
# Use smaller models
OLLAMA_MODEL=llama2  # Faster than deepseek-r1

# Use local Ollama instead of remote
OLLAMA_HOST=http://localhost:11434  # vs remote server

# Increase timeout for complex analysis
OLLAMA_TIMEOUT=180
```

---

## 🎯 Use Cases

### Use Case 1: Development/Testing

Use Ollama for free during development:

```bash
# .env.development
GEMINI_API_KEY=  # Not configured
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=llama2
```

**Benefits:**
- No API costs
- Works offline
- Faster iteration

### Use Case 2: Production with Fallback

Use Gemini with Ollama backup:

```bash
# .env.production
GEMINI_API_KEY=your-production-key
OLLAMA_HOST=http://internal-ollama:11434
OLLAMA_MODEL=deepseek-r1:latest
```

**Benefits:**
- Best quality (Gemini)
- Zero downtime (Ollama fallback)
- Cost optimization

### Use Case 3: Air-Gapped Environment

Use Ollama only (no internet):

```bash
# .env.airgap
GEMINI_API_KEY=  # Not available
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=deepseek-r1:latest
```

**Benefits:**
- Works without internet
- Data stays internal
- Full control

---

## 📈 Migration Path

### Step 1: Add Ollama (Keep Gemini)

```bash
# Add Ollama as fallback
OLLAMA_HOST=http://172.190.86.69:11434
OLLAMA_MODEL=deepseek-r1:latest

# Keep Gemini as primary
GEMINI_API_KEY=your-existing-key
```

**Test for 1 week, monitor fallback usage.**

### Step 2: Evaluate Performance

```sql
-- Check how often Ollama is used
SELECT
  COUNT(*) FILTER (WHERE details LIKE '%Gemini%') as gemini_count,
  COUNT(*) FILTER (WHERE details LIKE '%Ollama%') as ollama_count
FROM audit_trail
WHERE action = 'Ticket Created'
  AND timestamp > datetime('now', '-7 days');
```

### Step 3: Optimize (Optional)

If Gemini rarely fails, keep as-is.
If Gemini often fails, consider:
- Using Ollama as primary
- Investigating Gemini API issues
- Adding more fallback providers

---

## ✅ Summary

You now have:

✅ **Automatic AI provider fallback**
✅ **Zero downtime for RCA generation**
✅ **Support for Gemini + Ollama**
✅ **Cost optimization options**
✅ **Monitoring & troubleshooting tools**

**Configuration:**
```bash
# Primary
GEMINI_API_KEY=your-key

# Fallback
OLLAMA_HOST=http://172.190.86.69:11434
OLLAMA_MODEL=deepseek-r1:latest
```

**Usage:**
```python
from ai_providers import generate_rca

rca = generate_rca("error message", source="databricks")
# Automatically tries Gemini → Ollama → Fallback
```

**No changes needed to your existing code - just swap out the import!** 🎉
