"""
Decompression Manager for MQTT Vacuum Camera.
Version: 2025.8.0
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

from isal import igzip, isal_zlib  # pylint disable=I1101
from valetudo_map_parser import RRMapParser

from custom_components.mqtt_vacuum_camera.const import LOGGER
from custom_components.mqtt_vacuum_camera.utils.thread_pool import ThreadPoolManager


def _safe_zlib_decompress(data: bytes) -> str:
    """Decompress data using zlib."""
    try:
        return isal_zlib.decompress(data).decode()
    except ValueError as e:
        raise ValueError("Invalid Hypfer payload:") from e


def _safe_gzip_decompress(data: bytes) -> bytes:
    """Decompress data using gzip."""
    try:
        return igzip.decompress(data)
    except ValueError as e:
        raise ValueError("Invalid Rand256 payload:") from e


class DecompressionManager:
    """
    A singleton class that manages decompression operations for different vacuums.
    """

    __slots__ = ("vacuum_id", "_thread_pool", "_parser", "_last_payload")

    _instances: Dict[str, DecompressionManager] = {}

    @classmethod
    def get_instance(cls, vacuum_id: str) -> DecompressionManager:
        """Get the singleton instance of DecompressionManager for a specific vacuum."""
        if vacuum_id not in cls._instances:
            instance = super().__new__(cls)
            instance._init(vacuum_id)
            cls._instances[vacuum_id] = instance
        return cls._instances[vacuum_id]

    def _init(self, vacuum_id: str) -> None:
        """Initialize the DecompressionManager."""
        self.vacuum_id = vacuum_id
        self._thread_pool = ThreadPoolManager(vacuum_id)
        self._parser = RRMapParser()
        LOGGER.debug("Initialized DecompressionManager for vacuum %s:", vacuum_id)

    async def decompress(
        self, payload: bytes = None, data_type: str = None
    ) -> Optional[Any] | None:
        """Process a payload and return the result."""
        # If no parameters provided, use the last stored payload
        # If no payload, return None
        if not payload:
            return None

        # Extract payload if it's a message object
        if hasattr(payload, "payload"):
            payload = payload.payload

        # Process the payload based on data type
        try:
            if data_type == "Hypfer":
                raw = await self._thread_pool.run_in_executor(
                    "decompression", _safe_zlib_decompress, payload
                )
                return json.loads(raw)
            # elif data_type == "Rand256":
            decompressed = await self._thread_pool.run_in_executor(
                "decompression", _safe_gzip_decompress, payload
            )
            return await self._thread_pool.run_in_executor(
                "decompression", self._parser.parse_data, decompressed, True
            )
        except (EOFError, isal_zlib.error, igzip.igzip_lib.error) as e:  # pylint: disable=I1101
            LOGGER.error("%s: Error processing payload: %s", self.vacuum_id, e)
            return None
