"""
Circuit Breaker Pattern for Auto-Recovery
Prevents infinite retry loops and system overload
"""
import time
import logging
from typing import Dict, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger("circuit_breaker")


class CircuitState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"  # Normal operation, requests allowed
    OPEN = "open"      # Circuit tripped, requests blocked
    HALF_OPEN = "half_open"  # Testing if system recovered


@dataclass
class CircuitBreaker:
    """Circuit breaker for a specific error type or resource"""
    name: str  # Identifier (e.g., "DatabricksJobExecutionError:job-123")
    failure_threshold: int = 5  # Number of failures before opening circuit
    timeout_seconds: int = 300  # Time to wait before attempting half-open
    success_threshold: int = 2  # Successful attempts needed to close circuit from half-open

    # State tracking
    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    success_count: int = 0
    last_failure_time: Optional[float] = None
    last_state_change: Optional[float] = None
    total_failures: int = 0
    total_successes: int = 0

    def __post_init__(self):
        self.last_state_change = time.time()

    def record_success(self) -> None:
        """Record a successful operation"""
        self.success_count += 1
        self.total_successes += 1
        self.failure_count = 0  # Reset failure count on success

        if self.state == CircuitState.HALF_OPEN:
            if self.success_count >= self.success_threshold:
                self._close_circuit()

        logger.info(f"✅ Circuit '{self.name}': Success recorded. Success count: {self.success_count}")

    def record_failure(self) -> None:
        """Record a failed operation"""
        self.failure_count += 1
        self.total_failures += 1
        self.last_failure_time = time.time()
        self.success_count = 0  # Reset success count on failure

        logger.warning(f"❌ Circuit '{self.name}': Failure recorded. Failure count: {self.failure_count}/{self.failure_threshold}")

        if self.state == CircuitState.CLOSED:
            if self.failure_count >= self.failure_threshold:
                self._open_circuit()
        elif self.state == CircuitState.HALF_OPEN:
            # Failed during test, reopen circuit
            self._open_circuit()

    def can_execute(self) -> Tuple[bool, str]:
        """
        Check if operation can be executed

        Returns:
            (can_execute, reason)
        """
        if self.state == CircuitState.CLOSED:
            return True, "Circuit is closed, operation allowed"

        elif self.state == CircuitState.OPEN:
            # Check if timeout has elapsed
            if self.last_state_change:
                elapsed = time.time() - self.last_state_change

                if elapsed >= self.timeout_seconds:
                    self._half_open_circuit()
                    return True, "Circuit entering half-open state, test operation allowed"

            remaining = self.timeout_seconds - elapsed if self.last_state_change else self.timeout_seconds
            return False, f"Circuit is open, retry in {int(remaining)} seconds"

        elif self.state == CircuitState.HALF_OPEN:
            return True, "Circuit is half-open, test operation allowed"

        return False, "Unknown circuit state"

    def _open_circuit(self) -> None:
        """Open the circuit (block operations)"""
        self.state = CircuitState.OPEN
        self.last_state_change = time.time()
        logger.error(f"🔴 Circuit '{self.name}' OPENED after {self.failure_count} failures. Timeout: {self.timeout_seconds}s")

    def _half_open_circuit(self) -> None:
        """Enter half-open state (allow test operations)"""
        self.state = CircuitState.HALF_OPEN
        self.last_state_change = time.time()
        self.failure_count = 0
        self.success_count = 0
        logger.info(f"🟡 Circuit '{self.name}' entered HALF-OPEN state. Testing recovery...")

    def _close_circuit(self) -> None:
        """Close the circuit (normal operation)"""
        self.state = CircuitState.CLOSED
        self.last_state_change = time.time()
        self.failure_count = 0
        self.success_count = 0
        logger.info(f"🟢 Circuit '{self.name}' CLOSED. Normal operation resumed.")

    def reset(self) -> None:
        """Manually reset the circuit breaker"""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_state_change = time.time()
        logger.info(f"🔄 Circuit '{self.name}' manually reset.")

    def get_status(self) -> Dict:
        """Get current circuit breaker status"""
        uptime = time.time() - self.last_state_change if self.last_state_change else 0

        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "failure_threshold": self.failure_threshold,
            "success_count": self.success_count,
            "total_failures": self.total_failures,
            "total_successes": self.total_successes,
            "time_in_current_state": int(uptime),
            "timeout_seconds": self.timeout_seconds,
            "last_failure_time": datetime.fromtimestamp(self.last_failure_time).isoformat() if self.last_failure_time else None,
        }


# ============================================
# CIRCUIT BREAKER MANAGER
# ============================================

class CircuitBreakerManager:
    """Manages multiple circuit breakers"""

    def __init__(self):
        self.circuits: Dict[str, CircuitBreaker] = {}
        self.default_failure_threshold = 5
        self.default_timeout_seconds = 300
        self.default_success_threshold = 2

    def get_or_create_circuit(
        self,
        name: str,
        failure_threshold: Optional[int] = None,
        timeout_seconds: Optional[int] = None,
        success_threshold: Optional[int] = None
    ) -> CircuitBreaker:
        """Get existing circuit or create new one"""

        if name not in self.circuits:
            circuit = CircuitBreaker(
                name=name,
                failure_threshold=failure_threshold or self.default_failure_threshold,
                timeout_seconds=timeout_seconds or self.default_timeout_seconds,
                success_threshold=success_threshold or self.default_success_threshold
            )
            self.circuits[name] = circuit
            logger.info(f"🆕 Created new circuit breaker: {name}")

        return self.circuits[name]

    def record_success(self, name: str) -> None:
        """Record success for a circuit"""
        circuit = self.get_or_create_circuit(name)
        circuit.record_success()

    def record_failure(self, name: str) -> None:
        """Record failure for a circuit"""
        circuit = self.get_or_create_circuit(name)
        circuit.record_failure()

    def can_execute(self, name: str) -> Tuple[bool, str]:
        """Check if operation can be executed"""
        circuit = self.get_or_create_circuit(name)
        return circuit.can_execute()

    def reset_circuit(self, name: str) -> None:
        """Manually reset a circuit"""
        if name in self.circuits:
            self.circuits[name].reset()

    def get_all_circuits_status(self) -> Dict[str, Dict]:
        """Get status of all circuit breakers"""
        return {name: circuit.get_status() for name, circuit in self.circuits.items()}

    def get_open_circuits(self) -> list:
        """Get list of open circuits"""
        return [
            name for name, circuit in self.circuits.items()
            if circuit.state == CircuitState.OPEN
        ]

    def cleanup_old_circuits(self, max_age_hours: int = 24) -> int:
        """Remove old circuits that haven't been used recently"""
        cutoff_time = time.time() - (max_age_hours * 3600)
        removed = 0

        circuits_to_remove = [
            name for name, circuit in self.circuits.items()
            if circuit.last_state_change and circuit.last_state_change < cutoff_time
            and circuit.state == CircuitState.CLOSED
        ]

        for name in circuits_to_remove:
            del self.circuits[name]
            removed += 1
            logger.info(f"🧹 Removed old circuit: {name}")

        return removed


# ============================================
# GLOBAL CIRCUIT BREAKER MANAGER
# ============================================

# Singleton instance
_circuit_manager = CircuitBreakerManager()


def get_circuit_manager() -> CircuitBreakerManager:
    """Get the global circuit breaker manager"""
    return _circuit_manager


def check_circuit(
    error_type: str,
    resource_id: str = "global",
    failure_threshold: int = 5,
    timeout_seconds: int = 300
) -> Tuple[bool, str]:
    """
    Check if recovery can proceed for this error type + resource

    Args:
        error_type: The error type (e.g., "DatabricksJobExecutionError")
        resource_id: Specific resource ID (job ID, cluster ID, etc.) or "global"
        failure_threshold: Number of failures before circuit opens
        timeout_seconds: Time to wait before retry

    Returns:
        (can_proceed, reason)
    """
    circuit_name = f"{error_type}:{resource_id}"
    manager = get_circuit_manager()

    circuit = manager.get_or_create_circuit(
        circuit_name,
        failure_threshold=failure_threshold,
        timeout_seconds=timeout_seconds
    )

    return circuit.can_execute()


def record_recovery_success(error_type: str, resource_id: str = "global") -> None:
    """Record successful recovery"""
    circuit_name = f"{error_type}:{resource_id}"
    manager = get_circuit_manager()
    manager.record_success(circuit_name)


def record_recovery_failure(error_type: str, resource_id: str = "global") -> None:
    """Record failed recovery"""
    circuit_name = f"{error_type}:{resource_id}"
    manager = get_circuit_manager()
    manager.record_failure(circuit_name)


def reset_circuit(error_type: str, resource_id: str = "global") -> None:
    """Manually reset circuit breaker"""
    circuit_name = f"{error_type}:{resource_id}"
    manager = get_circuit_manager()
    manager.reset_circuit(circuit_name)


def get_circuit_status(error_type: str, resource_id: str = "global") -> Dict:
    """Get status of a specific circuit"""
    circuit_name = f"{error_type}:{resource_id}"
    manager = get_circuit_manager()
    circuit = manager.get_or_create_circuit(circuit_name)
    return circuit.get_status()


if __name__ == "__main__":
    # Test circuit breaker
    print("🧪 Testing Circuit Breaker System\n")

    # Test 1: Normal operation
    print("Test 1: Normal operation (circuit closed)")
    can_proceed, reason = check_circuit("TestError", "resource-1")
    print(f"  Can proceed: {can_proceed}, Reason: {reason}\n")

    # Test 2: Record failures until circuit opens
    print("Test 2: Recording failures")
    for i in range(6):
        record_recovery_failure("TestError", "resource-1")
        can_proceed, reason = check_circuit("TestError", "resource-1")
        print(f"  Failure {i+1}: Can proceed: {can_proceed}, Reason: {reason}")

    print("\n" + "="*60 + "\n")

    # Test 3: Try after timeout
    print("Test 3: Circuit status")
    status = get_circuit_status("TestError", "resource-1")
    print(f"  State: {status['state']}")
    print(f"  Failures: {status['failure_count']}/{status['failure_threshold']}")
    print(f"  Timeout: {status['timeout_seconds']}s")

    print("\n✅ Circuit breaker system ready!")
