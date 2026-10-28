"""Config flow for BWT Mon Service integration."""
import logging

import aiohttp
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
from homeassistant.core import callback

from .api import (
    BwtCloudApi,
    BwtApiError,
    BwtConnectionError,
    BwtDeviceNotFound,
    BwtInvalidCredentials,
)
from .const import (
    DOMAIN,
    CONF_SERIAL_NUMBER,
    CONF_DEVICE_NAME,
    CONF_INTERVAL_MAIN,
    CONF_INTERVAL_CONSUMPTION,
    CONF_REQUEST_TIMEOUT,
    DEFAULT_DEVICE_NAME,
    DEFAULT_INTERVAL_MAIN,
    DEFAULT_INTERVAL_CONSUMPTION,
    DEFAULT_REQUEST_TIMEOUT,
    MIN_INTERVAL_MAIN,
    MAX_INTERVAL_MAIN,
    MIN_INTERVAL_CONSUMPTION,
    MAX_INTERVAL_CONSUMPTION,
    MIN_REQUEST_TIMEOUT,
    MAX_REQUEST_TIMEOUT,
)

_LOGGER = logging.getLogger(__name__)

INTERVAL_MAIN_VALIDATOR = vol.All(
    vol.Coerce(int), vol.Range(min=MIN_INTERVAL_MAIN, max=MAX_INTERVAL_MAIN)
)
INTERVAL_CONSUMPTION_VALIDATOR = vol.All(
    vol.Coerce(int),
    vol.Range(min=MIN_INTERVAL_CONSUMPTION, max=MAX_INTERVAL_CONSUMPTION),
)
TIMEOUT_VALIDATOR = vol.All(
    vol.Coerce(int), vol.Range(min=MIN_REQUEST_TIMEOUT, max=MAX_REQUEST_TIMEOUT)
)


async def _async_validate(username: str, password: str, serial: str) -> str | None:
    """Try a login. Return None on success or an error key for the form."""
    session = aiohttp.ClientSession(cookie_jar=aiohttp.CookieJar(unsafe=True))
    try:
        api = BwtCloudApi(
            session=session, username=username, password=password, serial_number=serial
        )
        await api.authenticate()
    except BwtInvalidCredentials:
        return "invalid_auth"
    except BwtDeviceNotFound:
        return "device_not_found"
    except BwtConnectionError:
        return "cannot_connect"
    except BwtApiError:
        return "unknown"
    except Exception:  # noqa: BLE001
        _LOGGER.exception("Unexpected error during config validation")
        return "unknown"
    finally:
        await session.close()
    return None


class BWTConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for BWT Mon Service."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            for key in (CONF_USERNAME, CONF_PASSWORD, CONF_SERIAL_NUMBER):
                if not user_input.get(key):
                    errors[key] = "required"

            if not errors:
                error = await _async_validate(
                    user_input[CONF_USERNAME],
                    user_input[CONF_PASSWORD],
                    user_input[CONF_SERIAL_NUMBER],
                )
                if error:
                    errors["base"] = error

            if not errors:
                await self.async_set_unique_id(user_input[CONF_SERIAL_NUMBER])
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=user_input.get(
                        CONF_DEVICE_NAME, user_input[CONF_SERIAL_NUMBER]
                    ),
                    data=user_input,
                )

        data_schema = vol.Schema(
            {
                vol.Required(CONF_USERNAME): str,
                vol.Required(CONF_PASSWORD): str,
                vol.Required(CONF_SERIAL_NUMBER): str,
                vol.Optional(CONF_DEVICE_NAME, default=DEFAULT_DEVICE_NAME): str,
                vol.Optional(
                    CONF_INTERVAL_MAIN, default=DEFAULT_INTERVAL_MAIN
                ): INTERVAL_MAIN_VALIDATOR,
                vol.Optional(
                    CONF_INTERVAL_CONSUMPTION, default=DEFAULT_INTERVAL_CONSUMPTION
                ): INTERVAL_CONSUMPTION_VALIDATOR,
            }
        )

        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )

    # -- re-authentication (raised by the coordinator when BWT rejects the login)

    async def async_step_reauth(self, entry_data):
        """Start re-authentication."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None):
        """Ask for the new password (and email, if it changed)."""
        entry = self._get_reauth_entry()
        errors = {}

        if user_input is not None:
            error = await _async_validate(
                user_input[CONF_USERNAME],
                user_input[CONF_PASSWORD],
                entry.data[CONF_SERIAL_NUMBER],
            )
            if error:
                errors["base"] = error
            else:
                updates = {
                    CONF_USERNAME: user_input[CONF_USERNAME],
                    CONF_PASSWORD: user_input[CONF_PASSWORD],
                }
                # The entry failed during setup, so it has no update listener
                # yet: reload it explicitly. When it is already loaded, the
                # update listener takes care of the reload.
                if entry.update_listeners:
                    return self.async_update_and_abort(entry, data_updates=updates)
                return self.async_update_reload_and_abort(entry, data_updates=updates)

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_USERNAME,
                        default=(user_input or entry.data).get(CONF_USERNAME, ""),
                    ): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )

    # -- reconfigure (Settings > Devices & Services > integration > ⋮)

    async def async_step_reconfigure(self, user_input=None):
        """Change login, password and device name."""
        entry = self._get_reconfigure_entry()
        errors = {}

        if user_input is not None:
            username = user_input[CONF_USERNAME]
            # Blank password = keep the stored one
            password = user_input.get(CONF_PASSWORD) or entry.data[CONF_PASSWORD]
            error = await _async_validate(
                username, password, entry.data[CONF_SERIAL_NUMBER]
            )
            if error:
                errors["base"] = error
            else:
                device_name = user_input.get(CONF_DEVICE_NAME) or DEFAULT_DEVICE_NAME
                return self.async_update_and_abort(
                    entry,
                    title=device_name,
                    data_updates={
                        CONF_USERNAME: username,
                        CONF_PASSWORD: password,
                        CONF_DEVICE_NAME: device_name,
                    },
                )

        current = user_input or entry.data
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_USERNAME, default=current.get(CONF_USERNAME, "")
                    ): str,
                    vol.Optional(CONF_PASSWORD, default=""): str,
                    vol.Optional(
                        CONF_DEVICE_NAME,
                        default=current.get(CONF_DEVICE_NAME, DEFAULT_DEVICE_NAME),
                    ): str,
                }
            ),
            description_placeholders={"serial": entry.data[CONF_SERIAL_NUMBER]},
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return BWTOptionsFlow()


class BWTOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for BWT Mon Service."""

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        entry = self.config_entry

        def current(key, default):
            return entry.options.get(key, entry.data.get(key, default))

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_INTERVAL_MAIN,
                        default=current(CONF_INTERVAL_MAIN, DEFAULT_INTERVAL_MAIN),
                    ): INTERVAL_MAIN_VALIDATOR,
                    vol.Optional(
                        CONF_INTERVAL_CONSUMPTION,
                        default=current(
                            CONF_INTERVAL_CONSUMPTION, DEFAULT_INTERVAL_CONSUMPTION
                        ),
                    ): INTERVAL_CONSUMPTION_VALIDATOR,
                    vol.Optional(
                        CONF_REQUEST_TIMEOUT,
                        default=current(CONF_REQUEST_TIMEOUT, DEFAULT_REQUEST_TIMEOUT),
                    ): TIMEOUT_VALIDATOR,
                }
            ),
        )
