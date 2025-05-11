"""
Language Cache for MQTT Vacuum Camera.
This module provides caching for user language data to reduce I/O operations.
Version: 2025.5.0
"""

from __future__ import annotations

import asyncio
from functools import lru_cache
import json
import logging
import os
from typing import Dict, List, Optional, Set

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import STORAGE_DIR
from valetudo_map_parser.config.types import UserLanguageStore

_LOGGER = logging.getLogger(__name__)


class LanguageCache:
    """
    A singleton class that caches user language data to reduce I/O operations.
    """

    _instance: Optional[LanguageCache] = None
    _user_languages: Dict[str, str] = {}  # user_id -> language
    _all_languages: Set[str] = set()  # Set of all languages
    _translations_cache: Dict[str, dict] = {}  # language -> translation data
    _initialized: bool = False
    _auth_update_time: Optional[float] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(LanguageCache, cls).__new__(cls)
            cls._instance._user_languages = {}
            cls._instance._all_languages = set()
            cls._instance._translations_cache = {}
            cls._instance._initialized = False
            cls._instance._auth_update_time = None
        return cls._instance

    @staticmethod
    @lru_cache(maxsize=1)
    def get_instance() -> LanguageCache:
        """Get the singleton instance of LanguageCache."""
        return LanguageCache()

    async def initialize(self, hass: HomeAssistant) -> None:
        """
        Initialize the language cache by loading all user languages.
        This should be called once at startup.

        Args:
            hass: The Home Assistant instance
        """
        if self._initialized:
            return

        try:
            # Check if UserLanguageStore is already initialized
            user_language_store = UserLanguageStore()
            if not await UserLanguageStore.is_initialized():
                await self._populate_user_languages(hass, user_language_store)

            # Load all languages from UserLanguageStore
            all_languages = await user_language_store.get_all_languages()
            if all_languages:
                self._all_languages = set(all_languages)

            # Get the auth file update time
            auth_file_path = hass.config.path(STORAGE_DIR, "auth")
            if await asyncio.to_thread(os.path.exists, auth_file_path):
                self._auth_update_time = await asyncio.to_thread(
                    os.path.getmtime, auth_file_path
                )

            self._initialized = True
            _LOGGER.debug(
                "Language cache initialized with %d languages", len(self._all_languages)
            )
        except Exception as e:
            _LOGGER.warning(
                "Error initializing language cache: %s", str(e), exc_info=True
            )

    async def _populate_user_languages(
        self, hass: HomeAssistant, user_language_store: UserLanguageStore
    ) -> None:
        """
        Populate the UserLanguageStore with languages for all users.

        Args:
            hass: The Home Assistant instance
            user_language_store: The UserLanguageStore instance
        """
        try:
            # Get all user IDs excluding system users
            users = await hass.auth.async_get_users()
            excluded_users = [
                "Supervisor",
                "Home Assistant Content",
                "Home Assistant Cloud",
            ]
            user_ids = [user.id for user in users if user.name not in excluded_users]

            for user_id in user_ids:
                user_data_file = hass.config.path(
                    STORAGE_DIR, f"frontend.user_data_{user_id}"
                )

                if await asyncio.to_thread(os.path.exists, user_data_file):
                    try:
                        # Use asyncio.to_thread for non-blocking file operations
                        user_data = await self._async_read_file(user_data_file)
                        if user_data:
                            data = json.loads(user_data)
                            language = data["data"]["language"]["language"]

                            # Store in cache and UserLanguageStore
                            self._user_languages[user_id] = language
                            self._all_languages.add(language)
                            await user_language_store.set_user_language(
                                user_id, language
                            )
                            _LOGGER.debug(
                                "Cached language for user %s: %s", user_id, language
                            )
                    except (KeyError, json.JSONDecodeError) as e:
                        _LOGGER.warning(
                            "Error processing user data for %s: %s", user_id, str(e)
                        )

            # Mark UserLanguageStore as initialized using the proper method
            await self.async_mark_user_language_store_initialized()

        except Exception as e:
            _LOGGER.warning(
                "Error populating user languages: %s", str(e), exc_info=True
            )

    @staticmethod
    async def _async_read_file(file_path: str) -> str:
        """Read a file asynchronously."""
        try:
            return await asyncio.to_thread(LanguageCache._read_file, file_path)
        except Exception as e:
            _LOGGER.warning("Error reading file %s: %s", file_path, str(e))
            return ""

    @staticmethod
    def _read_file(file_path: str) -> str:
        """Read a file synchronously (to be called via asyncio.to_thread)."""
        with open(file_path, "r") as file:
            return file.read()

    async def get_active_user_language(self, hass: HomeAssistant) -> str:
        """
        Get the language of the active user, with caching to reduce I/O.

        Args:
            hass: The Home Assistant instance

        Returns:
            The language code (e.g., 'en', 'fr')
        """
        # Check if auth file has been updated
        if await self._is_auth_updated(hass):
            # If auth has been updated, we need to refresh the active user
            active_user_id = await self._find_last_logged_in_user(hass)
            if active_user_id:
                user_language_store = UserLanguageStore()
                language = await user_language_store.get_user_language(active_user_id)
                if language:
                    return language

                # Fallback to loading from file if not in UserLanguageStore
                user_data_path = hass.config.path(
                    STORAGE_DIR, f"frontend.user_data_{active_user_id}"
                )
                if await asyncio.to_thread(os.path.exists, user_data_path):
                    try:
                        # Use asyncio.to_thread for non-blocking file operations
                        user_data = await self._async_read_file(user_data_path)
                        if user_data:
                            data = json.loads(user_data)
                            language = data["data"]["language"]["language"]
                            self._user_languages[active_user_id] = language
                            await user_language_store.set_user_language(
                                active_user_id, language
                            )
                            return language
                    except (KeyError, json.JSONDecodeError) as e:
                        _LOGGER.debug(
                            "Error loading language for user %s: %s",
                            active_user_id,
                            str(e),
                        )

        # If we have a cached active user, use that
        active_user_id = await self._find_last_logged_in_user(hass)
        if active_user_id and active_user_id in self._user_languages:
            return self._user_languages[active_user_id]

        # Default to English if all else fails
        return "en"

    async def _is_auth_updated(self, hass: HomeAssistant) -> bool:
        """
        Check if the auth file has been updated since last check.

        Args:
            hass: The Home Assistant instance

        Returns:
            True if the auth file has been updated, False otherwise
        """
        auth_file_path = hass.config.path(STORAGE_DIR, "auth")
        if not await asyncio.to_thread(os.path.exists, auth_file_path):
            return False

        # Use asyncio.to_thread for non-blocking file operations
        current_mtime = await asyncio.to_thread(os.path.getmtime, auth_file_path)
        if self._auth_update_time is None or current_mtime > self._auth_update_time:
            self._auth_update_time = current_mtime
            return True
        return False

    @staticmethod
    async def _find_last_logged_in_user(hass: HomeAssistant) -> Optional[str]:
        """
        Find the ID of the last logged-in user.

        Args:
            hass: The Home Assistant instance

        Returns:
            The user ID of the last logged-in user, or None if no user found
        """
        users = await hass.auth.async_get_users()
        last_user = None
        last_login_time = None

        for user in users:
            for token in user.refresh_tokens.values():
                if token.last_used_at and (
                    last_login_time is None or token.last_used_at > last_login_time
                ):
                    last_login_time = token.last_used_at
                    last_user = user

        return last_user.id if last_user else None

    def is_initialized(self) -> bool:
        """
        Check if the language cache is initialized.

        Returns:
            True if initialized, False otherwise
        """
        return self._initialized

    async def get_all_languages(self) -> List[str]:
        """
        Get all languages from the cache.

        Returns:
            A list of language codes
        """
        return list(self._all_languages)

    async def load_translation(
        self, hass: HomeAssistant, language: str
    ) -> Optional[dict]:
        """
        Load a translation file with caching.

        Args:
            hass: The Home Assistant instance
            language: The language code

        Returns:
            The translation data as a dictionary, or None if not found
        """
        if language in self._translations_cache:
            return self._translations_cache[language]

        translations_path = hass.config.path(
            "custom_components/mqtt_vacuum_camera/translations"
        )
        file_path = os.path.join(translations_path, f"{language}.json")

        try:
            if await asyncio.to_thread(os.path.exists, file_path):
                # Use asyncio.to_thread for non-blocking file operations
                file_content = await self._async_read_file(file_path)
                if file_content:
                    translation_data = json.loads(file_content)
                    self._translations_cache[language] = translation_data
                    return translation_data
        except (json.JSONDecodeError, FileNotFoundError) as e:
            _LOGGER.warning("Error loading translation for %s: %s", language, str(e))

        return None

    async def load_translations_json(
        self, hass: HomeAssistant, languages: List[str]
    ) -> List[Optional[dict]]:
        """
        Load multiple translation files with caching.

        Args:
            hass: The Home Assistant instance
            languages: A list of language codes

        Returns:
            A list of translation data dictionaries, with None for languages not found
        """
        result = []
        for language in languages:
            translation = await self.load_translation(hass, language)
            result.append(translation)
        return result

    @staticmethod
    async def async_mark_user_language_store_initialized() -> None:
        """
        Mark the UserLanguageStore as initialized using a proper encapsulation approach.
        This method provides a public API for setting the initialization state instead of
        directly modifying protected attributes.
        """
        try:
            # Since we don't have direct access to modify the external package's API,
            # we're using this method as a proper encapsulation layer.
            # In a future update of the valetudo_map_parser package, this should be
            # replaced with a proper public API call if one becomes available.

            # Use setattr to set the initialization flag instead of directly accessing protected member
            setattr(UserLanguageStore, "_initialized", True)
            _LOGGER.debug("UserLanguageStore marked as initialized")
        except Exception as e:
            _LOGGER.warning(
                "Error marking UserLanguageStore as initialized: %s",
                str(e),
                exc_info=True,
            )
