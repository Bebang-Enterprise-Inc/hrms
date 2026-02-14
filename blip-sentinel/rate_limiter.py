"""
Blip Sentinel - Rate Limiting and Circuit Breaker

Implements token bucket rate limiting and circuit breaker pattern for API calls.
Protects against quota exhaustion and cascading failures.
"""

import time
import logging
from enum import Enum
from typing import Callable, Any, Optional
from collections import deque

logger = logging.getLogger("sentinel.rate_limiter")


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"        # Normal operation
    OPEN = "open"            # Failing, reject calls immediately
    HALF_OPEN = "half_open"  # Testing if service recovered


class TokenBucket:
    """
    Token bucket rate limiter.

    Allows bursts up to capacity, then enforces steady-state rate.
    Thread-safe for single-process use.

    Example:
        >>> limiter = TokenBucket(rate=1400, per=60)  # 1400 calls per 60 seconds
        >>> if limiter.consume(1):
        ...     make_api_call()
        ... else:
        ...     print("Rate limited")
    """

    def __init__(self, rate: int, per: int):
        """
        Initialize token bucket.

        Args:
            rate: Number of tokens to generate
            per: Time period in seconds

        Example:
            TokenBucket(rate=1400, per=60) allows 1400 calls per minute
        """
        self.rate = rate
        self.per = per
        self.capacity = rate
        self.tokens = float(rate)
        self.last_update = time.time()

        logger.info(f"TokenBucket initialized: {rate} tokens per {per}s (capacity: {self.capacity})")

    def _refill(self):
        """Refill tokens based on elapsed time."""
        now = time.time()
        elapsed = now - self.last_update

        # Add tokens based on elapsed time
        tokens_to_add = (elapsed / self.per) * self.rate
        self.tokens = min(self.capacity, self.tokens + tokens_to_add)
        self.last_update = now

    def consume(self, tokens: int = 1) -> bool:
        """
        Attempt to consume tokens.

        Args:
            tokens: Number of tokens to consume

        Returns:
            True if tokens were consumed, False if insufficient tokens
        """
        self._refill()

        if self.tokens >= tokens:
            self.tokens -= tokens
            logger.debug(f"Consumed {tokens} token(s), {self.tokens:.2f} remaining")
            return True
        else:
            logger.warning(f"Rate limit exceeded: need {tokens}, have {self.tokens:.2f}")
            return False

    def wait_for_token(self, tokens: int = 1, max_wait: float = 60.0) -> bool:
        """
        Wait until tokens are available (blocking).

        Args:
            tokens: Number of tokens needed
            max_wait: Maximum seconds to wait

        Returns:
            True if tokens were acquired, False if max_wait exceeded
        """
        start = time.time()

        while time.time() - start < max_wait:
            if self.consume(tokens):
                return True

            # Sleep for a fraction of the refill period
            sleep_time = min(1.0, self.per / 10)
            time.sleep(sleep_time)

        logger.error(f"Timeout waiting for {tokens} token(s) after {max_wait}s")
        return False


class CircuitBreaker:
    """
    Circuit breaker for fault tolerance.

    Prevents cascading failures by stopping calls to a failing service.
    Automatically attempts recovery after timeout.

    States:
    - CLOSED: Normal operation, calls allowed
    - OPEN: Too many failures, calls rejected immediately
    - HALF_OPEN: Testing recovery, allow 1 call

    Example:
        >>> breaker = CircuitBreaker("google_chat", failure_threshold=5, recovery_timeout=300)
        >>> if breaker.can_execute():
        ...     try:
        ...         result = api_call()
        ...         breaker.record_success()
        ...     except Exception:
        ...         breaker.record_failure()
    """

    def __init__(self, name: str, failure_threshold: int = 5, recovery_timeout: int = 300):
        """
        Initialize circuit breaker.

        Args:
            name: Identifier for this circuit breaker
            failure_threshold: Consecutive failures before opening circuit
            recovery_timeout: Seconds to wait in OPEN state before trying HALF_OPEN
        """
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time = None

        logger.info(f"CircuitBreaker '{name}' initialized: threshold={failure_threshold}, timeout={recovery_timeout}s")

    @property
    def state(self) -> CircuitState:
        """Get current circuit state."""
        self._check_recovery()
        return self._state

    def _check_recovery(self):
        """Check if circuit should transition from OPEN to HALF_OPEN."""
        if self._state == CircuitState.OPEN and self._last_failure_time:
            elapsed = time.time() - self._last_failure_time
            if elapsed >= self.recovery_timeout:
                logger.info(f"CircuitBreaker '{self.name}': OPEN -> HALF_OPEN (recovery timeout elapsed)")
                self._state = CircuitState.HALF_OPEN

    def can_execute(self) -> bool:
        """
        Check if calls are allowed in current state.

        Returns:
            True if call should be attempted, False if circuit is OPEN
        """
        current_state = self.state  # Triggers recovery check

        if current_state == CircuitState.OPEN:
            logger.warning(f"CircuitBreaker '{self.name}': Call rejected (circuit OPEN)")
            return False

        return True

    def record_success(self):
        """Record a successful call."""
        if self._state == CircuitState.HALF_OPEN:
            logger.info(f"CircuitBreaker '{self.name}': HALF_OPEN -> CLOSED (success)")
            self._state = CircuitState.CLOSED

        self._failure_count = 0

    def record_failure(self):
        """Record a failed call."""
        self._failure_count += 1
        self._last_failure_time = time.time()

        logger.warning(f"CircuitBreaker '{self.name}': Failure #{self._failure_count}")

        if self._state == CircuitState.HALF_OPEN:
            logger.warning(f"CircuitBreaker '{self.name}': HALF_OPEN -> OPEN (recovery failed)")
            self._state = CircuitState.OPEN
        elif self._failure_count >= self.failure_threshold:
            logger.error(f"CircuitBreaker '{self.name}': CLOSED -> OPEN (threshold reached)")
            self._state = CircuitState.OPEN


def rate_limited_call(
    func: Callable,
    *args,
    rate_limiter: Optional[TokenBucket] = None,
    circuit_breaker: Optional[CircuitBreaker] = None,
    **kwargs
) -> Any:
    """
    Execute a function with rate limiting and circuit breaker protection.

    Args:
        func: Function to call
        *args: Positional arguments for func
        rate_limiter: Optional TokenBucket instance
        circuit_breaker: Optional CircuitBreaker instance
        **kwargs: Keyword arguments for func

    Returns:
        Result of func(*args, **kwargs)

    Raises:
        RuntimeError: If circuit breaker is OPEN
        TimeoutError: If rate limiter cannot acquire token
        Exception: Any exception raised by func

    Example:
        >>> limiter = TokenBucket(rate=10, per=60)
        >>> breaker = CircuitBreaker("api")
        >>> result = rate_limited_call(api_func, arg1, arg2, rate_limiter=limiter, circuit_breaker=breaker)
    """
    # Check circuit breaker
    if circuit_breaker and not circuit_breaker.can_execute():
        raise RuntimeError(f"Circuit breaker '{circuit_breaker.name}' is OPEN")

    # Check rate limiter
    if rate_limiter:
        if not rate_limiter.wait_for_token(tokens=1, max_wait=30.0):
            raise TimeoutError("Rate limiter timeout: could not acquire token")

    # Execute function
    try:
        result = func(*args, **kwargs)

        if circuit_breaker:
            circuit_breaker.record_success()

        return result

    except Exception as e:
        if circuit_breaker:
            circuit_breaker.record_failure()

        logger.error(f"rate_limited_call failed: {e}")
        raise
