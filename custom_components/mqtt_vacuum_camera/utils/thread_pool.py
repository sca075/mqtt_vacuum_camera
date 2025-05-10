"""
Thread Pool Manager for MQTT Vacuum Camera.
This module provides a persistent thread pool for image processing operations.
Version: 2025.5.0
"""

from __future__ import annotations

import asyncio
import concurrent.futures
from functools import lru_cache
import logging
from typing import Any, Callable, Dict, Optional, TypeVar

_LOGGER = logging.getLogger(__name__)

T = TypeVar("T")
R = TypeVar("R")


class ThreadPoolManager:
    """
    A singleton class that manages thread pools for different components.
    This avoids creating and destroying thread pools for each operation.
    """

    _instance: Optional[ThreadPoolManager] = None
    _pools: Dict[str, concurrent.futures.ThreadPoolExecutor] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ThreadPoolManager, cls).__new__(cls)
            cls._instance._pools = {}
        return cls._instance

    def get_executor(
        self, name: str, max_workers: int = 1
    ) -> concurrent.futures.ThreadPoolExecutor:
        """
        Get or create a thread pool executor for a specific component.

        Args:
            name: The name of the component requesting the executor
            max_workers: Maximum number of worker threads

        Returns:
            A ThreadPoolExecutor instance
        """
        if name not in self._pools or self._pools[name]._shutdown:
            _LOGGER.debug(
                "Creating new thread pool for %s with %d workers", name, max_workers
            )
            self._pools[name] = concurrent.futures.ThreadPoolExecutor(
                max_workers=max_workers, thread_name_prefix=f"{name}_pool"
            )
        return self._pools[name]

    async def shutdown(self, name: Optional[str] = None):
        """
        Shutdown a specific thread pool or all thread pools asynchronously.

        Args:
            name: The name of the component whose pool should be shut down.
                 If None, all pools will be shut down.
        """
        if name is not None and name in self._pools:
            _LOGGER.debug("Shutting down thread pool for %s", name)
            await asyncio.to_thread(self._shutdown_pool, self._pools[name])
            del self._pools[name]
        elif name is None:
            _LOGGER.debug("Shutting down all thread pools")
            for pool_name, pool in list(self._pools.items()):
                await asyncio.to_thread(self._shutdown_pool, pool)
                del self._pools[pool_name]

    @staticmethod
    def _shutdown_pool(pool: concurrent.futures.ThreadPoolExecutor):
        """Shutdown a thread pool (to be called via asyncio.to_thread)."""
        pool.shutdown(wait=True)

    async def run_in_executor(
        self, name: str, func: Callable[[Any], R], *args, max_workers: int = 1
    ) -> R:
        """
        Run a function in a thread pool executor.

        Args:
            name: The name of the component requesting the executor
            func: The function to run
            *args: Arguments to pass to the function
            max_workers: Maximum number of worker threads

        Returns:
            The result of the function
        """
        executor = self.get_executor(name, max_workers)
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(executor, func, *args)

    @staticmethod
    @lru_cache(maxsize=32)
    def get_instance() -> ThreadPoolManager:
        """
        Get the singleton instance of ThreadPoolManager.
        This method is cached to avoid creating multiple instances.

        Returns:
            The singleton instance
        """
        return ThreadPoolManager()
