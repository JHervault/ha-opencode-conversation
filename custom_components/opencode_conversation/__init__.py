"""Set up the OpenCode Conversation integration."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .client import OpenCodeAuthenticationError, OpenCodeClient, OpenCodeConnectionError
from .const import CONF_AGENT, CONF_TIMEOUT, CONF_URL, PLATFORMS

type OpenCodeConfigEntry = ConfigEntry["OpenCodeRuntime"]


@dataclass
class OpenCodeRuntime:
    """Per-entry services shared by its conversation platform."""

    client: OpenCodeClient
    sessions: dict[str, tuple[str, float]] = field(default_factory=dict)
    locks: dict[str, asyncio.Lock] = field(default_factory=dict)


async def async_setup_entry(hass: HomeAssistant, entry: OpenCodeConfigEntry) -> bool:
    """Set up a configured OpenCode conversation agent."""
    client = OpenCodeClient(
        async_get_clientsession(hass),
        entry.data[CONF_URL],
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
        entry.data[CONF_TIMEOUT],
    )
    try:
        await client.validate(entry.data[CONF_AGENT])
    except OpenCodeAuthenticationError as err:
        raise ConfigEntryAuthFailed("OpenCode credentials were rejected") from err
    except OpenCodeConnectionError as err:
        raise ConfigEntryNotReady("OpenCode is unavailable") from err

    runtime = OpenCodeRuntime(client=client)
    entry.runtime_data = runtime
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: OpenCodeConfigEntry) -> bool:
    """Unload the conversation platform."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
