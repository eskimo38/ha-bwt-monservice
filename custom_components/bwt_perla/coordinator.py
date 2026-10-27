"""Data coordinator for BWT Perla integration."""
import logging
from datetime import timedelta

import aiohttp

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
from homeassistant.util import dt as dt_util

from .api import BwtCloudApi, BwtAuthError, BwtConnectionError, BwtApiError
from .const import (
    DOMAIN,
    CONF_SERIAL_NUMBER,
    CONF_INTERVAL_MAIN,
    CONF_INTERVAL_CONSUMPTION,
    DEFAULT_INTERVAL_MAIN,
    DEFAULT_INTERVAL_CONSUMPTION,
    CONSUMPTION_KEYS,
    GROUP_CONSUMPTION,
    GROUP_MAIN,
)

_LOGGER = logging.getLogger(__name__)


class BWTDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching BWT data."""

    def __init__(self, hass: HomeAssistant, entry) -> None:
        self.entry = entry
        self.receipt_line_key: str | None = None
        self._last_main_update: float = 0
        self._last_water_consumption: int = 0
        # Endpoint groups whose last fetch failed ("main" / "consumption")
        self._failed_groups: set[str] = set()

        # Use a dedicated session with cookie jar so login cookies persist
        # unsafe=True allows cookies for IP-based and non-standard domains
        self._cookie_jar = aiohttp.CookieJar(unsafe=True)
        self._session = aiohttp.ClientSession(cookie_jar=self._cookie_jar)

        self.api = BwtCloudApi(
            session=self._session,
            username=entry.data[CONF_USERNAME],
            password=entry.data[CONF_PASSWORD],
            serial_number=entry.data[CONF_SERIAL_NUMBER],
        )

        interval = entry.options.get(
            CONF_INTERVAL_CONSUMPTION,
            entry.data.get(CONF_INTERVAL_CONSUMPTION, DEFAULT_INTERVAL_CONSUMPTION),
        )

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=interval),
        )

    def key_available(self, key: str) -> bool:
        """Return False if the endpoint feeding this entity key is failing."""
        group = GROUP_CONSUMPTION if key in CONSUMPTION_KEYS else GROUP_MAIN
        return group not in self._failed_groups

    def _mark_failed(self, group: str, err: Exception) -> None:
        """Flag a group as failed; log at error level on the first failure only."""
        if group not in self._failed_groups:
            _LOGGER.error("Failed to update %s data, entities unavailable: %s", group, err)
        else:
            _LOGGER.debug("%s data still failing: %s", group, err)
        self._failed_groups.add(group)

    def _mark_ok(self, group: str) -> None:
        if group in self._failed_groups:
            _LOGGER.info("%s data update recovered", group)
            self._failed_groups.discard(group)

    async def _async_update_data(self) -> dict:
        """Fetch data from BWT."""
        try:
            # Authenticate if needed
            if not self.receipt_line_key:
                self.receipt_line_key = await self.api.authenticate()

            data = dict(self.data) if self.data else {}

            # Main data (less frequent)
            interval_main = self.entry.options.get(
                CONF_INTERVAL_MAIN,
                self.entry.data.get(CONF_INTERVAL_MAIN, DEFAULT_INTERVAL_MAIN),
            )

            if (self.hass.loop.time() - self._last_main_update) > interval_main:
                try:
                    main_data = await self.api.get_main_data(self.receipt_line_key)
                    data.update(main_data)
                    self._last_main_update = self.hass.loop.time()
                    self._mark_ok(GROUP_MAIN)
                    _LOGGER.debug("Main data updated")
                except BwtAuthError:
                    self.receipt_line_key = None
                    raise
                except BwtApiError as err:
                    self._mark_failed(GROUP_MAIN, err)

            # Consumption data (frequent)
            consumption_ok = False
            try:
                consumption_data = await self.api.get_consumption_data(
                    self.receipt_line_key
                )
                data.update(consumption_data)
                # Time of this successful fetch (the dataset only carries the
                # date of the data, not when we last retrieved it)
                data["refresh_date"] = dt_util.utcnow()
                self._mark_ok(GROUP_CONSUMPTION)
                consumption_ok = True
                _LOGGER.debug("Consumption data updated")
            except BwtAuthError:
                self.receipt_line_key = None
                raise
            except BwtApiError as err:
                self._mark_failed(GROUP_CONSUMPTION, err)
                consumption_ok = False

            # Calculate water increment (only from fresh data)
            if consumption_ok and "water_consumption" in data:
                current = data["water_consumption"]
                if self._last_water_consumption > 0:
                    if current < self._last_water_consumption:
                        data["water_increment"] = current
                    else:
                        data["water_increment"] = (
                            current - self._last_water_consumption
                        )
                else:
                    data["water_increment"] = 0
                self._last_water_consumption = current

            if not data or len(data) < 3:
                raise UpdateFailed("Insufficient data received")

            return data

        except (BwtAuthError, BwtConnectionError) as err:
            self.receipt_line_key = None
            raise UpdateFailed(f"Error communicating with API: {err}") from err
        except UpdateFailed:
            raise
        except Exception as err:
            _LOGGER.error("Error fetching BWT data: %s", err)
            raise UpdateFailed(f"Error communicating with API: {err}") from err

    async def async_shutdown(self) -> None:
        """Close the API session."""
        await self._session.close()
        await super().async_shutdown()
