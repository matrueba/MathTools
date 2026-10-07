"""Context-window lookup: provider-scoped table, normalized model ids."""

import pytest

from constants.source_files import MODEL_CONTEXT_WINDOW
from web.sources import models
from web.sources.models import context_window, model_key

TABLE = {
    "claude": {"opus-5.5": 1_000_000, "haiku-4.5": 200_000, "claude-special": 42},
    "opencode": {"minimax-m2.5-free": 200_000},
}


@pytest.fixture(autouse=True)
def table(monkeypatch):
    monkeypatch.setattr(models, "MODEL_CONTEXT_WINDOW", TABLE)


@pytest.mark.parametrize("recorded, key", [
    ("claude-opus-5-5", "opus-5.5"),
    ("claude-haiku-4-5-20251001", "haiku-4.5"),
    ("anthropic/claude-sonnet-4-6", "sonnet-4.6"),
    ("claude-opus-5-5[1m]", "opus-5.5"),
    ("Claude-Opus-5-5", "opus-5.5"),
    ("minimax-m2.5-free", "minimax-m2.5-free"),
])
def test_model_key_normalizes_recorded_ids(recorded, key):
    assert model_key(recorded) == key


def test_lookup_is_scoped_to_the_provider():
    assert context_window("claude", "claude-opus-5-5") == 1_000_000
    assert context_window("claude", "claude-haiku-4-5-20251001") == 200_000
    assert context_window("opencode", "opencode/minimax-m2.5-free") == 200_000
    # The same model name under another provider is not found.
    assert context_window("opencode", "claude-opus-5-5") is None


def test_an_exact_key_wins_over_normalization():
    assert context_window("claude", "claude-special") == 42


def test_unknown_provider_or_model_gets_the_default():
    assert context_window("codex", "gpt-5", default=7) == 7
    assert context_window("nope", "claude-opus-5-5", default=7) == 7
    assert context_window("claude", None, default=7) == 7
    assert context_window("claude", "claude-mystery-9", default=7) == 7


def test_the_real_table_resolves_the_ids_claude_code_writes(monkeypatch):
    monkeypatch.setattr(models, "MODEL_CONTEXT_WINDOW", MODEL_CONTEXT_WINDOW)
    for key, window in MODEL_CONTEXT_WINDOW["claude"].items():
        api_id = "claude-" + key.replace(".", "-")  # "opus-5.5" -> "claude-opus-5-5"
        assert context_window("claude", api_id) == window
