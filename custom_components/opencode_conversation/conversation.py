"""Conversation entity that forwards all prompts to OpenCode."""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING, Literal, override

from homeassistant.components import conversation
from homeassistant.components.conversation.chat_log import AssistantContent
from homeassistant.const import MATCH_ALL
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .client import OpenCodeAuthenticationError, OpenCodeConnectionError
from .const import CONF_AGENT, MAX_SESSIONS, SESSION_TTL_SECONDS

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

    from .__init__ import OpenCodeRuntime


FAILURE_SPEECH = "Je n’arrive pas à joindre l’assistant OpenCode pour le moment."


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the OpenCode conversation entity for a config entry."""
    runtime: OpenCodeRuntime = entry.runtime_data
    async_add_entities([OpenCodeConversationEntity(entry, runtime)])


class OpenCodeConversationEntity(
    conversation.ConversationEntity, conversation.AbstractConversationAgent
):
    """A Home Assistant conversation agent backed by an OpenCode session."""

    _attr_name = "OpenCode"
    _attr_has_entity_name = True

    def __init__(self, entry: ConfigEntry, runtime: OpenCodeRuntime) -> None:
        self._entry = entry
        self._runtime = runtime
        self._attr_unique_id = entry.entry_id

    @property
    @override
    def supported_languages(self) -> list[str] | Literal["*"]:
        """Support every language passed through a Home Assistant pipeline."""
        return MATCH_ALL

    @override
    async def async_added_to_hass(self) -> None:
        """Register this entity as the entry's conversation agent."""
        await super().async_added_to_hass()
        conversation.async_set_agent(self.hass, self._entry, self)

    @override
    async def async_will_remove_from_hass(self) -> None:
        """Remove the conversation agent when the entity is unloaded."""
        conversation.async_unset_agent(self.hass, self._entry)
        await super().async_will_remove_from_hass()

    def _clean_sessions(self) -> None:
        """Bound in-memory mappings; OpenCode owns the actual session lifecycle."""
        now = time.monotonic()
        stale = [
            key
            for key, (_, touched) in self._runtime.sessions.items()
            if now - touched > SESSION_TTL_SECONDS
        ]
        for key in stale:
            self._runtime.sessions.pop(key, None)
            self._runtime.locks.pop(key, None)
        overflow = len(self._runtime.sessions) - MAX_SESSIONS
        if overflow > 0:
            oldest_sessions = sorted(
                self._runtime.sessions.items(), key=lambda item: item[1][1]
            )
            for key, _ in oldest_sessions[:overflow]:
                self._runtime.sessions.pop(key, None)
                self._runtime.locks.pop(key, None)

    @override
    async def _async_handle_message(
        self,
        user_input: conversation.ConversationInput,
        chat_log: conversation.ChatLog,
    ) -> conversation.ConversationResult:
        """Forward text to OpenCode; HA CONTROL is intentionally unsupported."""
        conversation_id = chat_log.conversation_id
        self._clean_sessions()
        lock = self._runtime.locks.setdefault(conversation_id, asyncio.Lock())

        async with lock:
            try:
                saved = self._runtime.sessions.get(conversation_id)
                session_id = (
                    saved[0]
                    if saved
                    else await self._runtime.client.create_session()
                )
                answer = await self._runtime.client.send_message(
                    session_id, self._entry.data[CONF_AGENT], user_input.text
                )
                self._runtime.sessions[conversation_id] = (session_id, time.monotonic())
                speech = answer or FAILURE_SPEECH
            except OpenCodeAuthenticationError:
                try:
                    # ConfigEntry deduplicates concurrent reauthentication flows.
                    self._entry.async_start_reauth(self.hass)
                except Exception:  # Reauth UI failures must not break voice output.
                    pass
                speech = FAILURE_SPEECH
            except OpenCodeConnectionError:
                speech = FAILURE_SPEECH
            except Exception:  # Never expose internal failures through voice output.
                speech = FAILURE_SPEECH

        # Keep the assistant turn in HA's ChatLog without exposing OpenCode's
        # non-text parts (tool calls, reasoning, metadata) to later turns.
        chat_log.async_add_assistant_content_without_tools(
            AssistantContent(agent_id=self.entity_id, content=speech)
        )
        return conversation.async_get_result_from_chat_log(user_input, chat_log)
