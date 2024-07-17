"""
Version: 2024.07.2
Status text of the vacuum cleaners.
Clas to handle the status text of the vacuum cleaners.
"""

from __future__ import annotations

import json
import logging

from custom_components.mqtt_vacuum_camera.const import DOMAIN
from custom_components.mqtt_vacuum_camera.types import JsonType, PilPNG

_LOGGER = logging.getLogger(__name__)
_LOGGER.propagate = True


class StatusText:
    """
    Status text of the vacuum cleaners.
    """

    def __init__(self, hass, camera_shared):
        self.hass = hass
        self._shared = camera_shared
        self.file_name = self._shared.file_name
        self._translations_path = hass.config.path(
            f"custom_components/{DOMAIN}/translations/"
        )

    def load_translations(self, language: str) -> JsonType:
        """
        Load the user selected language json file and return it.
        @param language:self.hass.config.path(f"custom_components/mqtt_vacuum_camera/translations/
        @return: json format
        """
        file_name = f"{language}.json"
        file_path = f"{self._translations_path}/{file_name}"
        try:
            with open(file_path) as file:
                translations = json.load(file)
        except FileNotFoundError:
            _LOGGER.warning(
                f"{file_path} Not found. Report to the author that {language} is missing."
            )
            return None
        except json.JSONDecodeError:
            _LOGGER.warning(f"{file_path} is not a valid JSON file.")
            return None
        return translations

    def get_vacuum_status_translation(self, language: str) -> any:
        """
        Get the vacuum status translation.
        @param language: String IT, PL, DE, ES, FR, EN.
        @return: Json data or None.
        """
        translations = self.load_translations(language)

        # Check if the translations file is loaded.
        if translations is None:
            return None

        vacuum_status_options = (
            translations.get("selector", {}).get("vacuum_status", {}).get("options", {})
        )
        return vacuum_status_options

    def translate_vacuum_status(self) -> str:
        """Return the translated status."""
        status = self._shared.vacuum_state
        language = self._shared.user_language
        if not language:
            return status.capitalize()
        translations = self.get_vacuum_status_translation(language)
        if translations is not None and status in translations:
            return translations[status]
        else:
            return status.capitalize()

    def get_status_text(self, text_img: PilPNG) -> tuple[list[str], int]:
        """
        Compose the image status text.
        :param text_img: Image to draw the text on.
        :return status_text, text_size: List of the status text and the text size.
        """
        status_text = ["If you read me, something really went wrong.."]  # default text
        text_size_coverage = 1.5  # resize factor for the text
        text_size = self._shared.vacuum_status_size  # default text size
        charge_level = "\u03DE"  # unicode Koppa symbol
        charging = "\u2211"  # unicode Charging symbol
        vacuum_state = self.translate_vacuum_status()
        if self._shared.show_vacuum_state:
            status_text = [f"{self.file_name}: {vacuum_state}"]
            if not self._shared.vacuum_connection:
                status_text = [f"{self.file_name}: Disconnected from MQTT?"]
            else:
                if self._shared.current_room:
                    try:
                        in_room = self._shared.current_room.get("in_room", None)
                    except (ValueError, KeyError):
                        _LOGGER.debug("No in_room data.")
                    else:
                        if in_room:
                            status_text.append(f" ({in_room})")
                if self._shared.vacuum_state == "docked":
                    if int(self._shared.vacuum_battery) <= 99:
                        status_text.append(" \u00B7 ")
                        status_text.append(f"{charging}{charge_level} ")
                        status_text.append(f"{self._shared.vacuum_battery}%")
                        self._shared.vacuum_bat_charged = False
                    else:
                        status_text.append(" \u00B7 ")
                        status_text.append(f"{charge_level} ")
                        status_text.append("Ready.")
                        self._shared.vacuum_bat_charged = True
                else:
                    status_text.append(" \u00B7 ")
                    status_text.append(f"{charge_level}")
                    status_text.append(f" {self._shared.vacuum_battery}%")
                if text_size >= 50:
                    text_pixels = sum(len(text) for text in status_text)
                    text_size = int(
                        (text_size_coverage * text_img.width) // text_pixels
                    )
        return status_text, text_size
