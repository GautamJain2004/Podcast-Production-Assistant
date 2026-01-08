"""
Retry Configuration for Podcast Production Suite

Centralized configuration for retry logic and rate limiting across the application.
"""

from utils.retry_handler import RetryConfig, set_global_retry_config
import logging

logger = logging.getLogger("config.retry_config")


# Default retry configuration (balanced for reliability)
DEFAULT_RETRY_CONFIG = RetryConfig(
    max_retries=3,              # Retry up to 3 times
    initial_delay=3.0,          # Start with 3 second delay (increased for 503 errors)
    max_delay=30.0,             # Cap at 30 seconds (increased for server recovery)
    exponential_base=2.0,       # Double delay each time (3s, 6s, 12s, 24s)
    rate_limit_delay=2.0        # 2 seconds between all API calls (increased to reduce load)
)


# Aggressive retry configuration (for production with paid API)
AGGRESSIVE_RETRY_CONFIG = RetryConfig(
    max_retries=5,              # More retries
    initial_delay=1.0,          # Shorter initial delay
    max_delay=32.0,             # Higher max delay
    exponential_base=2.0,
    rate_limit_delay=0.5        # Faster rate limiting
)


# Persistent retry configuration (keeps retrying until success)
PERSISTENT_RETRY_CONFIG = RetryConfig(
    max_retries=999,            # Essentially infinite retries
    initial_delay=15.0,         # Fixed 15 second delay
    max_delay=15.0,             # Keep it at 15 seconds (no increase)
    exponential_base=1.0,       # No exponential growth (stays at 15s)
    rate_limit_delay=2.0        # 2 seconds between agents
)


# Conservative retry configuration (for free tier or when getting 503 errors)
CONSERVATIVE_RETRY_CONFIG = RetryConfig(
    max_retries=2,              # Fewer retries (let Google SDK handle most)
    initial_delay=5.0,          # Much longer initial delay
    max_delay=60.0,             # Very high max delay (give servers time to recover)
    exponential_base=2.0,
    rate_limit_delay=5.0        # Much slower rate limiting (5s between agents)
)


def initialize_retry_config(mode: str = "default") -> None:
    """
    Initialize global retry configuration.
    
    Args:
        mode: Configuration mode - "default", "aggressive", "conservative", or "persistent"
    """
    config_map = {
        "default": DEFAULT_RETRY_CONFIG,
        "aggressive": AGGRESSIVE_RETRY_CONFIG,
        "conservative": CONSERVATIVE_RETRY_CONFIG,
        "persistent": PERSISTENT_RETRY_CONFIG
    }
    
    config = config_map.get(mode, DEFAULT_RETRY_CONFIG)
    set_global_retry_config(config)
    
    logger.info(f"Retry configuration initialized in '{mode}' mode")
    logger.info(
        f"  Max retries: {config.max_retries}, "
        f"Initial delay: {config.initial_delay}s, "
        f"Rate limit: {config.rate_limit_delay}s"
    )
    
    if mode == "persistent":
        logger.warning("⚠️  PERSISTENT MODE: Will retry indefinitely until success!")
        logger.warning("⚠️  Press Ctrl+C to stop if needed")


# Initialize with default configuration on import
initialize_retry_config("default")
