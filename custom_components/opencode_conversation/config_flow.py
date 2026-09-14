"""Configuration flow for OpenCode Conversation."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .client import (
    OpenCodeAuthenticationError,
    OpenCodeClient,
    OpenCodeConnectionError,
    normalize_url,
)
from .const import (
    CONF_AGENT,
    CONF_TIMEOUT,
    CONF_URL,
    DEFAULT_AGENT,
    DEFAULT_TIMEOUT,
    DEFAULT_URL,
    DEFAULT_USERNAME,
    DOMAIN,
)


def _schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    defaults = defaults or {}
    return vol.Schema(
        {
            vol.Required(CONF_URL, default=defaults.get(CONF_URL, DEFAULT_URL)): str,
            vol.Required(
                CONF_USERNAME,
                default=defaults.get(CONF_USERNAME, DEFAULT_USERNAME),
            ): str,
            vol.Required(CONF_PASSWORD, default=defaults.get(CONF_PASSWORD, "")): str,
            vol.Required(
                CONF_AGENT, default=defaults.get(CONF_AGENT, DEFAULT_AGENT)
            ): str,
            vol.Required(
                CONF_TIMEOUT, default=defaults.get(CONF_TIMEOUT, DEFAULT_TIMEOUT)
            ): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=600)
            ),
        }
    )


def _reauth_schema(defaults: dict[str, Any]) -> vol.Schema:
    """Request only credentials; endpoint and agent are existing entry data."""
    return vol.Schema(
        {
            vol.Required(CONF_USERNAME, default=defaults[CONF_USERNAME]): str,
            vol.Required(CONF_PASSWORD, default=""): str,
        }
    )


async def _validate(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    data = dict(data)
    data[CONF_URL] = normalize_url(data[CONF_URL])
    client = OpenCodeClient(
        async_get_clientsession(hass),
        data[CONF_URL],
        data[CONF_USERNAME],
        data[CONF_PASSWORD],
        data[CONF_TIMEOUT],
    )
    await client.validate(data[CONF_AGENT])
    return data


class OpenCodeConversationConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle configuration and credential reauthentication."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                data = await _validate(self.hass, user_input)
            except OpenCodeAuthenticationError:
                errors["base"] = "invalid_auth"
            except (OpenCodeConnectionError, ValueError):
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(f"{data[CONF_URL]}|{data[CONF_AGENT]}")
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"OpenCode ({data[CONF_AGENT]})", data=data
                )
        return self.async_show_form(
            step_id="user", data_schema=_schema(user_input), errors=errors
        )

    async def async_step_reauth(
        self, entry_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Start reauthentication without creating a second entry."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        entry = self._get_reauth_entry()
        defaults = dict(entry.data)
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                data = await _validate(self.hass, {**defaults, **user_input})
            except OpenCodeAuthenticationError:
                errors["base"] = "invalid_auth"
            except (OpenCodeConnectionError, ValueError):
                errors["base"] = "cannot_connect"
            else:
                return self.async_update_reload_and_abort(
                    entry, data_updates=data, reason="reauth_successful"
                )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=_reauth_schema(defaults),
            errors=errors,
        )
