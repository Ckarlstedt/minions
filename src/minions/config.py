"""Runtime configuration.

Sources, in precedence order:

1. ``MINIONS_*`` process environment variables
2. a ``.env`` file in the current working directory (gitignored;
   see ``.env.example`` for every supported variable)
3. built-in defaults (targeting a local OpenAI-compatible server)

``.env`` was chosen over a bespoke config file (minions.toml etc.): it is the
ubiquitous convention for exactly this kind of per-checkout, possibly-secret
configuration, needs no new precedence rules beyond "process env wins", and
the parser below is ~15 lines — no dependency needed.

API keys: servers such as omlx require one. To keep secrets out of the
repository and shell history, the loader can discover the key from omlx's own
settings file when ``MINIONS_API_KEY`` is not set (path configurable via
``MINIONS_OMLX_SETTINGS_PATH``). The key is never logged and never written
anywhere by this package.
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


def read_dotenv(path: Path) -> dict[str, str]:
    """Parse a .env file: KEY=VALUE lines, '#' comments, optional quotes.

    Returns {} on any read failure — a missing .env is the common case.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return {}
    values: dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
            value = value[1:-1]
        if key:
            values[key] = value
    return values


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
    dotenv_path: Path | None = Path(".env"),
    omlx_settings_path: Path | None = None,
) -> Settings:
    if env is None:
        dotenv = read_dotenv(dotenv_path) if dotenv_path else {}
        env = {**dotenv, **os.environ}  # process env wins over .env
    defaults = Settings()

    if omlx_settings_path is None:
        raw_omlx = env.get("MINIONS_OMLX_SETTINGS_PATH")
        omlx_settings_path = Path(raw_omlx).expanduser() if raw_omlx else OMLX_SETTINGS_PATH

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
