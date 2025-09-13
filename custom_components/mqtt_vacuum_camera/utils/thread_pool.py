from __future__ import annotations

import asyncio
import concurrent.futures
from functools import lru_cache
import os
import threading
from typing import Awaitable, Callable, Dict, TypeVar

from ..const import LOGGER

T = TypeVar("T")
R = TypeVar("R")


class ThreadPoolManager:
    """
    A singleton class that manages thread pools for different components.
    Adds per-pool semaphores to enforce concurrency limits and provide
    backpressure (queued tasks instead of unbounded submission).
    """

    _instances: Dict[str, ThreadPoolManager] = {}
    _instances_lock = threading.Lock()

    def __new__(cls, vacuum_id: str = "default"):
        with cls._instances_lock:
            if vacuum_id not in cls._instances:
                instance = super(ThreadPoolManager, cls).__new__(cls)
                instance._pools = {}
                instance._semaphores = {}
                instance.vacuum_id = vacuum_id
                instance._pool_lock = threading.Lock()
                cls._instances[vacuum_id] = instance
            return cls._instances[vacuum_id]

    def __init__(self, vacuum_id: str = "default"):
        if not hasattr(self, "_initialized"):
            self._pools = {}
            self._semaphores = {}
            self.vacuum_id = vacuum_id
            self._create_used_pools()
            self._initialized = True

    def _create_used_pools(self):
        """Pre-create thread pools + semaphores for this vacuum."""
        pool_configs = {
            "decompression": self._get_optimal_worker_count("decompression"),  # up to 2
            "camera_processing": 1,  # allow some overlap
        }

        for name, workers in pool_configs.items():
            self.get_create_executor(name, workers)

    def get_create_executor(
        self, name: str, max_workers: int = 1
    ) -> concurrent.futures.ThreadPoolExecutor:
        """Create or return executor + semaphore for given pool name."""
        if self.vacuum_id != "default":
            pool_name = f"{self.vacuum_id}_{name}"
        else:
            pool_name = f"default_{name}"
            LOGGER.warning(
                "Using default vacuum_id for thread pool. This is not recommended."
            )
        with self._pool_lock:
            if pool_name not in self._pools:
                LOGGER.debug(
                    "Creating thread pool %s with %d workers", pool_name, max_workers
                )
                self._pools[pool_name] = concurrent.futures.ThreadPoolExecutor(
                    max_workers=max_workers, thread_name_prefix=pool_name
                )
                self._semaphores[pool_name] = asyncio.Semaphore(max_workers)
            return self._pools[pool_name]

    async def run_in_executor(
        self, name: str, func: Callable[..., R], *args, max_workers: int = 1
    ) -> R:
        """Run sync function in thread pool with concurrency control."""
        pool_name = f"{self.vacuum_id}_{name}"
        executor = self.get_create_executor(name, max_workers)
        loop = asyncio.get_running_loop()
        sem = self._semaphores[pool_name]

        async with sem:

            def logged_func(*args):
                LOGGER.debug("Running %s in pool %s", func.__name__, pool_name)
                try:
                    return func(*args)
                except Exception as err:
                    LOGGER.error(
                        "ThreadPoolManager: Error in %s (%s): %s",
                        pool_name,
                        threading.current_thread().name,
                        err,
                        exc_info=True,
                    )
                    raise

            return await loop.run_in_executor(executor, logged_func, *args)

    async def run_async_in_executor(
        self,
        name: str,
        async_func: Callable[..., Awaitable[R]],
        *args,
        max_workers: int = 1,
    ) -> R:
        """Run async function in thread pool (rarely needed)."""

        def sync_wrapper_with_args():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(async_func(*args))
            finally:
                loop.close()

        return await self.run_in_executor(
            name, sync_wrapper_with_args, max_workers=max_workers
        )

    @staticmethod
    def _get_optimal_worker_count(task_type: str = "default") -> int:
        cpu_count = os.cpu_count() or 1
        if task_type == "decompression":
            return min(2, cpu_count)
        return 1

    @staticmethod
    @lru_cache(maxsize=32)
    def get_instance(vacuum_id: str) -> ThreadPoolManager:
        return ThreadPoolManager(vacuum_id)

    async def shutdown_instance(self):
        """Shutdown all pools for this vacuum."""
        LOGGER.debug("Shutting down thread pools for instance: %s", self.vacuum_id)
        pools_to_shutdown = list(self._pools.items())

        if pools_to_shutdown:
            for pool_name, pool in pools_to_shutdown:
                LOGGER.debug("Shutdown for pool: %s", pool_name)
                try:
                    pool.shutdown(wait=False)
                except Exception as e:
                    LOGGER.warning("Error shutting down pool %s: %s", pool_name, e)

        self._pools.clear()
        self._semaphores.clear()
        with self._instances_lock:
            if self.vacuum_id in self._instances:
                del self._instances[self.vacuum_id]
        self.get_instance.cache_clear()
        LOGGER.info("Thread pools for instance %s cleared", self.vacuum_id)

    @classmethod
    async def shutdown_all(cls):
        """Shutdown all pools across all vacuums."""
        LOGGER.debug("Shutting down all thread pools across all instances")
        instances = list(cls._instances.items())
        for _, instance in instances:
            for pool_name, pool in list(instance._pools.items()):
                LOGGER.debug("Shutdown for pool: %s", pool_name)
                try:
                    pool.shutdown(wait=False)
                except Exception as e:
                    LOGGER.warning("Error shutting down pool %s: %s", pool_name, e)

        cls.get_instance.cache_clear()
        cls._instances.clear()
        LOGGER.info("Thread pools and instances cleared")
