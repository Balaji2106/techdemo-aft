"""
Verify auto-remediation code is in main.py
"""
import os

def verify_integration():
    print("🔍 Verifying Auto-Remediation Integration\n")
    print("=" * 60)
    
    # Check if databricks_remediation.py exists
    print("\n1️⃣ Checking databricks_remediation.py...")
    if os.path.exists("databricks_remediation.py"):
        print("   ✅ databricks_remediation.py exists")
    else:
        print("   ❌ databricks_remediation.py NOT FOUND")
        return False
    
    # Check main.py for required code
    print("\n2️⃣ Checking main.py for auto-remediation code...")
    
    with open("main.py", "r") as f:
        content = f.read()
    
    checks = {
        "Import statement": "from databricks_remediation import",
        "Orchestrator function": "async def attempt_databricks_auto_remediation",
        "Auto-remediation call": "await attempt_databricks_auto_remediation"
    }
    
    all_good = True
    for name, code_snippet in checks.items():
        if code_snippet in content:
            print(f"   ✅ {name} found")
        else:
            print(f"   ❌ {name} NOT FOUND")
            all_good = False
    
    print("\n" + "=" * 60)
    
    if all_good:
        print("✅ All auto-remediation code is in place!")
        print("\n🚀 Next steps:")
        print("   1. Restart FastAPI: uvicorn main:app --reload")
        print("   2. Run test: python test_job_retry.py")
    else:
        print("❌ Some auto-remediation code is missing!")
        print("\n📝 Please add the missing code sections above")
    
    return all_good

if __name__ == "__main__":
    verify_integration()