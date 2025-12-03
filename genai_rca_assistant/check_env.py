#!/usr/bin/env python3
"""
Check .env configuration for AI providers
"""
import os
from dotenv import load_dotenv

load_dotenv()

print("🔍 Checking .env Configuration")
print("="*80)

# Check Gemini
gemini_key = os.getenv("GEMINI_API_KEY", "")
gemini_model = os.getenv("GEMINI_MODEL_ID", "")

print(f"\n📦 Gemini Configuration:")
if gemini_key:
    print(f"   ✅ GEMINI_API_KEY: {gemini_key[:20]}...{gemini_key[-10:] if len(gemini_key) > 30 else ''}")
else:
    print(f"   ❌ GEMINI_API_KEY: NOT SET")

if gemini_model:
    print(f"   ✅ GEMINI_MODEL_ID: {gemini_model}")
else:
    print(f"   ⚠️  GEMINI_MODEL_ID: NOT SET (will use default)")

# Check Ollama
ollama_host = os.getenv("OLLAMA_HOST", "")
ollama_model = os.getenv("OLLAMA_MODEL", "")

print(f"\n🦙 Ollama Configuration:")
if ollama_host:
    print(f"   ✅ OLLAMA_HOST: {ollama_host}")
else:
    print(f"   ⚠️  OLLAMA_HOST: NOT SET")

if ollama_model:
    print(f"   ✅ OLLAMA_MODEL: {ollama_model}")
else:
    print(f"   ⚠️  OLLAMA_MODEL: NOT SET")

# Check auto-remediation
auto_rem = os.getenv("AUTO_REMEDIATION_ENABLED", "false")
print(f"\n⚙️  Auto-Remediation:")
print(f"   AUTO_REMEDIATION_ENABLED: {auto_rem}")

print("\n" + "="*80)

if not gemini_key and not ollama_host:
    print("❌ CRITICAL: No AI provider configured!")
    print("   You need at least one of:")
    print("   - GEMINI_API_KEY")
    print("   - OLLAMA_HOST")
elif not gemini_key:
    print("⚠️  Only Ollama configured (Gemini not available)")
elif not ollama_host:
    print("⚠️  Only Gemini configured (Ollama not available as fallback)")
else:
    print("✅ Both providers configured!")
