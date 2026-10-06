"""Tests for Valetudo event dismiss propagation in ValetudoConnector."""

from typing import Any, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.mqtt_vacuum_camera.utils.connection.connector import (
    ValetudoConnector,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_connector():
    """Build a ValetudoConnector with minimal mocks."""
    hass = MagicMock()
    hass.async_create_task = MagicMock()

    shared = MagicMock()
    shared.file_name = "test_vacuum"
    shared.camera_mode = MagicMock()

    with patch(
        "custom_components.mqtt_vacuum_camera.utils.connection.connector.RoomStore"
    ):
        connector = ValetudoConnector(
            mqtt_topic="valetudo/TestRobot",
            hass=hass,
            camera_shared=shared,
        )

    return connector


def _make_error_event(event_id, processed=False, message="Test error"):
    return {
        "__class": "ErrorStateValetudoEvent",
        "id": event_id,
        "timestamp": "2026-01-01T00:00:00.000Z",
        "processed": processed,
        "message": message,
        "metaData": {},
    }


def _make_consumable_event(event_id, processed=False):
    return {
        "__class": "ConsumableDepletedValetudoEvent",
        "id": event_id,
        "timestamp": "2026-01-01T00:00:00.000Z",
        "processed": processed,
        "type": "cleaning",
        "subType": "wheel",
        "metaData": {},
    }


# ---------------------------------------------------------------------------
# _hypfer_handle_valetudo_events
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_creates_notification_for_unprocessed_error():
    """An unprocessed ErrorStateValetudoEvent creates a persistent notification."""
    connector = _make_connector()
    events = {"evt-1": _make_error_event("evt-1", processed=False, message="Mop pad failure")}

    with patch(
        "custom_components.mqtt_vacuum_camera.utils.connection.connector.persistent_notification"
    ) as mock_pn:
        mock_pn.async_register_callback.return_value = MagicMock()
        await connector._hypfer_handle_valetudo_events(events)

    mock_pn.async_create.assert_called_once()
    call_kwargs = mock_pn.async_create.call_args
    assert call_kwargs[1]["notification_id"] == "valetudo_error_evt-1"
    assert "Mop pad failure" in call_kwargs[1]["message"]


@pytest.mark.asyncio
async def test_dismisses_ha_notification_when_event_becomes_processed():
    """When Valetudo marks an event processed, the HA notification is dismissed."""
    connector = _make_connector()
    events = {"evt-1": _make_error_event("evt-1", processed=True)}

    with patch(
        "custom_components.mqtt_vacuum_camera.utils.connection.connector.persistent_notification"
    ) as mock_pn:
        await connector._hypfer_handle_valetudo_events(events)

    mock_pn.async_dismiss.assert_called_once_with(
        connector.connector_data.hass,
        notification_id="valetudo_error_evt-1",
    )
    mock_pn.async_create.assert_not_called()


@pytest.mark.asyncio
async def test_ignores_non_error_classes():
    """Non-error event classes that aren't handled don't create notifications."""
    connector = _make_connector()
    events = {"evt-x": _make_consumable_event("evt-x", processed=False)}

    with patch(
        "custom_components.mqtt_vacuum_camera.utils.connection.connector.persistent_notification"
    ) as mock_pn:
        await connector._hypfer_handle_valetudo_events(events)

    mock_pn.async_create.assert_not_called()


@pytest.mark.asyncio
async def test_none_or_empty_events_does_not_notify():
    """None or empty-dict payloads never create/dismiss notifications."""
    connector = _make_connector()
    with patch(
        "custom_components.mqtt_vacuum_camera.utils.connection.connector.persistent_notification"
    ) as mock_pn:
        await connector._hypfer_handle_valetudo_events(None)
        await connector._hypfer_handle_valetudo_events({})

    mock_pn.async_create.assert_not_called()
    mock_pn.async_dismiss.assert_not_called()


# ---------------------------------------------------------------------------
# _register_notification_dismiss_listener
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_listener_registered_only_once_per_notification():
    """Calling register twice for the same notification_id is a no-op the second time."""
    connector = _make_connector()

    with patch(
        "custom_components.mqtt_vacuum_camera.utils.connection.connector.persistent_notification"
    ) as mock_pn:
        mock_pn.async_register_callback.return_value = MagicMock()
        connector._register_notification_dismiss_listener("evt-1", "ok", "valetudo_error_evt-1")
        connector._register_notification_dismiss_listener("evt-1", "ok", "valetudo_error_evt-1")

    assert mock_pn.async_register_callback.call_count == 1


@pytest.mark.asyncio
async def test_listener_unsubscribe_added_to_handlers():
    """The unsubscribe callable from async_register_callback is stored for cleanup."""
    connector = _make_connector()
    mock_unsub = MagicMock()

    with patch(
        "custom_components.mqtt_vacuum_camera.utils.connection.connector.persistent_notification"
    ) as mock_pn:
        mock_pn.async_register_callback.return_value = mock_unsub
        connector._register_notification_dismiss_listener("evt-1", "ok", "valetudo_error_evt-1")

    assert mock_unsub in connector.connector_data.unsubscribe_handlers
    assert connector._notification_listeners["valetudo_error_evt-1"] is mock_unsub


@pytest.mark.asyncio
async def test_removed_callback_dismisses_valetudo_event():
    """When HA dispatches UpdateType.REMOVED for our notification, propagate back to Valetudo."""
    connector = _make_connector()
    # MagicMock (not AsyncMock) — the code passes its return value to the
    # mocked hass.async_create_task which never awaits it; AsyncMock would
    # leak an un-awaited coroutine and emit RuntimeWarning.
    connector._dismiss_valetudo_event = MagicMock()

    captured = []

    def _capture(_hass, cb):
        captured.append(cb)
        return MagicMock()

    with patch(
        "custom_components.mqtt_vacuum_camera.utils.connection.connector.persistent_notification"
    ) as mock_pn:
        mock_pn.async_register_callback.side_effect = _capture
        removed_sentinel = object()
        mock_pn.UpdateType.REMOVED = removed_sentinel

        connector._register_notification_dismiss_listener(
            "evt-1", "ok", "valetudo_error_evt-1"
        )
        assert len(captured) == 1

        # Simulate HA dispatching the removal of our notification
        captured[0](removed_sentinel, {"valetudo_error_evt-1": object()})

    connector._dismiss_valetudo_event.assert_called_once_with("evt-1", "ok")
    # Listener must be cleaned up from both tracking structures to avoid
    # leaking stale entries in connector_data.unsubscribe_handlers.
    assert "valetudo_error_evt-1" not in connector._notification_listeners
    assert connector.connector_data.unsubscribe_handlers == []


@pytest.mark.asyncio
async def test_removed_callback_ignores_other_notifications():
    """REMOVED events for unrelated notification_ids must not trigger dismissal."""
    connector = _make_connector()
    # MagicMock (not AsyncMock) — the code passes its return value to the
    # mocked hass.async_create_task which never awaits it; AsyncMock would
    # leak an un-awaited coroutine and emit RuntimeWarning.
    connector._dismiss_valetudo_event = MagicMock()

    captured = []

    def _capture(_hass, cb):
        captured.append(cb)
        return MagicMock()

    with patch(
        "custom_components.mqtt_vacuum_camera.utils.connection.connector.persistent_notification"
    ) as mock_pn:
        mock_pn.async_register_callback.side_effect = _capture
        removed_sentinel = object()
        added_sentinel = object()
        mock_pn.UpdateType.REMOVED = removed_sentinel
        mock_pn.UpdateType.ADDED = added_sentinel

        connector._register_notification_dismiss_listener(
            "evt-1", "ok", "valetudo_error_evt-1"
        )
        # REMOVED for a different notification id
        captured[0](removed_sentinel, {"something_else": object()})
        # ADDED for our notification id
        captured[0](added_sentinel, {"valetudo_error_evt-1": object()})

    connector._dismiss_valetudo_event.assert_not_called()


@pytest.mark.asyncio
async def test_processed_event_unsubscribes_before_dismissing():
    """When Valetudo marks an event processed, unsubscribe BEFORE async_dismiss to prevent echo-back."""
    connector = _make_connector()
    mock_unsub = MagicMock()

    # First, register a listener as if an unprocessed event arrived earlier.
    with patch(
        "custom_components.mqtt_vacuum_camera.utils.connection.connector.persistent_notification"
    ) as mock_pn:
        mock_pn.async_register_callback.return_value = mock_unsub
        connector._register_notification_dismiss_listener(
            "evt-1", "ok", "valetudo_error_evt-1"
        )
    assert "valetudo_error_evt-1" in connector._notification_listeners

    # Now Valetudo sends processed=True — we must unsubscribe before dismissing.
    events = {"evt-1": _make_error_event("evt-1", processed=True)}
    call_order = []

    with patch(
        "custom_components.mqtt_vacuum_camera.utils.connection.connector.persistent_notification"
    ) as mock_pn:
        mock_unsub.side_effect = lambda: call_order.append("unsubscribe")
        mock_pn.async_dismiss.side_effect = lambda *a, **kw: call_order.append("dismiss")
        await connector._hypfer_handle_valetudo_events(events)

    assert call_order == ["unsubscribe", "dismiss"]
    assert "valetudo_error_evt-1" not in connector._notification_listeners


@pytest.mark.asyncio
async def test_full_flow_user_dismisses_in_ha_publishes_to_valetudo():
    """End-to-end: unprocessed event → HA dismissal → MQTT interact publish.

    Exercises the full code path without mocking _dismiss_valetudo_event:
      1. Valetudo publishes an unprocessed ErrorStateValetudoEvent.
      2. _hypfer_handle_valetudo_events creates the notification and registers
         a real dismissal listener.
      3. User dismisses the notification in HA (simulated by invoking the
         captured dispatcher callback with UpdateType.REMOVED).
      4. The scheduled _dismiss_valetudo_event runs and must publish an
         interact command with the exact payload Valetudo expects.
    """
    connector = _make_connector()
    connector.publish_to_broker = AsyncMock()

    # Collect coroutines scheduled via hass.async_create_task so we can await them.
    scheduled_coros: List[Any] = []
    connector.connector_data.hass.async_create_task = lambda coro: scheduled_coros.append(coro)

    captured_callbacks: List[Any] = []

    def _capture(_hass, cb):
        captured_callbacks.append(cb)
        return MagicMock()

    # Step 1–2: Valetudo sends an unprocessed error.
    events = {"evt-42": _make_error_event("evt-42", processed=False, message="Brush stuck")}
    with patch(
        "custom_components.mqtt_vacuum_camera.utils.connection.connector.persistent_notification"
    ) as mock_pn:
        mock_pn.async_register_callback.side_effect = _capture
        removed_sentinel = object()
        mock_pn.UpdateType.REMOVED = removed_sentinel

        await connector._hypfer_handle_valetudo_events(events)

        # Notification created for the user.
        mock_pn.async_create.assert_called_once()
        assert mock_pn.async_create.call_args.kwargs["notification_id"] == "valetudo_error_evt-42"

        # A listener was registered with HA's dispatcher.
        assert len(captured_callbacks) == 1
        ha_callback = captured_callbacks[0]

        # Step 3: user dismisses the notification in HA — HA dispatches REMOVED.
        ha_callback(removed_sentinel, {"valetudo_error_evt-42": object()})

    # The callback scheduled _dismiss_valetudo_event; await the real coroutine.
    assert len(scheduled_coros) == 1
    await scheduled_coros[0]

    # Step 4: MQTT interact command actually published with correct payload.
    connector.publish_to_broker.assert_awaited_once_with(
        "valetudo/TestRobot/ValetudoEvents/valetudo_events/interact/set",
        {"id": "evt-42", "interaction": "ok"},
    )

    # And the listener tracking is fully cleaned up.
    assert "valetudo_error_evt-42" not in connector._notification_listeners
    assert connector.connector_data.unsubscribe_handlers == []


@pytest.mark.asyncio
async def test_full_flow_dismissal_in_valetudo_does_not_echo_to_mqtt():
    """End-to-end: when Valetudo-side dismissal arrives (processed=True),
    the HA notification is dismissed but NO MQTT interact is published.

    This exercises the echo-back prevention: unsubscribe fires before
    async_dismiss, so HA's own REMOVED dispatch doesn't retrigger the
    callback that would republish to Valetudo.

    Simulates HA's dispatcher faithfully: callbacks live in a list, the
    returned unsubscribe removes them from that list, and async_dismiss
    dispatches only to callbacks still registered at the time.
    """
    connector = _make_connector()
    connector.publish_to_broker = AsyncMock()

    scheduled_coros: List[Any] = []
    connector.connector_data.hass.async_create_task = lambda coro: scheduled_coros.append(coro)

    # Faithful HA dispatcher simulation.
    dispatcher: List[Any] = []
    removed_sentinel = object()

    def _register(_hass, cb):
        dispatcher.append(cb)

        def _unsubscribe():
            if cb in dispatcher:
                dispatcher.remove(cb)

        return _unsubscribe

    def _dispatch_removed(notification_id: str) -> None:
        """Invoke all currently-registered callbacks, like HA would."""
        for cb in list(dispatcher):
            cb(removed_sentinel, {notification_id: object()})

    # Arm: unprocessed event arrives first so a listener is registered.
    unprocessed = {"evt-7": _make_error_event("evt-7", processed=False, message="Filter clog")}
    with patch(
        "custom_components.mqtt_vacuum_camera.utils.connection.connector.persistent_notification"
    ) as mock_pn:
        mock_pn.async_register_callback.side_effect = _register
        mock_pn.UpdateType.REMOVED = removed_sentinel
        # In real HA, async_dismiss would trigger the dispatcher. Wire that up.
        mock_pn.async_dismiss.side_effect = lambda _hass, notification_id: _dispatch_removed(
            notification_id
        )

        await connector._hypfer_handle_valetudo_events(unprocessed)
        assert len(dispatcher) == 1, "listener should be in the dispatcher"

        # Simulate Valetudo-side dismissal: processed=True arrives.
        processed = {"evt-7": _make_error_event("evt-7", processed=True)}
        await connector._hypfer_handle_valetudo_events(processed)

    # async_dismiss fired the dispatcher, but our callback was already gone
    # because _unsubscribe_notification_listener ran first — no echo.
    assert dispatcher == [], "listener should have been removed before async_dismiss"
    assert scheduled_coros == [], "no _dismiss_valetudo_event should have been scheduled"
    connector.publish_to_broker.assert_not_called()


@pytest.mark.asyncio
async def test_empty_events_dict_clears_stale_events():
    """An empty-dict payload must overwrite previously stored events (not be ignored)."""
    connector = _make_connector()
    connector.mqtt_data.valetudo_events = {"stale": {"__class": "ErrorStateValetudoEvent"}}

    with patch(
        "custom_components.mqtt_vacuum_camera.utils.connection.connector.persistent_notification"
    ):
        await connector._hypfer_handle_valetudo_events({})

    assert connector.mqtt_data.valetudo_events == {}


@pytest.mark.asyncio
async def test_dismisses_ha_notification_when_event_disappears_from_payload():
    """Valetudo only publishes unprocessed events, so a dismissed one just vanishes."""
    connector = _make_connector()
    connector.publish_to_broker = AsyncMock()
    scheduled_coros: List[Any] = []
    connector.connector_data.hass.async_create_task = lambda coro: scheduled_coros.append(coro)

    with patch(
        "custom_components.mqtt_vacuum_camera.utils.connection.connector.persistent_notification"
    ) as mock_pn:
        unsub = MagicMock()
        mock_pn.async_register_callback.return_value = unsub
        await connector._hypfer_handle_valetudo_events(
            {"evt-1": _make_error_event("evt-1", processed=False)}
        )
        mock_pn.async_dismiss.assert_not_called()

        # Dismissed on the vacuum: the event is no longer in the payload.
        await connector._hypfer_handle_valetudo_events({})

    mock_pn.async_dismiss.assert_called_once_with(
        connector.connector_data.hass,
        notification_id="valetudo_error_evt-1",
    )
    unsub.assert_called_once()
    assert connector._notification_listeners == {}
    assert scheduled_coros == []
    connector.publish_to_broker.assert_not_called()


@pytest.mark.asyncio
async def test_still_active_event_is_not_dismissed_by_other_event_leaving():
    """Only the notification whose event left the payload is dismissed."""
    connector = _make_connector()

    with patch(
        "custom_components.mqtt_vacuum_camera.utils.connection.connector.persistent_notification"
    ) as mock_pn:
        mock_pn.async_register_callback.return_value = MagicMock()
        await connector._hypfer_handle_valetudo_events(
            {
                "evt-1": _make_error_event("evt-1", processed=False),
                "evt-2": _make_error_event("evt-2", processed=False),
            }
        )
        await connector._hypfer_handle_valetudo_events(
            {"evt-2": _make_error_event("evt-2", processed=False)}
        )

    mock_pn.async_dismiss.assert_called_once_with(
        connector.connector_data.hass,
        notification_id="valetudo_error_evt-1",
    )
    assert list(connector._notification_listeners) == ["valetudo_error_evt-2"]


@pytest.mark.asyncio
async def test_user_dismiss_in_ha_still_publishes_and_later_payload_is_noop():
    """HA dismissal publishes to Valetudo; the follow-up payload without the event does nothing."""
    connector = _make_connector()
    connector.publish_to_broker = AsyncMock()
    scheduled_coros: List[Any] = []
    connector.connector_data.hass.async_create_task = lambda coro: scheduled_coros.append(coro)

    callbacks: List[Any] = []
    removed_sentinel = object()

    with patch(
        "custom_components.mqtt_vacuum_camera.utils.connection.connector.persistent_notification"
    ) as mock_pn:
        mock_pn.async_register_callback.side_effect = lambda _hass, cb: (
            callbacks.append(cb) or MagicMock()
        )
        mock_pn.UpdateType.REMOVED = removed_sentinel
        await connector._hypfer_handle_valetudo_events(
            {"evt-9": _make_error_event("evt-9", processed=False)}
        )

        # User dismisses the notification in HA.
        callbacks[0](removed_sentinel, {"valetudo_error_evt-9": object()})
        assert len(scheduled_coros) == 1
        await scheduled_coros[0]

        # Valetudo processes the interaction and republishes without the event.
        await connector._hypfer_handle_valetudo_events({})

    connector.publish_to_broker.assert_called_once_with(
        "valetudo/TestRobot/ValetudoEvents/valetudo_events/interact/set",
        {"id": "evt-9", "interaction": "ok"},
    )
    mock_pn.async_dismiss.assert_not_called()


# ---------------------------------------------------------------------------
# _dismiss_valetudo_event
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dismiss_publishes_to_mqtt_interact_topic():
    """_dismiss_valetudo_event publishes the correct payload to the MQTT interact topic."""
    connector = _make_connector()
    connector.publish_to_broker = AsyncMock()

    await connector._dismiss_valetudo_event("evt-1", "ok")

    connector.publish_to_broker.assert_called_once_with(
        "valetudo/TestRobot/ValetudoEvents/valetudo_events/interact/set",
        {"id": "evt-1", "interaction": "ok"},
    )


@pytest.mark.asyncio
async def test_dismiss_uses_correct_interaction_per_event_type():
    """Different interaction values are forwarded as-is to the MQTT topic."""
    connector = _make_connector()
    connector.publish_to_broker = AsyncMock()

    await connector._dismiss_valetudo_event("consumable-1", "reset")

    connector.publish_to_broker.assert_called_once_with(
        "valetudo/TestRobot/ValetudoEvents/valetudo_events/interact/set",
        {"id": "consumable-1", "interaction": "reset"},
    )
