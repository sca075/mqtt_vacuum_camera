from __future__ import annotations

import asyncio
from concurrent.futures import Future, ThreadPoolExecutor
from functools import lru_cache
import os
from queue import Empty, Full, Queue
import threading
from typing import Awaitable, Callable, Dict, TypeVar

from ..const import LOGGER

T = TypeVar("T")
R = TypeVar("R")


class BoundedExecutor:
    def __init__(self, max_workers: int, max_queue: int = 3, name: str = "default"):
        self._exec = ThreadPoolExecutor(
            max_workers=max_workers, thread_name_prefix=name
        )
        self._q: Queue = Queue(maxsize=max_queue)
        self._stop = threading.Event()
        self._name = name
        # simple metrics
        self._stats_lock = threading.Lock()
        self._submitted = 0
        self._dropped = 0
        self._started = 0
        self._executed = 0
        for _ in range(max_workers):
            self._exec.submit(self._worker)

    def _worker(self):
        while not self._stop.is_set():
            try:
                fn, args, kwargs, promise = self._q.get(timeout=0.2)
            except Empty:
                continue
            with self._stats_lock:
                self._started += 1
            if promise.set_running_or_notify_cancel():
                try:
                    res = fn(*args, **kwargs)
                except BaseException as e:
                    promise.set_exception(e)
                else:
                    promise.set_result(res)
            with self._stats_lock:
                self._executed += 1
            self._q.task_done()

    def submit_latest(self, fn, *args, **kwargs) -> Future:
        # Always prefer latest: if queue full, drop the oldest and enqueue the new one
        fut: Future = Future()
        with self._stats_lock:
            self._submitted += 1
        try:
            self._q.put_nowait((fn, args, kwargs, fut))
        except Full:
            try:
                old_fn, old_args, old_kwargs, old_promise = (
                    self._q.get_nowait()
                )  # drop oldest
                self._q.task_done()
                # Signal the dropped future so awaiters don't hang
                try:
                    old_promise.set_exception(
                        RuntimeError("dropped: newer job preferred")
                    )
                except Exception:
                    pass
                with self._stats_lock:
                    self._dropped += 1
            except Empty:
                pass
            self._q.put_nowait((fn, args, kwargs, fut))
        return fut

    def stats(self) -> dict:
        with self._stats_lock:
            return {
                "name": self._name,
                "submitted": self._submitted,
                "dropped": self._dropped,
                "started": self._started,
                "executed": self._executed,
                "queue_size": self._q.qsize(),
            }

    def shutdown(self, wait: bool = False):
        self._stop.set()
        self._exec.shutdown(wait=wait)


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
                instance.vacuum_id = vacuum_id
                instance._pool_lock = threading.Lock()
                cls._instances[vacuum_id] = instance
            return cls._instances[vacuum_id]

    def __init__(self, vacuum_id: str = "default"):
        if not hasattr(self, "_initialized"):
            self._pools = {}
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

    def get_create_executor(self, name: str, max_workers: int = 1) -> BoundedExecutor:
        """Create or return a bounded executor for given pool name.
        Bounded executor keeps a tiny queue (size 1) and always prefers the latest job.
        """
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
                    "Creating bounded thread pool %s with %d workers",
                    pool_name,
                    max_workers,
                )
                qsize = self._get_queue_size(name)
                self._pools[pool_name] = BoundedExecutor(
                    max_workers=max_workers, max_queue=qsize, name=pool_name
                )
            return self._pools[pool_name]

    async def run_in_executor(
        self, name: str, func: Callable[..., R], *args, max_workers: int = 1
    ) -> R:
        """Run sync function in bounded thread pool, preferring the latest submission."""
        pool_name = f"{self.vacuum_id}_{name}"
        executor = self.get_create_executor(name, max_workers)

        def logged_func(*f_args):
            try:
                return func(*f_args)
            except Exception as err:
                LOGGER.error(
                    "ThreadPoolManager: Error in %s (%s): %s",
                    pool_name,
                    threading.current_thread().name,
                    err,
                    exc_info=True,
                )
                raise

        fut = executor.submit_latest(logged_func, *args)
        return await asyncio.wrap_future(fut)

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

    def shut_down_specific_pool(self, name: str, wait: bool = False) -> None:
        """Shutdown and remove a specific pool for this vacuum.

        Does not affect other pools or instances. Safe to call multiple times.
        """
        pool_name = (
            f"{self.vacuum_id}_{name}"
            if self.vacuum_id != "default"
            else f"default_{name}"
        )
        with self._pool_lock:
            executor = self._pools.pop(pool_name, None)
            if executor is not None:
                try:
                    executor.shutdown(wait=wait)
                except Exception as e:
                    LOGGER.warning("Error shutting down pool %s: %s", pool_name, e)

    def shutdown_pool(self, name: str, wait: bool = False) -> None:
        """Alias utility to shut down a specific pool (public-friendly name)."""
        self.shut_down_specific_pool(name, wait)

    def get_pool_stats(self, name: str) -> dict | None:
        """Return metrics for a specific pool, if available."""
        pool_name = (
            f"{self.vacuum_id}_{name}"
            if self.vacuum_id != "default"
            else f"default_{name}"
        )
        with self._pool_lock:
            exec_obj = self._pools.get(pool_name)
        if exec_obj and hasattr(exec_obj, "stats"):
            return exec_obj.stats()
        return None

    @staticmethod
    def _get_optimal_worker_count(task_type: str = "default") -> int:
        cpu_count = os.cpu_count() or 1
        if task_type == "decompression":
            return min(2, cpu_count)
        return 1

    @staticmethod
    def _get_queue_size(name: str) -> int:
        """Queue sizing per pool name (small to avoid backlogs)."""
        # Prefer tiny queues; latest-wins behavior will drop intermediate items.
        if name == "decompression":
            return 2
        if name == "camera_processing":
            return 3
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
