"""
News Intelligence System v3.0 - Timeout Utilities
Provides timeout protection for all external calls
"""

import asyncio
import logging
from collections.abc import Callable
from functools import wraps
from typing import Any

logger = logging.getLogger(__name__)


def timeout_protection(timeout_seconds: int = 30):
    """Decorator to add timeout protection to async functions"""

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            try:
                return await asyncio.wait_for(func(*args, **kwargs), timeout=timeout_seconds)
            except asyncio.TimeoutError:
                logger.error(f"Function {func.__name__} timed out after {timeout_seconds} seconds")
                return None
            except Exception as e:
                logger.error(f"Function {func.__name__} failed: {e}")
                return None

        return wrapper

    return decorator


async def safe_api_call(url: str, timeout: int = 10) -> dict | None:
    """Make a safe API call with timeout"""
    try:
        import aiohttp

        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=timeout)) as session:
            async with session.get(url) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logger.error(f"API call failed with status {response.status}")
                    return None
    except asyncio.TimeoutError:
        logger.error(f"API call to {url} timed out after {timeout} seconds")
        return None
    except Exception as e:
        logger.error(f"API call to {url} failed: {e}")
        return None


async def safe_database_call(query_func: Callable, timeout: int = 5) -> Any | None:
    """Execute database call with timeout"""
    try:
        return await asyncio.wait_for(query_func(), timeout=timeout)
    except asyncio.TimeoutError:
        logger.error(f"Database call timed out after {timeout} seconds")
        return None
    except Exception as e:
        logger.error(f"Database call failed: {e}")
        return None
