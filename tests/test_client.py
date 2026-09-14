"""Tests for client helpers which can run without Home Assistant."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


def _client_module():
    path = (
        Path(__file__).parents[1]
        / "custom_components/opencode_conversation/client.py"
    )
    spec = importlib.util.spec_from_file_location("opencode_client", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


client = _client_module()


def test_normalize_url_removes_trailing_slash_and_query() -> None:
    assert client.normalize_url(" https://example.test/api/?unsafe=query ") == "https://example.test/api"


def test_normalize_url_removes_fragment() -> None:
    assert client.normalize_url("https://example.test/#fragment") == "https://example.test"


@pytest.mark.parametrize("url", ["example.test", "ftp://example.test", "http://"])
def test_normalize_url_rejects_non_http_absolute_urls(url: str) -> None:
    with pytest.raises(ValueError):
        client.normalize_url(url)


def test_extract_text_parts_ignores_tools_and_unknown_content() -> None:
    payload = {
        "messages": [
            {"parts": [{"type": "tool", "name": "secret_tool"}]},
            {
                "parts": [
                    {"type": "text", "text": " First "},
                    {"type": "reasoning", "text": "hidden"},
                ]
            },
            {"parts": [{"type": "text", "text": "Second"}]},
        ]
    }
    assert client.extract_text_parts(payload) == "First\nSecond"


def test_extract_text_parts_accepts_a_single_message() -> None:
    payload = {"parts": [{"type": "text", "text": "Answer"}]}
    assert client.extract_text_parts(payload) == "Answer"


def test_extract_text_parts_accepts_a_list_of_messages() -> None:
    payload = [
        {"parts": [{"type": "text", "text": "First"}]},
        {"parts": [{"type": "text", "text": "Second"}]},
    ]
    assert client.extract_text_parts(payload) == "First\nSecond"


def test_extract_text_parts_returns_empty_for_non_text_response() -> None:
    payload = {"parts": [{"type": "tool", "name": "call"}]}
    assert client.extract_text_parts(payload) == ""
