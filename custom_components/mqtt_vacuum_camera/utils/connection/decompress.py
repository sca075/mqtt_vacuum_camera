"""
Decompression Manager for MQTT Vacuum Camera.
This module provides a singleton manager for decompressing MQTT map payloads.
Version: 2025.5.0
"""

from __future__ import annotations

import asyncio
from collections import OrderedDict
from functools import lru_cache
import json
import time
from typing import Any, Dict, List, Optional, Tuple

from isal import igzip, isal_zlib  # pylint: disable=I1101
from valetudo_map_parser.config.rand25_parser import RRMapParser

from custom_components.mqtt_vacuum_camera.const import LOGGER
from custom_components.mqtt_vacuum_camera.utils.thread_pool import ThreadPoolManager

# Extract the cache function to module scope
@lru_cache(maxsize=32)
def _make_cache_key(topic: str, data_type: str, payload_hash: int) -> str:
    """Generate a cache key for decompression results."""
    return f"{topic}:{data_type}:{payload_hash}"


class FIFOCache:
    """
    A FIFO (First-In-First-Out) cache implementation with a maximum size limit.
    When the cache reaches its maximum size, the oldest entries are evicted first.
    """

    def __init__(self, max_size: int = 3):
        """Initialize the FIFO cache with a maximum size.

        Args:
            max_size: Maximum number of entries to store in the cache
        """
        self._max_size = max_size
        self._cache = OrderedDict()  # OrderedDict preserves insertion order

    def get(self, key: str) -> Optional[Tuple[Any, float]]:
        """Get a value from the cache.

        Args:
            key: The cache key

        Returns:
            The cached value and timestamp, or None if not found
        """
        return self._cache.get(key)

    def put(self, key: str, value: Any) -> None:
        """Add a value to the cache with the current timestamp.

        If the cache is full, the oldest entry will be evicted.

        Args:
            key: The cache key
            value: The value to cache
        """
        # If the key already exists, remove it first to update its position
        if key in self._cache:
            del self._cache[key]

        # Add the new entry with current timestamp
        self._cache[key] = (value, time.time())

        # If we've exceeded the maximum size, remove the oldest entry (first item)
        if len(self._cache) > self._max_size:
            self._cache.popitem(last=False)  # Remove the first item (oldest)

    def clear(self) -> None:
        """Clear all entries from the cache."""
        self._cache.clear()

    def __len__(self) -> int:
        """Return the number of entries in the cache."""
        return len(self._cache)

    def get_max_size(self) -> int:
        """Return the maximum size of the cache."""
        return self._max_size

    def get_all_keys(self) -> List[str]:
        """Return all keys in the cache."""
        return list(self._cache.keys())


class DecompressionManager:
    """
    Singleton manager for decompressing MQTT map payloads with header validation
    using a FIFO queue and ThreadPoolManager for efficient processing.
    Each vacuum has its own instance for better isolation.
    """

    _instances: Dict[str, "DecompressionManager"] = {}  # Store instances by vacuum_id

    def __new__(cls, vacuum_id: str = "default") -> "DecompressionManager":
        if vacuum_id not in cls._instances:
            cls._instances[vacuum_id] = super().__new__(cls)
        return cls._instances[vacuum_id]

    def __init__(self, vacuum_id: str = "default") -> None:
        # Skip initialization if already initialized for this vacuum_id
        if hasattr(self, "initialized") and self.initialized:
            return

        self.initialized = True
        self.vacuum_id = vacuum_id

        # Track background tasks for cleanup
        self._background_tasks = []

        # Get the thread pool manager instance for this vacuum - defer worker creation
        self._thread_pool = ThreadPoolManager.get_instance(vacuum_id)

        # Pre-initialize parser to avoid initialization delay during first use
        self._parser = RRMapParser()

        # Use a priority queue for better task management
        self._queue: asyncio.PriorityQueue = asyncio.PriorityQueue()

        # Add a counter for task ordering to ensure FIFO behavior
        self._task_counter = 0

        # FIFO cache with a maximum of 3 entries per vacuum (to handle 0.5s image frequency)
        self._results = FIFOCache(max_size=3)

        # Cache expiration time (10 minutes)
        self._cache_expiry = 600

        # Defer background worker creation to avoid initialization delays
        asyncio.create_task(self._initialize_workers())

        LOGGER.debug(
            "Initialized DecompressionManager for vacuum: %s", vacuum_id
        )

    @staticmethod
    def get_instance(vacuum_id: str = "default") -> "DecompressionManager":
        """Get the singleton instance of DecompressionManager for a specific vacuum.

        Args:
            vacuum_id: The unique identifier for the vacuum

        Returns:
            The singleton instance for this vacuum
        """
        return DecompressionManager(vacuum_id)

    @staticmethod
    def _cache_key(topic: str, data_type: str, payload_hash: int) -> str:
        """Generate a cache key using the module-level cached function."""
        return _make_cache_key(topic, data_type, payload_hash)

    @property
    def decompress_queue(self) -> bool:
        """
        Check if there are items in the decompression queue waiting to be processed.

        Returns:
            bool: True if there are items in the queue, False otherwise
        """
        return not self._queue.empty()

    async def _validate_compressed_header(
            self, payload: bytes, data_type: str
    ) -> bool:
        """
        Validate compressed data headers and checksums.
        Args:
            payload: The compressed payload
            data_type: Either "Rand256" or "Hypfer"
        Returns:
            bool: True if valid, False otherwise
        """
        try:
            if len(payload) < 4:
                LOGGER.warning(
                    "%s Payload too short: %r",
                    self.vacuum_id,
                    payload[:10],
                )
                return False

            if data_type == "Hypfer":
                # isal-zlib header magic bytes: 0x78 0x9c
                if not payload.startswith(b"\x78\x9c"):
                    LOGGER.warning(
                        "%s Invalid isal-zlib header: %r",
                        self.vacuum_id,
                        payload[:10],
                    )
                    return False
                # Validate zlib header checksum
                if (payload[0] * 256 + payload[1]) % 31 != 0:
                    LOGGER.warning(
                        "%s Invalid isal-zlib header checksum",
                        self.vacuum_id,
                    )
                    return False
            elif data_type == "Rand256":
                # gzip header magic bytes: 0x1f 0x8b
                if not payload.startswith(b"\x1f\x8b"):
                    LOGGER.warning(
                        "%s Invalid gzip header: %r",
                        self.vacuum_id,
                        payload[:10],
                    )
                    return False
            return True
        except Exception as e:
            LOGGER.error("Error validating header: %s", str(e))
            return False

    async def _cleanup_cache(self) -> None:
        """
        Periodically check for expired cache entries.
        With the FIFO cache implementation, we don't need to manually remove old entries,
        but we still want to log cache statistics periodically.
        """
        while True:
            try:
                await asyncio.sleep(60)  # Check every minute

                # Only log cache statistics in debug mode
                if LOGGER.isEnabledFor(10):  # DEBUG level
                    cache_size = len(self._results)
                    LOGGER.debug(
                        "%s: Cache status - %d entries in FIFO cache (max: %d)",
                        self.vacuum_id,
                        cache_size,
                        self._results.get_max_size()
                    )

            except asyncio.CancelledError:
                break
            except Exception as e:
                LOGGER.error("Error in cache monitoring: %s", str(e))

    async def _worker_loop(self) -> None:
        """
        Consume tasks: each is (priority, (topic, payload, data_type, future)).
        Implements FIFO processing with efficient caching.
        """

        def _hypfer_decompress(p: bytes) -> str:  # local helper
            return isal_zlib.decompress(p).decode()

        def _rand256_decompress(p: bytes) -> bytes:
            return igzip.decompress(p)

        while True:
            try:
                # Get next task with priority
                _, (topic, payload, data_type, future) = await self._queue.get()
                device_name = self.vacuum_id

                # Generate cache key for larger payloads
                key = None
                payload_len = len(payload)
                if payload_len > 50000:  # Only hash larger payloads
                    payload_hash = hash(payload)
                    key = self._cache_key(topic, data_type, payload_hash)
                    # Check cache first
                    cached = self._results.get(key)
                    if cached:
                        result, timestamp = cached
                        if LOGGER.isEnabledFor(20):  # INFO level
                            LOGGER.info(
                                "%s: Cache hit for %s data",
                                device_name,
                                data_type
                            )
                        future.set_result(result)
                        self._queue.task_done()
                        continue

                try:
                    # Process based on data type
                    if data_type == "Hypfer":
                        # ThreadPoolManager will automatically use optimal worker count for decompression
                        raw = await self._thread_pool.run_in_executor(
                            "decompression",
                            _hypfer_decompress,
                            payload,
                        )

                        result = json.loads(raw)

                        if LOGGER.isEnabledFor(20):  # INFO level
                            LOGGER.info(
                                "%s: Hypfer processing completed",
                                device_name
                            )
                    else:
                        # ThreadPoolManager will automatically use optimal worker count for decompression
                        decompressed = await self._thread_pool.run_in_executor(
                            "decompression",
                            _rand256_decompress,
                            payload,
                        )

                        def _parse_rand256(buf: bytes) -> Any:
                            return self._parser.parse_data(payload=buf, pixels=True)

                        # ThreadPoolManager will automatically use optimal worker count for decompression
                        result = await self._thread_pool.run_in_executor(
                            "decompression",
                            _parse_rand256,
                            decompressed,
                        )

                        if LOGGER.isEnabledFor(20):  # INFO level
                            LOGGER.info(
                                "%s: Rand256 processing completed",
                                device_name
                            )

                    # Cache result in FIFO cache
                    if key:
                        self._results.put(key, result)

                    future.set_result(result)

                    # Log completion in debug mode
                    if LOGGER.isEnabledFor(10):  # DEBUG level
                        LOGGER.debug(
                            "%s: Worker completed %s processing",
                            device_name,
                            data_type
                        )
                except Exception as e:
                    LOGGER.error(
                        "%s: Worker decompression error for %s: %s",
                        device_name,
                        data_type,
                        str(e),
                    )
                    future.set_exception(e)
                finally:
                    self._queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                LOGGER.error("Worker error: %s", str(e))

    async def queue_task(self, topic: str, payload: bytes, data_type: str) -> None:
        """
        Queue a decompression task without waiting for the result.
        This is used when we want to add a task to the queue but not process it immediately.
        Implements strict FIFO ordering with priority queue.
        """
        if not payload:
            return

        # Validate header
        if not await self._validate_compressed_header(payload, data_type):
            return

        device_name = self.vacuum_id

        # Create a future that will never be awaited
        loop = asyncio.get_running_loop()
        future: asyncio.Future = loop.create_future()

        # Use a monotonically increasing counter for strict FIFO ordering
        self._task_counter += 1
        priority = -self._task_counter  # Negative to ensure earlier tasks have higher priority

        # Queue the task with priority
        await self._queue.put((priority, (topic, payload, data_type, future)))

        LOGGER.debug(
            "%s: Queued %s task for later processing. Queue size: %d",
            device_name,
            data_type,
            self._queue.qsize()
        )

    async def decompress(self, topic: str, payload: bytes, data_type: str) -> Any:
        """
        Queue a decompression task and await the JSON result.
        Uses FIFO ordering based on arrival time with efficient caching.
        """
        device_name = self.vacuum_id

        if not payload:
            return None

        # Log the payload size only in debug mode
        payload_len = len(payload)
        if LOGGER.isEnabledFor(10):  # DEBUG level
            LOGGER.debug(
                "%s: Starting decompression of %s data, size: %d bytes",
                device_name,
                data_type,
                payload_len,
            )

        # Fast path: check cache first using hash of payload
        if payload_len > 50000:  # Only hash larger payloads
            payload_hash = hash(payload)
            key = self._cache_key(topic, data_type, payload_hash)
            cached = self._results.get(key)
            if cached:
                result, _ = cached
                if LOGGER.isEnabledFor(20):  # INFO level
                    LOGGER.info(
                        "%s: Cache hit for %s data",
                        device_name,
                        data_type
                    )
                return result

        # Validate header
        if not await self._validate_compressed_header(payload, data_type):
            return None

        # Async path for all payloads - only log in debug mode
        if LOGGER.isEnabledFor(10):  # DEBUG level
            LOGGER.debug(
                "%s: Using async path for %s data",
                device_name,
                data_type
            )

        loop = asyncio.get_running_loop()
        future: asyncio.Future = loop.create_future()

        # Use a monotonically increasing counter for strict FIFO ordering
        # Lower values have higher priority, so we use negative counter
        self._task_counter += 1
        priority = -self._task_counter  # Negative to ensure earlier tasks have higher priority

        # Queue the task with priority
        await self._queue.put((priority, (topic, payload, data_type, future)))

        # Wait for the result
        result = await future

        # Log completion in debug mode
        if LOGGER.isEnabledFor(10):  # DEBUG level
            LOGGER.debug(
                "%s: Async %s processing completed",
                device_name,
                data_type
            )

        return result

    def get_cached(self, topic: str, data_type: str, payload: bytes) -> Optional[Any]:
        """
        Return cached decompressed result if available.
        """
        if len(payload) <= 50000:  # Don't bother with cache for small payloads
            return None

        key = self._cache_key(topic, data_type, hash(payload))
        cached = self._results.get(key)
        return cached[0] if cached else None

    def has_pending_tasks(self) -> bool:
        """
        Check if there are any pending decompression tasks in the queue.

        Returns:
            bool: True if there are tasks waiting to be processed, False otherwise
        """
        return not self._queue.empty()

    def get_pending_tasks_count(self) -> int:
        """
        Get the number of pending decompression tasks in the queue.

        Returns:
            int: The number of tasks waiting to be processed
        """
        return self._queue.qsize()

    def get_queue_status(self) -> Dict[str, Any]:
        """
        Get status information about the decompression queue.

        Returns:
            Dict with queue status information including:
            - pending_tasks: Number of tasks in the queue
            - has_pending: Whether there are any pending tasks
            - cache_entries: Number of cached results
            - cache_max_size: Maximum number of entries in the cache
            - vacuum_id: Vacuum identifier
        """
        return {
            "pending_tasks": self._queue.qsize(),
            "has_pending": not self._queue.empty(),
            "cache_entries": len(self._results),
            "cache_max_size": self._results.get_max_size(),
            "vacuum_id": self.vacuum_id,
        }

    async def shutdown(self) -> None:
        """Shutdown the decompression manager and clean up resources."""
        # Only proceed if this instance is initialized
        if not hasattr(self, "initialized") or not self.initialized:
            LOGGER.debug("DecompressionManager not initialized, skipping shutdown")
            return

        LOGGER.debug("Shutting down DecompressionManager for %s", self.vacuum_id)

        # Cancel all background tasks
        if hasattr(self, "_background_tasks"):
            for task in self._background_tasks:
                if not task.done():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass

            # Clear the background tasks list
            self._background_tasks.clear()

        # No need to shutdown thread pool executor - ThreadPoolManager handles this
        # Just shutdown our specific pools if needed
        if hasattr(self, "_thread_pool"):
            try:
                await self._thread_pool.shutdown("decompression")
            except Exception as e:
                LOGGER.debug("Error shutting down thread pools: %s", e)

        # Clear the FIFO cache
        if hasattr(self, "_results"):
            self._results.clear()

        # Remove this instance from the instances dictionary
        if self.vacuum_id in DecompressionManager._instances:
            del DecompressionManager._instances[self.vacuum_id]

        LOGGER.debug("DecompressionManager shutdown complete for %s", self.vacuum_id)

    async def _initialize_workers(self) -> None:
        """Initialize background workers after a short delay to avoid blocking entity creation."""
        try:
            # Short delay to allow entity creation to complete
            await asyncio.sleep(0.1)

            # Start a single worker for better resource management
            # This is sufficient since we're using a priority queue
            task = asyncio.create_task(self._worker_loop())
            self._background_tasks.append(task)

            # Start cache monitoring task
            task = asyncio.create_task(self._cleanup_cache())
            self._background_tasks.append(task)

            if LOGGER.isEnabledFor(10):  # DEBUG level
                LOGGER.debug(
                    "%s: Initialized workers with FIFO cache (max size: %d)",
                    self.vacuum_id,
                    self._results.get_max_size()
                )
        except Exception as e:
            LOGGER.error("Error initializing workers: %s", e)
