"""
Tests for rate limiting and circuit breaker in rate_limiter.py
"""

import pytest
import time
from rate_limiter import TokenBucket, CircuitBreaker, CircuitState


def test_token_bucket_allows_requests_within_rate():
    """Test TokenBucket allows requests when tokens available."""
    bucket = TokenBucket(rate=10, per=60)  # 10 per minute

    # Should allow 10 requests
    for _ in range(10):
        assert bucket.consume(1) is True


def test_token_bucket_blocks_when_exhausted():
    """Test TokenBucket blocks when no tokens available."""
    bucket = TokenBucket(rate=5, per=60)

    # Consume all tokens
    for _ in range(5):
        bucket.consume(1)

    # Next request should be blocked
    assert bucket.consume(1) is False


def test_token_bucket_refills_over_time():
    """Test TokenBucket refills tokens over time."""
    bucket = TokenBucket(rate=10, per=1)  # 10 per second

    # Consume all tokens
    for _ in range(10):
        bucket.consume(1)

    # Should be blocked immediately
    assert bucket.consume(1) is False

    # Wait for refill (0.2 seconds = 2 tokens)
    time.sleep(0.2)

    # Should allow at least 1 request now
    assert bucket.consume(1) is True


def test_circuit_breaker_starts_closed():
    """Test CircuitBreaker starts in CLOSED state."""
    breaker = CircuitBreaker("test", failure_threshold=3, recovery_timeout=5)
    assert breaker.state == CircuitState.CLOSED


def test_circuit_breaker_opens_after_failures():
    """Test CircuitBreaker opens after threshold failures."""
    breaker = CircuitBreaker("test", failure_threshold=3, recovery_timeout=5)

    # Record failures
    breaker.record_failure()
    assert breaker.state == CircuitState.CLOSED

    breaker.record_failure()
    assert breaker.state == CircuitState.CLOSED

    breaker.record_failure()
    assert breaker.state == CircuitState.OPEN  # Should open after 3rd failure


def test_circuit_breaker_transitions_to_half_open():
    """Test CircuitBreaker transitions to HALF_OPEN after recovery timeout."""
    breaker = CircuitBreaker("test", failure_threshold=2, recovery_timeout=1)

    # Open the circuit
    breaker.record_failure()
    breaker.record_failure()
    assert breaker.state == CircuitState.OPEN

    # Wait for recovery timeout
    time.sleep(1.1)

    # Should transition to HALF_OPEN
    assert breaker.state == CircuitState.HALF_OPEN


def test_circuit_breaker_closes_after_success_in_half_open():
    """Test CircuitBreaker closes after success in HALF_OPEN state."""
    breaker = CircuitBreaker("test", failure_threshold=2, recovery_timeout=1)

    # Open the circuit
    breaker.record_failure()
    breaker.record_failure()
    assert breaker.state == CircuitState.OPEN

    # Wait for recovery
    time.sleep(1.1)
    assert breaker.state == CircuitState.HALF_OPEN

    # Record success
    breaker.record_success()
    assert breaker.state == CircuitState.CLOSED


def test_circuit_breaker_stays_open_on_failure_in_half_open():
    """Test CircuitBreaker returns to OPEN on failure in HALF_OPEN state."""
    breaker = CircuitBreaker("test", failure_threshold=2, recovery_timeout=1)

    # Open the circuit
    breaker.record_failure()
    breaker.record_failure()

    # Wait for recovery
    time.sleep(1.1)
    assert breaker.state == CircuitState.HALF_OPEN

    # Record failure
    breaker.record_failure()
    assert breaker.state == CircuitState.OPEN


def test_circuit_breaker_can_execute_when_closed():
    """Test can_execute() returns True when circuit is CLOSED."""
    breaker = CircuitBreaker("test")
    assert breaker.can_execute() is True


def test_circuit_breaker_cannot_execute_when_open():
    """Test can_execute() returns False when circuit is OPEN."""
    breaker = CircuitBreaker("test", failure_threshold=1)

    # Open the circuit
    breaker.record_failure()

    assert breaker.can_execute() is False


def test_circuit_breaker_success_resets_failure_count():
    """Test record_success() resets failure count."""
    breaker = CircuitBreaker("test", failure_threshold=5)

    # Record some failures
    breaker.record_failure()
    breaker.record_failure()

    # Record success (should reset count)
    breaker.record_success()

    # Should still be closed even after more failures (up to threshold)
    breaker.record_failure()
    breaker.record_failure()
    assert breaker.state == CircuitState.CLOSED
