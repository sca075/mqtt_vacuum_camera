"""
Decompression Manager for MQTT Vacuum Camera.
Version: 2025.5.0
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, Optional

from isal import igzip, isal_zlib  # pylint: disable=I1101
from valetudo_map_parser.config.rand25_parser import RRMapParser

from custom_components.mqtt_vacuum_camera.const import LOGGER
from custom_components.mqtt_vacuum_camera.utils.thread_pool import ThreadPoolManager


def _safe_zlib_decompress(data: bytes) -> str:
    try:
        return isal_zlib.decompress(data).decode()
    except Exception as e:
        raise ValueError(f"Invalid Hypfer payload: {e}")


def _safe_gzip_decompress(data: bytes) -> bytes:
    try:
        return igzip.decompress(data)
    except Exception as e:
        raise ValueError(f"Invalid Rand256 payload: {e}")


class DecompressionManager:
    __slots__ = ("vacuum_id", "_thread_pool", "_parser", "_last_payload")

    _instances: Dict[str, DecompressionManager] = {}

    @classmethod
    def get_instance(cls, vacuum_id: str) -> DecompressionManager:
        if vacuum_id not in cls._instances:
            instance = super().__new__(cls)
            instance._init(vacuum_id)
            cls._instances[vacuum_id] = instance
        return cls._instances[vacuum_id]

    def _init(self, vacuum_id: str) -> None:
        self.vacuum_id = vacuum_id
        self._thread_pool = ThreadPoolManager(vacuum_id)
        self._parser = RRMapParser()
        LOGGER.debug(f"Initialized DecompressionManager for vacuum: {vacuum_id}")

    async def decompress(
        self, topic: str = None, payload: bytes = None, data_type: str = None
    ) -> Optional[Any]:
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
            elif data_type == "Rand256":
                decompressed = await self._thread_pool.run_in_executor(
                    "decompression", _safe_gzip_decompress, payload
                )
                return await self._thread_pool.run_in_executor(
                    "decompression", self._parser.parse_data, decompressed, True
                )
            else:
                LOGGER.warning(f"{self.vacuum_id}: Unknown data type: {data_type}")
                return None
        except Exception as e:
            LOGGER.error(f"{self.vacuum_id}: Error processing payload: {e}")
            return None

    async def shutdown(self) -> None:
        await self._thread_pool.shutdown("decompression")
        if self.vacuum_id in DecompressionManager._instances:
            del DecompressionManager._instances[self.vacuum_id]
