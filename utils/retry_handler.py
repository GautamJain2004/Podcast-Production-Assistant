"""
Retry Handler with Exponential Backoff

Provides automatic retry logic for API calls with rate limiting and exponential backoff.
Handles transient errors like 503 (Service Unavailable) and rate limit errors.
"""

import time
import logging
from typing import Callable, TypeVar, Optional, Any
from functools import wraps

logger = logging.getLogger("utils.retry_handler")

T = TypeVar('T')


class RetryConfig:
    """Configuration for retry behavior."""
    
    def __init__(
        self,
        max_retries: int = 3,
        initial_delay: float = 2.0,
        max_delay: float = 32.0,
        exponential_base: float = 2.0,
        rate_limit_delay: float = 1.0
    ):
        """
        Initialize retry configuration.
        
        Args:
            max_retries: Maximum number of retry attempts
            initial_delay: Initial delay in seconds before first retry
            max_delay: Maximum delay in seconds between retries
            exponential_base: Base for exponential backoff calculation
            rate_limit_delay: Delay in seconds between all API calls (rate limiting)
        """
        self.max_retries = max_retries
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.rate_limit_delay = rate_limit_delay


# Global retry configuration
_global_config = RetryConfig()


def set_global_retry_config(config: RetryConfig) -> None:
    """Set the global retry configuration."""
    global _global_config
    _global_config = config
    logger.info(
        f"Global retry config updated: max_retries={config.max_retries}, "
        f"initial_delay={config.initial_delay}s, rate_limit_delay={config.rate_limit_delay}s"
    )


def get_global_retry_config() -> RetryConfig:
    """Get the current global retry configuration."""
    return _global_config


def is_retryable_error(error: Exception) -> bool:
    """
    Determine if an error is retryable.
    
    Args:
        error: The exception to check
        
    Returns:
        True if the error should trigger a retry, False otherwise
    """
    error_str = str(error).lower()
    error_type = type(error).__name__.lower()
    error_module = type(error).__module__.lower()
    
    # Check for specific retryable conditions
    retryable_conditions = [
        '503' in error_str,  # Service Unavailable
        'overloaded' in error_str,  # Model overloaded
        'unavailable' in error_str,  # Service unavailable
        'timeout' in error_str,  # Timeout errors
        'rate limit' in error_str,  # Rate limit errors
        '429' in error_str,  # Too Many Requests
        'servererror' in error_type,  # ServerError type
        'servererror' in error_module,  # google.genai.errors.ServerError
        'genai.errors' in error_module,  # Any genai error module
    ]
    
    return any(retryable_conditions)


def calculate_backoff_delay(attempt: int, config: RetryConfig) -> float:
    """
    Calculate delay for exponential backoff.
    
    Args:
        attempt: Current retry attempt number (0-indexed)
        config: Retry configuration
        
    Returns:
        Delay in seconds
    """
    delay = config.initial_delay * (config.exponential_base ** attempt)
    return min(delay, config.max_delay)


def retry_with_backoff(
    func: Optional[Callable[..., T]] = None,
    *,
    config: Optional[RetryConfig] = None,
    on_retry: Optional[Callable[[Exception, int, float], None]] = None
) -> Callable[..., T]:
    """
    Decorator to add retry logic with exponential backoff to a function.
    
    Args:
        func: Function to wrap (when used as @retry_with_backoff)
        config: Retry configuration (uses global config if None)
        on_retry: Optional callback called on each retry attempt
                  Signature: (error, attempt, delay) -> None
    
    Returns:
        Decorated function with retry logic
        
    Example:
        @retry_with_backoff
        def call_api():
            return api.request()
            
        @retry_with_backoff(config=RetryConfig(max_retries=5))
        def call_api_custom():
            return api.request()
    """
    def decorator(f: Callable[..., T]) -> Callable[..., T]:
        @wraps(f)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            retry_config = config or get_global_retry_config()
            last_exception = None
            
            for attempt in range(retry_config.max_retries + 1):
                try:
                    # Add rate limiting delay before each call (except first)
                    if attempt > 0 and retry_config.rate_limit_delay > 0:
                        time.sleep(retry_config.rate_limit_delay)
                    
                    # Execute the function
                    result = f(*args, **kwargs)
                    
                    # Success - log if this was a retry
                    if attempt > 0:
                        logger.info(
                            f"✅ {f.__name__} succeeded after {attempt} retries"
                        )
                    
                    return result
                    
                except Exception as e:
                    last_exception = e
                    
                    # Check if error is retryable
                    if not is_retryable_error(e):
                        logger.warning(
                            f"❌ {f.__name__} failed with non-retryable error: {e}"
                        )
                        raise
                    
                    # Check if we have retries left
                    if attempt >= retry_config.max_retries:
                        logger.error(
                            f"❌ {f.__name__} failed after {retry_config.max_retries} retries: {e}"
                        )
                        raise
                    
                    # Calculate backoff delay
                    delay = calculate_backoff_delay(attempt, retry_config)
                    
                    # Log retry attempt
                    if retry_config.max_retries > 100:
                        # Persistent mode - show different message
                        logger.warning(
                            f"⚠️  {f.__name__} failed (attempt {attempt + 1}): {e}"
                        )
                        logger.info(
                            f"🔄 Retrying in {delay:.1f} seconds... (persistent mode - will keep trying)"
                        )
                    else:
                        logger.warning(
                            f"⚠️  {f.__name__} failed (attempt {attempt + 1}/{retry_config.max_retries + 1}): {e}"
                        )
                        logger.info(
                            f"🔄 Retrying in {delay:.1f} seconds..."
                        )
                    
                    # Call retry callback if provided
                    if on_retry:
                        try:
                            on_retry(e, attempt, delay)
                        except Exception as callback_error:
                            logger.warning(f"Retry callback failed: {callback_error}")
                    
                    # Wait before retry
                    time.sleep(delay)
            
            # Should never reach here, but just in case
            if last_exception:
                raise last_exception
            raise RuntimeError(f"{f.__name__} failed without exception")
        
        return wrapper
    
    # Handle both @retry_with_backoff and @retry_with_backoff()
    if func is None:
        return decorator
    else:
        return decorator(func)


def add_rate_limiting(delay: float = 1.0) -> Callable:
    """
    Decorator to add rate limiting (delay) between function calls.
    
    Args:
        delay: Delay in seconds between calls
        
    Returns:
        Decorated function with rate limiting
        
    Example:
        @add_rate_limiting(delay=0.5)
        def call_api():
            return api.request()
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        last_call_time = [0.0]  # Use list to allow modification in closure
        
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            # Calculate time since last call
            current_time = time.time()
            time_since_last_call = current_time - last_call_time[0]
            
            # If not enough time has passed, wait
            if time_since_last_call < delay:
                wait_time = delay - time_since_last_call
                logger.debug(f"⏱️  Rate limiting: waiting {wait_time:.2f}s before {func.__name__}")
                time.sleep(wait_time)
            
            # Update last call time
            last_call_time[0] = time.time()
            
            # Execute function
            return func(*args, **kwargs)
        
        return wrapper
    
    return decorator


class RateLimiter:
    """
    Context manager for rate limiting a block of code.
    
    Example:
        rate_limiter = RateLimiter(delay=1.0)
        
        with rate_limiter:
            call_api_1()
        
        with rate_limiter:
            call_api_2()  # Will wait 1s after previous call
    """
    
    def __init__(self, delay: float = 1.0):
        """
        Initialize rate limiter.
        
        Args:
            delay: Minimum delay in seconds between operations
        """
        self.delay = delay
        self.last_call_time = 0.0
    
    def __enter__(self):
        """Enter context - apply rate limiting."""
        current_time = time.time()
        time_since_last_call = current_time - self.last_call_time
        
        if time_since_last_call < self.delay:
            wait_time = self.delay - time_since_last_call
            logger.debug(f"⏱️  Rate limiting: waiting {wait_time:.2f}s")
            time.sleep(wait_time)
        
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context - update last call time."""
        self.last_call_time = time.time()
        return False  # Don't suppress exceptions
