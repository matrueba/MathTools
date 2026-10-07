"""
Context-window lookup shared by every session reader.

MODEL_CONTEXT_WINDOW is keyed by provider id, then by a short model name
("opus-5.5"), while each tool records its own spelling of the model id:
Claude Code writes the API id ("claude-opus-5-5", "claude-haiku-4-5-20251001"),
Opencode prefixes a provider ("anthropic/claude-sonnet-4-6"). `model_key`
reduces any of those to the table's form, so the table stays readable and one
entry covers every spelling and dated snapshot of a model.
"""

import re

from constants.source_files import MODEL_CONTEXT_WINDOW

_DATED_SNAPSHOT = re.compile(r"-\d{8}$")  # "-20251001"
_VERSION_DASH = re.compile(r"(?<=\d)-(?=\d)")  # "5-5" -> "5.5"


def model_key(model: str) -> str:
    """
    Normalize a recorded model id to MODEL_CONTEXT_WINDOW's key form.

        claude-opus-5-5             -> opus-5.5
        claude-haiku-4-5-20251001   -> haiku-4.5
        anthropic/claude-sonnet-4-6 -> sonnet-4.6
        claude-opus-5-5[1m]         -> opus-5.5
        minimax-m2.5-free           -> minimax-m2.5-free
    """
    key = model.strip().lower()
    key = key.split("[", 1)[0]  # Claude Code's "[1m]"-style variant suffix
    key = key.rsplit("/", 1)[-1]  # "provider/model"
    key = _DATED_SNAPSHOT.sub("", key)
    key = key.removeprefix("claude-")
    return _VERSION_DASH.sub(".", key)


def context_window(provider: str, model: str | None, default: int | None = None) -> int | None:
    """
    Context window of `model` as run by `provider` (an AGENT_PROVIDERS id).

    An exact key wins over the normalized one, so the table can still pin a
    specific spelling. Unknown providers and models get `default`.
    """
    windows = MODEL_CONTEXT_WINDOW.get(provider) or {}
    if not model:
        return default
    if model in windows:
        return windows[model]
    return windows.get(model_key(model), default)
