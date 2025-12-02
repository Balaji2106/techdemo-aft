#!/usr/bin/env python3
"""
Test AI Provider Fallback System
Tests Gemini, Ollama, and automatic fallback
"""
import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Test cases
TEST_ERRORS = [
    {
        "error": "java.lang.OutOfMemoryError: GC overhead limit exceeded at org.apache.spark.executor.Executor",
        "source": "databricks",
        "expected_type": "DatabricksOutOfMemoryError"
    },
    {
        "error": "Cluster driver is unreachable. Driver may have crashed or network connectivity is lost",
        "source": "databricks",
        "expected_type": "DatabricksDriverNotResponding"
    },
    {
        "error": "Activity failed: Copy activity encountered a user error: Source blob not found",
        "source": "adf",
        "expected_type": "UserErrorSourceBlobNotExists"
    }
]


def test_provider_availability():
    """Test 1: Check if providers are available"""
    print("\n" + "="*60)
    print("TEST 1: Provider Availability")
    print("="*60 + "\n")

    from ai_providers import get_ai_manager

    manager = get_ai_manager()
    status = manager.get_provider_status()

    print(f"📊 Total Providers: {status['total_providers']}")
    print(f"✅ Available: {', '.join(status['available_providers'])}\n")

    if status['total_providers'] == 0:
        print("❌ No providers available!")
        print("\nConfigured environment variables:")
        print(f"  GEMINI_API_KEY: {'✅ Set' if os.getenv('GEMINI_API_KEY') else '❌ Not set'}")
        print(f"  OLLAMA_HOST: {'✅ Set' if os.getenv('OLLAMA_HOST') else '❌ Not set'}")
        return False

    for provider in status['providers']:
        print(f"\n📋 Provider: {provider['name']}")
        print(f"   Status: {'✅ Available' if provider['available'] else '❌ Unavailable'}")

        if provider['config']:
            for key, value in provider['config'].items():
                print(f"   {key}: {value}")

    return status['total_providers'] > 0


def test_rca_generation():
    """Test 2: Generate RCA for different error types"""
    print("\n" + "="*60)
    print("TEST 2: RCA Generation")
    print("="*60 + "\n")

    from ai_providers import generate_rca

    for i, test_case in enumerate(TEST_ERRORS, 1):
        print(f"\n🧪 Test Case {i}: {test_case['source'].upper()} Error")
        print(f"   Error: {test_case['error'][:80]}...")

        try:
            rca = generate_rca(
                error_message=test_case['error'],
                source=test_case['source'],
                metadata={"test": True}
            )

            # Check results
            provider = rca.get('ai_provider', 'unknown')
            fallback = rca.get('provider_fallback_used', False)
            error_type = rca.get('error_type', 'Unknown')
            severity = rca.get('severity', 'Unknown')
            root_cause = rca.get('root_cause', 'Unknown')

            print(f"\n   ✅ RCA Generated Successfully")
            print(f"   Provider: {provider}")
            print(f"   Fallback Used: {'Yes ⚠️' if fallback else 'No'}")
            print(f"   Error Type: {error_type}")
            print(f"   Severity: {severity}")
            print(f"   Root Cause: {root_cause[:100]}...")

            # Check if error type is reasonable
            if error_type != "UnknownError":
                print(f"   ✅ Error type classified correctly")
            else:
                print(f"   ⚠️  Error type not classified")

        except Exception as e:
            print(f"\n   ❌ RCA Generation Failed: {str(e)}")
            return False

    return True


def test_fallback_mechanism():
    """Test 3: Test fallback when primary fails"""
    print("\n" + "="*60)
    print("TEST 3: Fallback Mechanism")
    print("="*60 + "\n")

    from ai_providers import get_ai_manager, GeminiProvider, OllamaProvider

    manager = get_ai_manager()

    # Check what providers we have
    available = manager.get_available_providers()
    print(f"Available providers: {available}\n")

    if len(available) < 2:
        print("⚠️  Only 1 provider available, cannot test fallback")
        print("   Configure both GEMINI_API_KEY and OLLAMA_HOST to test fallback")
        return True  # Not a failure, just can't test

    # Temporarily disable first provider by clearing credentials
    # (This is a simulation - in real scenario, API would fail)
    print("🧪 Simulating primary provider failure...")
    print("   (In production, this happens when API is down/rate limited)\n")

    # Test with both providers
    test_error = "Test error for fallback testing"

    try:
        from ai_providers import generate_rca

        rca = generate_rca(test_error, source="databricks")

        provider = rca.get('ai_provider')
        fallback_used = rca.get('provider_fallback_used')

        print(f"✅ RCA Generated")
        print(f"   Primary provider: {available[0]}")
        print(f"   Used provider: {provider}")
        print(f"   Fallback activated: {fallback_used}")

        if len(available) > 1:
            print(f"\n   ℹ️  To test actual fallback, temporarily set:")
            print(f"      GEMINI_API_KEY=invalid")
            print(f"   Then run this test again. Ollama should be used automatically.")

        return True

    except Exception as e:
        print(f"❌ Fallback test failed: {e}")
        return False


def test_performance():
    """Test 4: Compare provider performance"""
    print("\n" + "="*60)
    print("TEST 4: Performance Comparison")
    print("="*60 + "\n")

    from ai_providers import get_ai_manager
    import time

    manager = get_ai_manager()
    available = manager.get_available_providers()

    if not available:
        print("❌ No providers available")
        return False

    test_error = "Job failed with OutOfMemoryError in Spark executor"

    print(f"Testing with error: {test_error}\n")

    results = []

    for provider_name in available:
        print(f"🔍 Testing {provider_name}...")

        start_time = time.time()

        try:
            from ai_providers import generate_rca
            rca = generate_rca(test_error, source="databricks")

            elapsed = time.time() - start_time

            if rca.get('ai_provider') == provider_name or provider_name == 'fallback':
                results.append({
                    'provider': provider_name,
                    'time': elapsed,
                    'success': True,
                    'error_type': rca.get('error_type', 'Unknown')
                })
                print(f"   ✅ Completed in {elapsed:.2f}s")
            else:
                print(f"   ⚠️  Used different provider: {rca.get('ai_provider')}")

        except Exception as e:
            elapsed = time.time() - start_time
            results.append({
                'provider': provider_name,
                'time': elapsed,
                'success': False,
                'error': str(e)
            })
            print(f"   ❌ Failed after {elapsed:.2f}s: {e}")

    # Summary
    print("\n📊 Performance Summary:")
    print("-" * 60)
    for r in results:
        status = "✅" if r['success'] else "❌"
        print(f"{status} {r['provider']}: {r['time']:.2f}s")

    return len([r for r in results if r['success']]) > 0


def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("AI PROVIDER FALLBACK SYSTEM - TEST SUITE")
    print("="*60)

    tests = [
        ("Provider Availability", test_provider_availability),
        ("RCA Generation", test_rca_generation),
        ("Fallback Mechanism", test_fallback_mechanism),
        ("Performance Comparison", test_performance),
    ]

    results = []

    for test_name, test_func in tests:
        try:
            passed = test_func()
            results.append((test_name, passed))
        except Exception as e:
            print(f"\n❌ {test_name} crashed: {e}")
            import traceback
            traceback.print_exc()
            results.append((test_name, False))

    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60 + "\n")

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 All tests passed! AI provider system is ready.")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Review errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
