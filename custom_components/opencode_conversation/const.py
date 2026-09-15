"""Constants for the OpenCode Conversation integration."""

from homeassistant.const import Platform

DOMAIN = "opencode_conversation"
PLATFORMS: list[Platform] = [Platform.CONVERSATION]

CONF_URL = "url"
CONF_AGENT = "agent"
CONF_TIMEOUT = "timeout"

DEFAULT_URL = "http://127.0.0.1:4096"
DEFAULT_USERNAME = "opencode"
DEFAULT_AGENT = "ha-test"
DEFAULT_TIMEOUT = 90

SESSION_TTL_SECONDS = 60 * 60 * 6
MAX_SESSIONS = 100
