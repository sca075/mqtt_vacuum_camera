"""
Vacuum State Manager for MQTT Vacuum Camera.
Version: 2025.6.0
"""

from __future__ import annotations

from valetudo_map_parser.config.types import LOGGER

from ...const import NOT_STREAMING_STATES
from ...utils.connection.connector import ValetudoConnector
from valetudo_map_parser.config.shared import CameraShared


class VacuumStateManager:
    """Manages vacuum state and streaming logic."""

    def __init__(
        self, shared_data: CameraShared, connector: ValetudoConnector, file_name: str
    ):
        """Initialize the vacuum state manager."""
        self.shared = shared_data
        self.connector = connector
        self.file_name = file_name

    async def update_vacuum_state(self) -> bool:
        """
        Update vacuum state and return streaming decision.

        Returns:
            bool: True if camera should stream, False if is idle
        """
        try:
            # Update battery level
            self.shared.vacuum_battery = await self.connector.get_battery_level()

            # Update connection state
            self.shared.vacuum_connection = (
                await self.connector.get_vacuum_connection_state()
            )

            # Update vacuum status
            if self.shared.vacuum_connection:
                self.shared.vacuum_state = await self.connector.get_vacuum_status()
            else:
                self.shared.vacuum_state = "disconnected"

            # Return streaming decision
            return self.should_stream()

        except Exception as err:
            LOGGER.error("Error updating vacuum state for %s: %s", self.file_name, err)
            return False

    def should_stream(self) -> bool:
        """Determine if camera should stream based on vacuum state."""
        if not self.shared.vacuum_connection:
            return False

        current_status = self.shared.vacuum_state
        state_changed = current_status not in NOT_STREAMING_STATES or (
            current_status == "docked" and not self.shared.vacuum_bat_charged
        )
        if state_changed:
            self.shared.image_grab = True
            self.shared.snapshot_take = False

        # Streaming logic from original camera.py
        return current_status not in NOT_STREAMING_STATES or (
            current_status == "docked" and not self.shared.vacuum_bat_charged
        )
