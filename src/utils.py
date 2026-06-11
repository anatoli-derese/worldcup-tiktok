"""Shared utilities: logging and retries."""
import logging
import time
from functools import wraps

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)

def retry(max_attempts: int = 3, delay: float = 2.0):
    """Retry decorator with exponential backoff."""
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            last_err: Exception | None = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return fn(*args, **kwargs)
                except Exception as e:
                    last_err = e
                    if attempt < max_attempts:
                        wait = delay * (2 ** (attempt - 1))
                        get_logger(fn.__module__).warning(
                            f"Attempt {attempt} failed: {e}. Retrying in {wait}s..."
                        )
                        time.sleep(wait)
            raise RuntimeError(f"All {max_attempts} attempts failed") from last_err
        return wrapper
    return decorator

