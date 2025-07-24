"""
Thread Pool Manager for MQTT Vacuum Camera.
This module provides a persistent thread pool for image processing operations.
Version: 2025.6.0
"""

from __future__ import annotations

import asyncio
import concurrent.futures
from functools import lru_cache
import os
import threading
from typing import Awaitable, Callable, Dict, TypeVar, List

from ..const import LOGGER

T = TypeVar("T")
R = TypeVar("R")


class ThreadPoolManager:
    """
    A singleton class that manages thread pools for different components.
    This avoids creating and destroying thread pools for each operation.
    """

    _instances: Dict[str, ThreadPoolManager] = {}
    _instances_lock = threading.Lock()

    def __new__(cls, vacuum_id: str = "default"):
        with cls._instances_lock:
            if vacuum_id not in cls._instances:
                instance = super(ThreadPoolManager, cls).__new__(cls)
                instance._pools = {}  # Instance-specific pools dictionary
                instance.vacuum_id = vacuum_id
                instance._pool_lock = threading.Lock()  # Instance-level lock
                instance.pools_to_shutdown = []
                # DON'T set _initialized here - let __init__ handle it
                cls._instances[vacuum_id] = instance
            return cls._instances[vacuum_id]

    def __init__(self, vacuum_id: str = "default"):
        # Only initialize if this is a new instance
        if not hasattr(self, "_initialized"):
            self._pools = {}
            self.vacuum_id = vacuum_id
            self._create_used_pools()  # Pre-create all pools
            self._initialized = True

    def _create_used_pools(self):
        """Pre-create all thread pools for this vacuum."""
        pool_configs = {
            "decompression": self._get_optimal_worker_count(
                "decompression"
            ),  # 2 workers
            "camera": 1,
            "camera_processing": 1,
            "snapshot": 1,
        }

        for name, workers in pool_configs.items():
            pool_name = f"{self.vacuum_id}_{name}"
            LOGGER.debug(
                "Pre-creating thread pool: %s with %d workers", pool_name, workers
            )

            _ = self.get_create_executor(name, workers)

    def get_create_executor(
        self, name: str, max_workers: int = 1
    ) -> concurrent.futures.ThreadPoolExecutor:
        # Create a pool name that includes the vacuum_id to avoid conflicts
        if self.vacuum_id != "default":
            pool_name = f"{self.vacuum_id}_{name}"
        else:
            pool_name = f"default_{name}"
            LOGGER.warning(
                "Using default vacuum_id for thread pool. This is not recommended."
            )
        with self._pool_lock:
            if pool_name not in self._pools:
                self._pools[pool_name] = concurrent.futures.ThreadPoolExecutor(
                    max_workers=max_workers, thread_name_prefix=pool_name
                )
            return self._pools[pool_name]

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
        try:
            executor = self.get_create_executor(name, max_workers)
            loop = asyncio.get_running_loop()

            # Create a wrapper function that logs from the worker thread
            def logged_func(*args):
                LOGGER.debug(
                    "Running function in thread pool: %s",
                    name,
                )
                try:
                    result = func(*args)
                    return result
                except Exception as err:
                    LOGGER.error(
                        "ThreadPoolManager: Error in %s worker thread %s: %s",
                        name,
                        threading.current_thread().name,
                        str(err),
                    )
                    raise

            return await loop.run_in_executor(executor, logged_func, *args)
        except Exception as e:
            LOGGER.error(
                "Error executing function in thread pool: %s", str(e), exc_info=True
            )
            raise

    async def run_async_in_executor(
        self,
        name: str,
        async_func: Callable[..., Awaitable[R]],
        *args,
        max_workers: int = 1,
    ) -> R:
        """
        Run an async function in a thread pool by automatically wrapping it.

        Args:
            name: The name of the component requesting the executor
            async_func: The async function to run
            *args: Arguments to pass to the function
            max_workers: Maximum number of worker threads

        Returns:
            The result of the async function
        """

        # Create a wrapper that captures the async function and its arguments
        def sync_wrapper_with_args():
            # Create new event loop in worker thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                # Run the async function with the captured arguments
                result = loop.run_until_complete(async_func(*args))
                return result
            finally:
                loop.close()

        # Run the wrapper function in the executor (no additional args needed)
        return await self.run_in_executor(
            name, sync_wrapper_with_args, max_workers=max_workers
        )

    @staticmethod
    def _get_optimal_worker_count(task_type: str = "default") -> int:
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
    def get_instance(vacuum_id: str) -> ThreadPoolManager:
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
    async def shutdown_all(cls):
        """
        Shutdown all thread pools across all instances with proper error handling.
        This is useful for application shutdown.
        """
        LOGGER.debug("Shutting down all thread pools across all instances")
        # Create a copy of the instances to avoid modifying during iteration
        instances = list(cls._instances.items())

        # Collect all pools from all instances for direct shutdown
        all_pools = []
        for _, instance in instances:
            pools_to_shutdown = list(instance._pools.items())
            all_pools.extend(pools_to_shutdown)

        # Shutdown all pools quickly - don't wait for completion
        if all_pools:
            try:
                # Initiate shutdown for all pools without waiting
                for pool_name, pool in all_pools:
                    LOGGER.debug("Shutdown for pool: %s", pool_name)
                    try:
                        # Use shutdown(wait=False) for immediate return
                        pool.shutdown(wait=False)
                    except Exception as e:
                        LOGGER.warning("Error shutting down pool %s: %s", pool_name, e)

                LOGGER.debug("All thread pools are now shutdown...")
            except Exception as e:
                LOGGER.error("Error during thread pool shutdown: %s", e)

        # Clear instances regardless of shutdown success
        cls.get_instance.cache_clear()
        cls._instances.clear()
        LOGGER.info("Thread pools and instances cleared")


class TaskQueue:
    def __init__(self, max_batch=5, batch_timeout=0.1):
        self._queue: List[Awaitable] = []
        self._max_batch, self._timeout = max_batch, batch_timeout
        self._timer = None

    def add_task(self, coro: Awaitable):
        self._queue.append(coro)
        if len(self._queue) >= self._max_batch:
            asyncio.create_task(self._process_batch())
        elif len(self._queue) == 1:  # First task starts timer
            self._timer = asyncio.create_task(asyncio.sleep(self._timeout))
            self._timer.add_done_callback(
                lambda _: asyncio.create_task(self._process_batch())
            )

    async def _process_batch(self):
        if self._queue:
            batch, self._queue = (
                self._queue[: self._max_batch],
                self._queue[self._max_batch :],
            )
            if self._timer:
                self._timer.cancel()
            await asyncio.gather(*batch, return_exceptions=True)
