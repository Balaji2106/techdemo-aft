"""
AI Provider Abstraction Layer with Fallback Support
Supports multiple AI providers (Gemini, Ollama) with automatic fallback
"""
import os
import json
import logging
import requests
from typing import Dict, Optional, Tuple, List
from abc import ABC, abstractmethod

logger = logging.getLogger("ai_providers")


# ============================================
# BASE AI PROVIDER CLASS
# ============================================

class AIProvider(ABC):
    """Base class for AI providers"""

    def __init__(self, name: str):
        self.name = name
        self.is_available = False

    @abstractmethod
    def generate_rca(
        self,
        error_message: str,
        source: str,
        metadata: Dict
    ) -> Tuple[bool, Optional[Dict], str]:
        """
        Generate RCA using this provider

        Args:
            error_message: The error message to analyze
            source: Source system (databricks, adf, etc.)
            metadata: Additional context

        Returns:
            (success, rca_dict, error_message)
        """
        pass

    @abstractmethod
    def check_availability(self) -> bool:
        """Check if this provider is available"""
        pass


# ============================================
# GEMINI PROVIDER
# ============================================

class GeminiProvider(AIProvider):
    """Google Gemini AI provider"""

    def __init__(self):
        super().__init__("Gemini")
        self.api_key = os.getenv("GEMINI_API_KEY", "")
        self.model_id = os.getenv("GEMINI_MODEL_ID", "models/gemini-2.0-flash-exp")
        self.is_available = self.check_availability()

    def check_availability(self) -> bool:
        """Check if Gemini is available"""
        if not self.api_key:
            logger.warning(f"❌ {self.name}: API key not configured")
            return False

        try:
            import google.generativeai as genai
            genai.configure(api_key=self.api_key)
            logger.info(f"✅ {self.name}: Available (model={self.model_id})")
            return True
        except ImportError:
            logger.error(f"❌ {self.name}: google-generativeai not installed")
            return False
        except Exception as e:
            logger.error(f"❌ {self.name}: Configuration failed: {e}")
            return False

    def generate_rca(
        self,
        error_message: str,
        source: str,
        metadata: Dict
    ) -> Tuple[bool, Optional[Dict], str]:
        """Generate RCA using Gemini"""

        if not self.is_available:
            return False, None, f"{self.name} is not available"

        try:
            import google.generativeai as genai

            logger.info(f"🤖 Using {self.name} for RCA generation...")

            # Build prompt
            prompt = self._build_prompt(error_message, source, metadata)

            # Call Gemini API
            model = genai.GenerativeModel(self.model_id)
            response = model.generate_content(prompt)

            # Parse response
            rca_dict = self._parse_response(response.text)

            if rca_dict:
                logger.info(f"✅ {self.name}: RCA generated successfully")
                return True, rca_dict, ""
            else:
                return False, None, f"{self.name}: Failed to parse response"

        except Exception as e:
            error_msg = f"{self.name} error: {str(e)}"
            logger.error(f"❌ {error_msg}")
            return False, None, error_msg

    def _build_prompt(self, error_message: str, source: str, metadata: Dict) -> str:
        """Build prompt for Gemini"""

        # Error type lists based on source
        if source.lower() == "databricks":
            error_types = [
                "DatabricksJobExecutionError", "DatabricksClusterStartFailure",
                "DatabricksResourceExhausted", "DatabricksLibraryInstallationError",
                "DatabricksPermissionDenied", "DatabricksDriverNotResponding",
                "DatabricksTimeoutError", "DatabricksConfigurationError",
                "DatabricksNetworkError", "DatabricksOutOfMemoryError",
                "DatabricksClusterTerminated", "DatabricksStorageError"
            ]
        else:  # ADF
            error_types = [
                "UserErrorSourceBlobNotExists", "GatewayTimeout",
                "HttpConnectionFailed", "InternalServerError",
                "ActivityThrottlingError", "InvalidTemplate",
                "ResourceNotFound", "AuthorizationFailed"
            ]

        prompt = f"""Analyze this {source.upper()} error and return ONLY a JSON object. NO explanations, NO markdown, NO text - ONLY the JSON object.

ERROR: {error_message}

METADATA: {json.dumps(metadata, indent=2)}

Return THIS EXACT JSON structure (fill in the values):
{{
  "root_cause": "Brief explanation why this failed",
  "error_type": "MUST be one of: {', '.join(error_types)}",
  "severity": "Critical|High|Medium|Low",
  "priority": "P1|P2|P3|P4",
  "confidence": "High|Medium|Low",
  "recommendations": ["action 1", "action 2", "action 3"],
  "auto_heal_possible": true,
  "affected_entity": "resource name"
}}

CRITICAL: Set "auto_heal_possible" to TRUE for:
- Timeouts, network errors, driver unresponsive, cluster failures, resource exhaustion (OOM/CPU/disk), connectivity issues, job execution failures

Set to FALSE ONLY for:
- Code bugs, permission errors, missing config

YOUR RESPONSE MUST START WITH {{ and END WITH }}. Nothing else.

        return prompt

    def _parse_response(self, response_text: str) -> Optional[Dict]:
        """Parse Gemini response - try hard to extract JSON"""
        try:
            response_text = response_text.strip()

            # Remove markdown code blocks if present
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.startswith("```"):
                response_text = response_text[3:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]

            response_text = response_text.strip()

            # Try direct JSON parse first
            try:
                rca_dict = json.loads(response_text)
            except json.JSONDecodeError:
                # If that fails, try to extract JSON from text
                # Find first { and last }
                start = response_text.find("{")
                end = response_text.rfind("}") + 1

                if start != -1 and end > start:
                    json_str = response_text[start:end]
                    rca_dict = json.loads(json_str)
                else:
                    logger.error("Could not find JSON object in response")
                    logger.debug(f"Response: {response_text[:500]}")
                    return None

            # Validate required fields
            required_fields = ["root_cause", "error_type", "severity", "recommendations"]
            for field in required_fields:
                if field not in rca_dict:
                    logger.warning(f"Missing field in RCA: {field}")
                    return None

            return rca_dict

        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error: {e}")
            logger.debug(f"Response text: {response_text[:500]}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error parsing response: {e}")
            return None


# ============================================
# OLLAMA PROVIDER
# ============================================

class OllamaProvider(AIProvider):
    """Ollama (local/self-hosted) AI provider"""

    def __init__(self):
        super().__init__("Ollama")
        self.host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
        self.model = os.getenv("OLLAMA_MODEL", "deepseek-r1:latest")
        self.timeout = int(os.getenv("OLLAMA_TIMEOUT", "120"))
        self.is_available = self.check_availability()

    def check_availability(self) -> bool:
        """Check if Ollama is available"""
        if not self.host:
            logger.warning(f"❌ {self.name}: Host not configured")
            return False

        try:
            # Try to ping Ollama API
            response = requests.get(f"{self.host}/api/tags", timeout=5)

            if response.status_code == 200:
                models = response.json().get("models", [])
                model_names = [m.get("name") for m in models]

                if self.model in model_names:
                    logger.info(f"✅ {self.name}: Available (host={self.host}, model={self.model})")
                    return True
                else:
                    logger.warning(f"⚠️  {self.name}: Model '{self.model}' not found. Available: {model_names}")
                    return False
            else:
                logger.warning(f"❌ {self.name}: Server responded with {response.status_code}")
                return False

        except requests.exceptions.RequestException as e:
            logger.warning(f"❌ {self.name}: Connection failed: {e}")
            return False

    def generate_rca(
        self,
        error_message: str,
        source: str,
        metadata: Dict
    ) -> Tuple[bool, Optional[Dict], str]:
        """Generate RCA using Ollama"""

        if not self.is_available:
            return False, None, f"{self.name} is not available"

        try:
            logger.info(f"🤖 Using {self.name} for RCA generation...")

            # Build prompt
            prompt = self._build_prompt(error_message, source, metadata)

            # Call Ollama API
            url = f"{self.host}/api/generate"
            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "format": "json"  # Request JSON output
            }

            response = requests.post(url, json=payload, timeout=self.timeout)

            if response.status_code != 200:
                return False, None, f"{self.name}: API returned {response.status_code}"

            result = response.json()
            generated_text = result.get("response", "")

            # Parse response
            rca_dict = self._parse_response(generated_text)

            if rca_dict:
                logger.info(f"✅ {self.name}: RCA generated successfully")
                return True, rca_dict, ""
            else:
                return False, None, f"{self.name}: Failed to parse response"

        except requests.exceptions.Timeout:
            error_msg = f"{self.name}: Request timeout after {self.timeout}s"
            logger.error(f"❌ {error_msg}")
            return False, None, error_msg
        except Exception as e:
            error_msg = f"{self.name} error: {str(e)}"
            logger.error(f"❌ {error_msg}")
            return False, None, error_msg

    def _build_prompt(self, error_message: str, source: str, metadata: Dict) -> str:
        """Build prompt for Ollama (same as Gemini for consistency)"""

        # Use same prompt structure as Gemini for consistency
        if source.lower() == "databricks":
            error_types = [
                "DatabricksJobExecutionError", "DatabricksClusterStartFailure",
                "DatabricksResourceExhausted", "DatabricksLibraryInstallationError",
                "DatabricksPermissionDenied", "DatabricksDriverNotResponding",
                "DatabricksTimeoutError", "DatabricksConfigurationError",
                "DatabricksNetworkError", "DatabricksOutOfMemoryError",
                "DatabricksClusterTerminated", "DatabricksStorageError"
            ]
        else:  # ADF
            error_types = [
                "UserErrorSourceBlobNotExists", "GatewayTimeout",
                "HttpConnectionFailed", "InternalServerError",
                "ActivityThrottlingError", "InvalidTemplate",
                "ResourceNotFound", "AuthorizationFailed"
            ]

        prompt = f"""Analyze this {source.upper()} failure and provide Root Cause Analysis in JSON format.

ERROR: {error_message}

METADATA: {json.dumps(metadata, indent=2)}

Respond with valid JSON only (no markdown):
{{
  "root_cause": "Why this failed",
  "error_type": "Choose from: {', '.join(error_types[:5])}...",
  "severity": "Critical|High|Medium|Low",
  "priority": "P1|P2|P3|P4",
  "confidence": "High|Medium|Low",
  "recommendations": ["action1", "action2", "action3"],
  "auto_heal_possible": true|false,
  "affected_entity": "resource name"
}}

IMPORTANT: Set "auto_heal_possible" to TRUE for:
- Infrastructure/transient issues (timeouts, network, driver unresponsive, cluster failures)
- Resource exhaustion (OOM, CPU, disk)
- Temporary connectivity issues
- Job execution failures (NOT code bugs)

Set FALSE only for: code bugs, permissions, or config issues requiring manual fix."""

        return prompt

    def _parse_response(self, response_text: str) -> Optional[Dict]:
        """Parse Ollama response"""
        try:
            # Ollama with format=json should return clean JSON
            # But some models might still wrap it
            response_text = response_text.strip()

            # Remove common wrappers
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.startswith("```"):
                response_text = response_text[3:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]

            # Try to find JSON object
            start = response_text.find("{")
            end = response_text.rfind("}") + 1

            if start != -1 and end > start:
                response_text = response_text[start:end]

            rca_dict = json.loads(response_text.strip())

            # Validate and set defaults for missing fields
            defaults = {
                "root_cause": "Unknown",
                "error_type": "UnknownError",
                "severity": "Medium",
                "priority": "P3",
                "confidence": "Medium",
                "recommendations": [],
                "auto_heal_possible": False,
                "affected_entity": "Unknown"
            }

            for key, default_value in defaults.items():
                if key not in rca_dict:
                    logger.warning(f"Missing field '{key}', using default: {default_value}")
                    rca_dict[key] = default_value

            return rca_dict

        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error: {e}")
            logger.debug(f"Response text: {response_text[:500]}")
            return None


# ============================================
# AI PROVIDER MANAGER WITH FALLBACK
# ============================================

class AIProviderManager:
    """Manages multiple AI providers with fallback support"""

    def __init__(self):
        self.providers: List[AIProvider] = []
        self._initialize_providers()

    def _initialize_providers(self):
        """Initialize all configured providers"""

        # Primary provider: Gemini (if configured)
        if os.getenv("GEMINI_API_KEY"):
            gemini = GeminiProvider()
            if gemini.is_available:
                self.providers.append(gemini)
                logger.info("✅ Primary AI provider: Gemini")

        # Fallback provider: Ollama (if configured)
        if os.getenv("OLLAMA_HOST"):
            ollama = OllamaProvider()
            if ollama.is_available:
                self.providers.append(ollama)
                logger.info(f"✅ Fallback AI provider: Ollama")

        if not self.providers:
            logger.error("❌ No AI providers available! Configure GEMINI_API_KEY or OLLAMA_HOST")
        else:
            logger.info(f"🤖 Total AI providers available: {len(self.providers)}")

    def generate_rca_with_fallback(
        self,
        error_message: str,
        source: str = "databricks",
        metadata: Optional[Dict] = None
    ) -> Dict:
        """
        Generate RCA with automatic fallback to next provider if primary fails

        Args:
            error_message: The error to analyze
            source: Source system (databricks, adf, etc.)
            metadata: Additional context

        Returns:
            RCA dictionary with results and provider info
        """

        if metadata is None:
            metadata = {}

        if not self.providers:
            logger.error("❌ No AI providers available!")
            return self._create_fallback_rca(error_message, "No AI providers configured")

        # Try each provider in order until one succeeds
        for i, provider in enumerate(self.providers):
            provider_num = i + 1
            total_providers = len(self.providers)

            logger.info(f"🔄 Trying provider {provider_num}/{total_providers}: {provider.name}")

            success, rca_dict, error = provider.generate_rca(error_message, source, metadata)

            if success and rca_dict:
                # Add provider metadata
                rca_dict["ai_provider"] = provider.name
                rca_dict["provider_fallback_used"] = i > 0

                logger.info(f"✅ RCA generated successfully using {provider.name}")
                return rca_dict
            else:
                logger.warning(f"⚠️  {provider.name} failed: {error}")

                # If this is not the last provider, try next one
                if i < len(self.providers) - 1:
                    logger.info(f"🔄 Falling back to next provider...")

        # All providers failed
        logger.error("❌ All AI providers failed!")
        return self._create_fallback_rca(error_message, "All AI providers failed")

    def _create_fallback_rca(self, error_message: str, reason: str) -> Dict:
        """Create a basic RCA when all providers fail"""
        return {
            "root_cause": f"RCA generation failed: {reason}. Error: {error_message[:200]}",
            "error_type": "UnknownError",
            "severity": "High",
            "priority": "P2",
            "confidence": "Low",
            "recommendations": [
                "Check AI provider configuration",
                "Review error logs",
                "Manual investigation required"
            ],
            "auto_heal_possible": False,
            "affected_entity": "Unknown",
            "ai_provider": "fallback",
            "provider_fallback_used": True
        }

    def get_available_providers(self) -> List[str]:
        """Get list of available provider names"""
        return [p.name for p in self.providers]

    def get_provider_status(self) -> Dict:
        """Get status of all providers"""
        return {
            "total_providers": len(self.providers),
            "available_providers": self.get_available_providers(),
            "providers": [
                {
                    "name": p.name,
                    "available": p.is_available,
                    "config": {
                        "Gemini": {"model": p.model_id} if isinstance(p, GeminiProvider) else None,
                        "Ollama": {"host": p.host, "model": p.model} if isinstance(p, OllamaProvider) else None
                    }.get(p.name)
                }
                for p in self.providers
            ]
        }


# ============================================
# GLOBAL INSTANCE
# ============================================

_ai_manager = None

def get_ai_manager() -> AIProviderManager:
    """Get or create global AI provider manager"""
    global _ai_manager
    if _ai_manager is None:
        _ai_manager = AIProviderManager()
    return _ai_manager


# ============================================
# CONVENIENCE FUNCTION
# ============================================

def generate_rca(error_message: str, source: str = "databricks", metadata: Optional[Dict] = None) -> Dict:
    """
    Convenience function to generate RCA with automatic fallback

    Usage:
        rca = generate_rca("Job failed with OOM error", source="databricks")
    """
    manager = get_ai_manager()
    return manager.generate_rca_with_fallback(error_message, source, metadata)


# ============================================
# TESTING
# ============================================

if __name__ == "__main__":
    print("🧪 Testing AI Provider System\n")

    # Initialize manager
    manager = get_ai_manager()

    # Show provider status
    status = manager.get_provider_status()
    print(f"📊 Provider Status:")
    print(f"   Total providers: {status['total_providers']}")
    print(f"   Available: {', '.join(status['available_providers'])}")
    print()

    # Test RCA generation
    if status['total_providers'] > 0:
        print("🤖 Testing RCA generation...\n")

        test_error = "Job failed: java.lang.OutOfMemoryError: GC overhead limit exceeded"
        rca = generate_rca(test_error, source="databricks", metadata={"job_id": "123"})

        print("📋 RCA Result:")
        print(f"   Provider: {rca.get('ai_provider', 'Unknown')}")
        print(f"   Fallback used: {rca.get('provider_fallback_used', False)}")
        print(f"   Error type: {rca.get('error_type', 'N/A')}")
        print(f"   Severity: {rca.get('severity', 'N/A')}")
        print(f"   Root cause: {rca.get('root_cause', 'N/A')[:100]}...")
        print()
    else:
        print("⚠️  No providers available. Configure GEMINI_API_KEY or OLLAMA_HOST")

    print("✅ Test complete!")
