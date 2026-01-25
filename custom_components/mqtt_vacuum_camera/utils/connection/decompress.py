"""
Decompression Manager for MQTT Vacuum Camera.
Version: 2025.10.0
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

from isal import igzip, isal_zlib  # pylint: disable=c-extension-no-member
from valetudo_map_parser.config.rand256_parser import RRMapParser

from custom_components.mqtt_vacuum_camera.const import LOGGER
from custom_components.mqtt_vacuum_camera.utils.thread_pool import (
    DECOMPRESSION_THREAD_POOL,
    ThreadPoolManager,
)


def _safe_zlib_decompress(data: bytes) -> str:
    """Decompress Hypfer payload using zlib."""
    try:
        return isal_zlib.decompress(data).decode()
    except Exception as e:
        raise ValueError(f"Invalid Hypfer payload: {e}") from e


def _safe_gzip_decompress(data: bytes) -> bytes:
    """Decompress Rand256 payload using gzip."""
    try:
        return igzip.decompress(data)
    except Exception as e:
        raise ValueError(f"Invalid Rand256 payload: {e}") from e


class DecompressionManager:
    """
    Manages decompression of MQTT payloads for vacuum map data.
    Singleton per vacuum_id to ensure thread pool reuse.
    """

    __slots__ = ("vacuum_id", "_thread_pool", "_parser")

    _instances: Dict[str, DecompressionManager] = {}

    def __new__(cls, vacuum_id: str) -> DecompressionManager:
        """Create or return existing instance for the given vacuum_id."""
        if vacuum_id not in cls._instances:
            instance = super().__new__(cls)
            cls._instances[vacuum_id] = instance
        return cls._instances[vacuum_id]

    def __init__(self, vacuum_id: str) -> None:
        """Initialize the decompression manager (only runs once per vacuum_id)."""
        # Skip initialization if already initialized
        if hasattr(self, "vacuum_id"):
            return

        self.vacuum_id = vacuum_id
        self._thread_pool = ThreadPoolManager(vacuum_id)
        self._parser = RRMapParser()
        LOGGER.debug("Initialized DecompressionManager for vacuum: %s", vacuum_id)

    @classmethod
    def get_instance(cls, vacuum_id: str) -> DecompressionManager:
        """Get or create a DecompressionManager instance for the given vacuum_id."""
        return cls(vacuum_id)

    async def decompress(
        self, payload: Optional[bytes] = None, data_type: Optional[str] = None
    ) -> Optional[Any]:
        """
        Decompress and parse vacuum map binary payload data into JSON.
        """
        if not payload:
            return None

        # Extract payload if it's a message object
        if hasattr(payload, "payload"):
            payload = payload.payload

        # Process the payload based on data type
        try:
            if data_type == "Hypfer":
                raw = await self._thread_pool.run_in_executor(
                    DECOMPRESSION_THREAD_POOL, _safe_zlib_decompress, payload
                )
                return json.loads(raw)

            if data_type == "Rand256":
                decompressed = await self._thread_pool.run_in_executor(
                    DECOMPRESSION_THREAD_POOL, _safe_gzip_decompress, payload
                )
                return await self._thread_pool.run_in_executor(
                    DECOMPRESSION_THREAD_POOL,
                    self._parser.parse_data,
                    decompressed,
                    True,
                )

            LOGGER.warning("%s: Unknown data type: %s", self.vacuum_id, data_type)
            return None
        except (ValueError, json.JSONDecodeError) as e:
            LOGGER.warning("%s: Invalid payload: %s", self.vacuum_id, e)
            return None
