"""
Vacuum State Manager for MQTT Vacuum Camera.
Version: 2025.6.0
"""

from __future__ import annotations

from valetudo_map_parser.config.shared import CameraShared
from valetudo_map_parser.config.types import LOGGER

from ...const import NOT_STREAMING_STATES
from ...utils.connection.connector import ValetudoConnector


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

        vacuum_status = self.shared.vacuum_state
        stream_state_changed = vacuum_status not in NOT_STREAMING_STATES or (
            vacuum_status == "docked" and not self.shared.vacuum_bat_charged
        )
        if stream_state_changed:
            self.shared.image_grab = True
            self.shared.snapshot_take = False

        return stream_state_changed
