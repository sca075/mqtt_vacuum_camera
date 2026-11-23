"""Zone clean payloads include every selected rectangle."""

from custom_components.mqtt_vacuum_camera.utils.vacuum.mqtt_vacuum_services import (
    generate_zone_payload,
)


def test_valetudo_zone_payload_includes_every_rectangle():
    """Hypfer Valetudo payloads list each rectangle, not only the first."""
    payload = generate_zone_payload(
        [[1, 2, 3, 4], [10, 20, 30, 40]],
        repeat=2,
        is_rand256=False,
    )

    assert payload["iterations"] == 2
    assert payload["zones"] == [
        {
            "points": {
                "pA": {"x": 1, "y": 2},
                "pB": {"x": 3, "y": 2},
                "pC": {"x": 3, "y": 4},
                "pD": {"x": 1, "y": 4},
            }
        },
        {
            "points": {
                "pA": {"x": 10, "y": 20},
                "pB": {"x": 30, "y": 20},
                "pC": {"x": 30, "y": 40},
                "pD": {"x": 10, "y": 40},
            }
        },
    ]


def test_rand256_zone_payload_includes_every_rectangle():
    """Rand256 coordinate payloads list each rectangle, not only the first."""
    payload = generate_zone_payload(
        [[1, 2, 3, 4], [10, 20, 30, 40]],
        repeat=1,
        is_rand256=True,
    )

    assert payload == {
        "command": "zoned_cleanup",
        "zone_coordinates": [
            {"x1": 1, "y1": 2, "x2": 3, "y2": 4, "repeats": 1},
            {"x1": 10, "y1": 20, "x2": 30, "y2": 40, "repeats": 1},
        ],
    }
