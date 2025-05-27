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
import os
from typing import Callable, Dict, Optional, TypeVar

_LOGGER = logging.getLogger(__name__)

T = TypeVar("T")
R = TypeVar("R")


class ThreadPoolManager:
    """
    A singleton class that manages thread pools for different components.
    This avoids creating and destroying thread pools for each operation.
    """

    _instances: Dict[str, ThreadPoolManager] = {}

    def __new__(cls, vacuum_id: str = "default"):
        if vacuum_id not in cls._instances:
            instance = super(ThreadPoolManager, cls).__new__(cls)
            instance._pools = {}  # Instance-specific pools dictionary
            instance.vacuum_id = vacuum_id
            cls._instances[vacuum_id] = instance
        return cls._instances[vacuum_id]

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
        # Create a pool name that includes the vacuum_id to avoid conflicts
        pool_name = f"{self.vacuum_id}_{name}" if self.vacuum_id != "default" else name

        if pool_name not in self._pools or self._pools[pool_name]._shutdown:
            _LOGGER.debug(
                "Creating new thread pool for %s with %d workers",
                pool_name,
                max_workers,
            )
            self._pools[pool_name] = concurrent.futures.ThreadPoolExecutor(
                max_workers=max_workers, thread_name_prefix=f"{pool_name}_pool"
            )
        return self._pools[pool_name]

    async def shutdown(self, name: Optional[str] = None):
        """
        Shutdown a specific thread pool or all thread pools asynchronously.

        Args:
            name: The name of the component whose pool should be shut down.
                 If None, all pools will be shut down.
        """
        # If a specific name is provided, create the pool name with vacuum_id
        if name is not None:
            pool_name = (
                f"{self.vacuum_id}_{name}" if self.vacuum_id != "default" else name
            )
            if pool_name in self._pools:
                _LOGGER.debug("Shutting down thread pool for %s", pool_name)
                await asyncio.to_thread(self._shutdown_pool, self._pools[pool_name])
                del self._pools[pool_name]
        # If no name is provided, shut down all pools for this vacuum_id
        else:
            _LOGGER.debug(
                "Shutting down all thread pools for vacuum_id %s", self.vacuum_id
            )
            # Create a list of pools to shut down to avoid modifying the dictionary during iteration
            pools_to_shutdown = list(self._pools.items())

            for pool_name, pool in pools_to_shutdown:
                _LOGGER.debug("Shutting down pool %s", pool_name)
                await asyncio.to_thread(self._shutdown_pool, pool)
                del self._pools[pool_name]

    @staticmethod
    def _shutdown_pool(pool: concurrent.futures.ThreadPoolExecutor):
        """Shutdown a thread pool (to be called via asyncio.to_thread)."""
        pool.shutdown(wait=True)

    async def run_in_executor(
        self, name: str, func: Callable[..., R], *args, max_workers: int = 1
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
        if name == "decompression":
            max_workers = self.get_optimal_worker_count("decompression")

        try:
            executor = self.get_executor(self.vacuum_id, max_workers)
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(executor, func, *args)
        except Exception as e:
            _LOGGER.error(
                "Error executing function in thread pool: %s", str(e), exc_info=True
            )
            raise

    @staticmethod
    def get_optimal_worker_count(task_type: str = "default") -> int:
        """
        Calculate the optimal number of worker threads based on the task type.

        Args:
            task_type: The type of task ("decompression" or any other task)

        Returns:
            The optimal number of worker threads
        """
        cpu_count = os.cpu_count() or 1

        if task_type == "decompression":
            # For decompression tasks, use at most 2 workers to avoid excessive resource usage
            return min(2, cpu_count)
        else:
            # For all other tasks, use 1 worker to minimize resource usage
            return 1

    @staticmethod
    @lru_cache(maxsize=32)
    def get_instance(vacuum_id: str = "default") -> ThreadPoolManager:
        """
        Get the singleton instance of ThreadPoolManager for a specific vacuum.
        This method is cached to avoid creating multiple instances.

        Args:
            vacuum_id: The ID of the vacuum to get the instance for.
                      Use "default" for non-vacuum-specific operations.

        Returns:
            The singleton instance for the specified vacuum
        """
        return ThreadPoolManager(vacuum_id)

    @classmethod
    def get_all_instances(cls) -> Dict[str, ThreadPoolManager]:
        """
        Get all instances of ThreadPoolManager.

        Returns:
            A dictionary of all instances, keyed by vacuum_id
        """
        return cls._instances

    @classmethod
    async def shutdown_all(cls):
        """
        Shutdown all thread pools across all instances.
        This is useful for application shutdown.
        """
        _LOGGER.debug("Shutting down all thread pools across all instances")
        # Create a copy of the instances to avoid modifying during iteration
        instances = list(cls._instances.items())
        for vacuum_id, instance in instances:
            await instance.shutdown()
        cls._instances.clear()
