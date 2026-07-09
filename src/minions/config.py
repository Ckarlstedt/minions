"""Runtime configuration.

Sources, in precedence order:

1. ``MINIONS_*`` environment variables
2. built-in defaults (tuned for the local omlx server)

The omlx server requires an API key. To keep secrets out of the repository
and out of shell history, the loader can discover it from omlx's own config
(``~/.omlx/settings.json``) when ``MINIONS_API_KEY`` is not set. The key is
never logged and never written anywhere by this package.

A config *file* (e.g. minions.toml) is deliberately deferred: with this few
knobs, env vars cover real use, and every additional source adds precedence
rules to explain. Revisit if the surface grows (see .agents/open-questions.md).
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_BASE_URL = "http://127.0.0.1:8000/v1"
# The omlx server advertises the model without the HF org prefix.
DEFAULT_MODEL = "gpt-oss-20b-MXFP4-Q8"

OMLX_SETTINGS_PATH = Path.home() / ".omlx" / "settings.json"


class ConfigError(Exception):
    """Raised when configuration values cannot be parsed."""


def default_state_dir() -> Path:
    """Directory for run traces — outside any repository (minions are read-only)."""
    xdg = os.environ.get("XDG_STATE_HOME")
    base = Path(xdg) if xdg else Path.home() / ".local" / "state"
    return base / "minions"


@dataclass(frozen=True)
class Settings:
    base_url: str = DEFAULT_BASE_URL
    model: str = DEFAULT_MODEL
    api_key: str | None = None
    api_key_source: str = "none"

    # Budgets. The omlx server caps context at 32k tokens; the loop force-finishes
    # before that wall so the report never gets truncated by the server.
    max_steps: int = 16
    context_token_limit: int = 24_000
    max_tool_output_chars: int = 8_000
    max_completion_tokens: int = 4_096

    temperature: float = 0.2
    request_timeout: float = 180.0
    state_dir: Path = field(default_factory=default_state_dir)


def _get_int(env: Mapping[str, str], key: str, fallback: int) -> int:
    raw = env.get(key)
    if raw is None:
        return fallback
    try:
        return int(raw)
    except ValueError as exc:
        raise ConfigError(f"{key} must be an integer, got {raw!r}") from exc


def _get_float(env: Mapping[str, str], key: str, fallback: float) -> float:
    raw = env.get(key)
    if raw is None:
        return fallback
    try:
        return float(raw)
    except ValueError as exc:
        raise ConfigError(f"{key} must be a number, got {raw!r}") from exc


def discover_omlx_api_key(settings_path: Path = OMLX_SETTINGS_PATH) -> str | None:
    """Best-effort read of the omlx server's own API key. Returns None on any failure."""
    try:
        data = json.loads(settings_path.read_text(encoding="utf-8"))
        key = data.get("auth", {}).get("api_key")
    except (OSError, ValueError, AttributeError):
        return None
    if isinstance(key, str) and key.strip():
        return key.strip()
    return None


def load_settings(
    env: Mapping[str, str] | None = None,
    *,
    omlx_settings_path: Path = OMLX_SETTINGS_PATH,
) -> Settings:
    env = os.environ if env is None else env
    defaults = Settings()

    api_key = env.get("MINIONS_API_KEY")
    api_key_source = "MINIONS_API_KEY env" if api_key else "none"
    if not api_key:
        api_key = discover_omlx_api_key(omlx_settings_path)
        if api_key:
            api_key_source = f"omlx settings ({omlx_settings_path})"

    state_dir_raw = env.get("MINIONS_STATE_DIR")

    return Settings(
        base_url=env.get("MINIONS_BASE_URL", defaults.base_url).rstrip("/"),
        model=env.get("MINIONS_MODEL", defaults.model),
        api_key=api_key,
        api_key_source=api_key_source,
        max_steps=_get_int(env, "MINIONS_MAX_STEPS", defaults.max_steps),
        context_token_limit=_get_int(
            env, "MINIONS_CONTEXT_TOKEN_LIMIT", defaults.context_token_limit
        ),
        max_tool_output_chars=_get_int(
            env, "MINIONS_MAX_TOOL_OUTPUT_CHARS", defaults.max_tool_output_chars
        ),
        max_completion_tokens=_get_int(
            env, "MINIONS_MAX_COMPLETION_TOKENS", defaults.max_completion_tokens
        ),
        temperature=_get_float(env, "MINIONS_TEMPERATURE", defaults.temperature),
        request_timeout=_get_float(env, "MINIONS_REQUEST_TIMEOUT", defaults.request_timeout),
        state_dir=Path(state_dir_raw) if state_dir_raw else defaults.state_dir,
    )
