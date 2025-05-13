import asyncio
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from typing import Any, Dict, Optional, Tuple, Callable

from isal import igzip, isal_zlib  # pylint: disable=I1101
from valetudo_map_parser.config.rand25_parser import RRMapParser
from valetudo_map_parser.config.types import LOGGER

class DecompressionManager:
    """
    Singleton manager for decompressing MQTT map payloads with header validation
    and synchronous short-circuit for small payloads.
    """
    _instance: Optional["DecompressionManager"] = None

    # Increased thresholds for synchronous processing to handle more payloads directly
    SYNC_HYPFER_THRESHOLD = 100_000  # Increased from 50_000
    SYNC_RAND256_THRESHOLD = 150_000  # Increased from 100_000

    # Cache size for recently processed payloads
    CACHE_SIZE = 10

    # Maximum number of concurrent decompression tasks
    MAX_CONCURRENT_TASKS = 4

    def __new__(cls) -> "DecompressionManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if hasattr(self, "initialized"):
            return
        self.initialized = True

        # Optimize thread pool size based on workload type
        cpu = os.cpu_count() or 1
        max_workers = min(max(2, cpu), 8)  # At least 2, at most 8 workers
        self._executor = ThreadPoolExecutor(max_workers=max_workers)

        # Pre-initialize parser to avoid initialization delay during first use
        self._parser = RRMapParser()

        # Use a priority queue for better task management
        self._queue: asyncio.PriorityQueue = asyncio.PriorityQueue()

        # Results cache with timestamp for expiration
        self._results: Dict[str, Tuple[Any, float]] = {}

        # Cache expiration time (10 minutes)
        self._cache_expiry = 600

        # Track active tasks to limit concurrency
        self._active_tasks = 0
        self._task_semaphore = asyncio.Semaphore(self.MAX_CONCURRENT_TASKS)

        # Start background workers
        for _ in range(2):  # Multiple workers for better throughput
            asyncio.create_task(self._worker_loop())

        # Start cache cleanup task
        asyncio.create_task(self._cleanup_cache())

    @classmethod
    def get_instance(cls) -> "DecompressionManager":
        return cls()

    @lru_cache(maxsize=32)
    def _cache_key(self, topic: str, data_type: str, payload_hash: int) -> str:
        """Generate a cache key with LRU caching to avoid repeated string operations."""
        return f"{topic}:{data_type}:{payload_hash}"

    def _validate_header(self, payload: bytes, data_type: str) -> bool:
        """
        Validate compressed payload headers with minimal overhead.
        """
        try:
            # Fast path checks with minimal operations
            if not payload or len(payload) < 2:
                return False

            if data_type == "Hypfer":
                if not payload.startswith(b"\x78\x9c"):
                    raise ValueError("Invalid isal-zlib header")
                # Validate zlib header checksum
                if (payload[0] * 256 + payload[1]) % 31 != 0:
                    raise ValueError("Invalid isal-zlib header checksum")

            elif data_type == "Rand256":
                if not payload.startswith(b"\x1f\x8b"):
                    raise ValueError("Invalid gzip header")
        except Exception as e:
            LOGGER.warning("Header validation error for %s: %s", data_type, e)
            return False
        return True

    async def _cleanup_cache(self) -> None:
        """Periodically clean up expired cache entries."""
        while True:
            try:
                await asyncio.sleep(60)  # Check every minute
                now = time.time()
                expired_keys = [k for k, (_, timestamp) in self._results.items()
                               if now - timestamp > self._cache_expiry]

                for key in expired_keys:
                    del self._results[key]

                if expired_keys:
                    LOGGER.debug("Cleaned up %d expired cache entries", len(expired_keys))
            except Exception as e:
                LOGGER.error("Error in cache cleanup: %s", e)

    async def _worker_loop(self) -> None:
        """
        Consume tasks: each is (priority, (topic, payload, data_type, future)).
        """
        loop = asyncio.get_running_loop()

        # Pre-compile lambda functions to avoid recreation on each iteration
        hypfer_decompress: Callable = lambda p: isal_zlib.decompress(p).decode()
        rand256_decompress: Callable = lambda p: igzip.decompress(p)

        while True:
            try:
                # Get next task with priority
                _, (topic, payload, data_type, future) = await self._queue.get()
                device_name = topic.split('/')[-1] if '/' in topic else topic
                worker_start_time = time.time()

                # Limit concurrent tasks
                async with self._task_semaphore:
                    self._active_tasks += 1

                    try:
                        # Calculate cache key only once
                        payload_len = len(payload)
                        payload_hash = hash(payload)
                        key = self._cache_key(topic, data_type, payload_hash) if payload_len > 50000 else ""

                        # Check cache first
                        if key and key in self._results:
                            LOGGER.info(
                                "%s: TIMING - Worker cache hit for %s data",
                                device_name, data_type
                            )
                            result, _ = self._results[key]
                            future.set_result(result)
                            continue

                        # Process based on data type
                        if data_type == "Hypfer":
                            # Time the decompression step
                            decompress_start_time = time.time()
                            raw = await loop.run_in_executor(self._executor, hypfer_decompress, payload)
                            decompress_time = time.time() - decompress_start_time

                            # Time the JSON parsing step
                            json_start_time = time.time()
                            result = json.loads(raw)
                            json_time = time.time() - json_start_time

                            LOGGER.info(
                                "%s: TIMING - Worker Hypfer processing: decompress=%.3fs, json=%.3fs",
                                device_name, decompress_time, json_time
                            )
                        else:
                            # Time the decompression step
                            decompress_start_time = time.time()
                            decompressed = await loop.run_in_executor(self._executor, rand256_decompress, payload)
                            decompress_time = time.time() - decompress_start_time

                            # Time the parsing step
                            parse_start_time = time.time()
                            parse_func = lambda: self._parser.parse_data(payload=decompressed, pixels=True)
                            result = await loop.run_in_executor(self._executor, parse_func)
                            parse_time = time.time() - parse_start_time

                            LOGGER.info(
                                "%s: TIMING - Worker Rand256 processing: decompress=%.3fs, parse=%.3fs",
                                device_name, decompress_time, parse_time
                            )

                        # Cache result with timestamp
                        if key:
                            self._results[key] = (result, time.time())

                        future.set_result(result)

                        # Log total worker time
                        total_worker_time = time.time() - worker_start_time
                        LOGGER.info(
                            "%s: TIMING - Worker completed %s processing in %.3fs",
                            device_name, data_type, total_worker_time
                        )
                    except Exception as e:
                        LOGGER.error(
                            "%s: Worker decompression error for %s: %s",
                            device_name, data_type, str(e)
                        )
                        future.set_exception(e)
                    finally:
                        self._active_tasks -= 1
                        self._queue.task_done()
            except Exception as e:
                LOGGER.error("Worker error: %s", str(e))

    async def decompress(
        self, topic: str, payload: bytes, data_type: str
    ) -> Any:
        """
        Queue a decompression task (with optional sync short-circuit) and await the JSON result.
        """
        # Start timing the entire decompression process
        overall_start_time = time.time()
        device_name = topic.split('/')[-1] if '/' in topic else topic

        if not payload:
            return None

        # Log the payload size
        payload_len = len(payload)
        LOGGER.info(
            "%s: TIMING - Starting decompression of %s data, size: %d bytes",
            device_name, data_type, payload_len
        )

        # Fast path: check cache first using hash of payload
        if payload_len > 50000:  # Only hash larger payloads
            payload_hash = hash(payload)
            key = self._cache_key(topic, data_type, payload_hash)
            cached = self._results.get(key)
            if cached:
                result, _ = cached
                LOGGER.info(
                    "%s: TIMING - Cache hit for %s data",
                    device_name, data_type
                )
                return result

        # Validate header
        if not self._validate_header(payload, data_type):
            return None

        # Synchronous fast path for small payloads
        if data_type == "Hypfer" and payload_len <= self.SYNC_HYPFER_THRESHOLD:
            try:
                # Time the decompression step
                decompress_start_time = time.time()
                raw = isal_zlib.decompress(payload).decode()
                decompress_time = time.time() - decompress_start_time

                # Time the JSON parsing step
                json_start_time = time.time()
                result = json.loads(raw)
                json_time = time.time() - json_start_time

                total_time = time.time() - overall_start_time
                LOGGER.info(
                    "%s: TIMING - Sync Hypfer processing: total=%.3fs, decompress=%.3fs, json=%.3fs",
                    device_name, total_time, decompress_time, json_time
                )
                return result
            except Exception as e:
                LOGGER.error(
                    "%s: Sync Hypfer decompression error: %s",
                    device_name, str(e)
                )
                return None

        if data_type != "Hypfer" and payload_len <= self.SYNC_RAND256_THRESHOLD:
            try:
                # Time the decompression step
                decompress_start_time = time.time()
                decompressed = igzip.decompress(payload)
                decompress_time = time.time() - decompress_start_time

                # Time the parsing step
                parse_start_time = time.time()
                result = self._parser.parse_data(payload=decompressed, pixels=True)
                parse_time = time.time() - parse_start_time

                total_time = time.time() - overall_start_time
                LOGGER.info(
                    "%s: TIMING - Sync Rand256 processing: total=%.3fs, decompress=%.3fs, parse=%.3fs",
                    device_name, total_time, decompress_time, parse_time
                )
                return result
            except Exception as e:
                LOGGER.error(
                    "%s: Sync Rand256 decompression error: %s",
                    device_name, str(e)
                )
                return None

        # Async path for larger payloads
        LOGGER.info(
            "%s: TIMING - Using async path for %s data (size: %d bytes)",
            device_name, data_type, payload_len
        )

        loop = asyncio.get_running_loop()
        future: asyncio.Future = loop.create_future()

        # Use priority based on payload size (smaller = higher priority)
        priority = payload_len

        # Queue the task with priority
        await self._queue.put((priority, (topic, payload, data_type, future)))

        # Wait for the result
        wait_start_time = time.time()
        result = await future
        wait_time = time.time() - wait_start_time

        # Log the total time
        total_time = time.time() - overall_start_time
        LOGGER.info(
            "%s: TIMING - Async %s processing: total=%.3fs, wait=%.3fs",
            device_name, data_type, total_time, wait_time
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
