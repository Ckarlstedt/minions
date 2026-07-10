"""Runtime configuration.

Sources, in precedence order:

1. ``MINIONS_*`` process environment variables (one-off overrides, CI)
2. ``.env.toml`` in the current working directory (gitignored; copy
   ``.env.example.toml`` to create one)
3. built-in defaults (targeting a local OpenAI-compatible server)

TOML was chosen for the config file because values arrive typed (ints stay
ints), comments are first-class, and ``tomllib`` is stdlib — no dependency.
A missing ``.env.toml`` is fine; a malformed one is a hard ConfigError
(silent misconfiguration is worse than a crash).

API keys: servers such as omlx require one. To keep secrets out of the
repository and shell history, the loader can discover the key from omlx's own
settings file when no key is configured. This discovery is omlx-specific —
other providers have no such file — which is why it lives under the
``[provider.omlx]`` table and the ``MINIONS_OMLX_SETTINGS_PATH`` variable.
The key is never logged and never written anywhere by this package.
"""

from __future__ import annotations

import json
import os
import tomllib
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_BASE_URL = "http://127.0.0.1:8000/v1"
# omlx advertises models without the HF org prefix.
DEFAULT_MODEL = "gpt-oss-20b-MXFP4-Q8"

DEFAULT_CONFIG_PATH = Path(".env.toml")
OMLX_SETTINGS_PATH = Path.home() / ".omlx" / "settings.json"


class ConfigError(Exception):
    """Raised when configuration values cannot be read or parsed."""


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

    # Budgets. Local servers cap context (omlx: 32k tokens); the loop
    # force-finishes before that wall so the report never gets truncated.
    max_steps: int = 16
    context_token_limit: int = 24_000
    max_tool_output_chars: int = 8_000
    max_completion_tokens: int = 4_096

    temperature: float = 0.2
    request_timeout: float = 180.0
    state_dir: Path = field(default_factory=default_state_dir)


def read_config_file(path: Path) -> dict:
    """Read .env.toml. Missing file → {}; malformed file → ConfigError."""
    try:
        with path.open("rb") as handle:
            return tomllib.load(handle)
    except FileNotFoundError:
        return {}
    except OSError as exc:
        raise ConfigError(f"Cannot read {path}: {exc}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"Invalid TOML in {path}: {exc}") from exc


def discover_omlx_api_key(settings_path: Path = OMLX_SETTINGS_PATH) -> str | None:
    """Best-effort read of the omlx server's own API key. Returns None on any failure.

    omlx-specific convenience: other providers have no equivalent settings file.
    """
    try:
        data = json.loads(settings_path.read_text(encoding="utf-8"))
        key = data.get("auth", {}).get("api_key")
    except (OSError, ValueError, AttributeError):
        return None
    if isinstance(key, str) and key.strip():
        return key.strip()
    return None


def _as_str(value: object, origin: str) -> str:
    if not isinstance(value, str):
        raise ConfigError(f"{origin} must be a string, got {value!r}")
    return value


def _as_int(value: object, origin: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int | str):
        raise ConfigError(f"{origin} must be an integer, got {value!r}")
    try:
        return int(value)
    except ValueError as exc:
        raise ConfigError(f"{origin} must be an integer, got {value!r}") from exc


def _as_float(value: object, origin: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float | str):
        raise ConfigError(f"{origin} must be a number, got {value!r}")
    try:
        return float(value)
    except ValueError as exc:
        raise ConfigError(f"{origin} must be a number, got {value!r}") from exc


def _table(config: dict, name: str) -> dict:
    value = config.get(name, {})
    if not isinstance(value, dict):
        raise ConfigError(f"[{name}] in .env.toml must be a table")
    return value


def load_settings(
    env: Mapping[str, str] | None = None,
    *,
    config_path: Path | None = DEFAULT_CONFIG_PATH,
    omlx_settings_path: Path | None = None,
) -> Settings:
    env = os.environ if env is None else env
    config = read_config_file(config_path) if config_path else {}
    provider = _table(config, "provider")
    omlx = _table(provider, "omlx")
    budgets = _table(config, "budgets")
    sampling = _table(config, "sampling")
    trace = _table(config, "trace")
    defaults = Settings()

    def pick[T](env_key: str, table: dict, file_key: str, fallback: T, cast: Callable[..., T]) -> T:
        if env_key in env:
            return cast(env[env_key], f"{env_key} env var")
        if file_key in table:
            return cast(table[file_key], f"{file_key} in .env.toml")
        return fallback

    if omlx_settings_path is None:
        raw = pick("MINIONS_OMLX_SETTINGS_PATH", omlx, "settings_path", None, _as_str)
        omlx_settings_path = Path(raw).expanduser() if raw else OMLX_SETTINGS_PATH

    api_key: str | None
    if "MINIONS_API_KEY" in env:
        api_key = env["MINIONS_API_KEY"]
        api_key_source = "MINIONS_API_KEY env"
    elif "api_key" in provider:
        api_key = _as_str(provider["api_key"], "api_key in .env.toml")
        api_key_source = ".env.toml provider.api_key"
    else:
        api_key = discover_omlx_api_key(omlx_settings_path)
        api_key_source = f"omlx settings ({omlx_settings_path})" if api_key else "none"

    state_dir_raw = pick("MINIONS_STATE_DIR", trace, "state_dir", None, _as_str)

    return Settings(
        base_url=pick(
            "MINIONS_BASE_URL", provider, "base_url", defaults.base_url, _as_str
        ).rstrip("/"),
        model=pick("MINIONS_MODEL", provider, "model", defaults.model, _as_str),
        api_key=api_key,
        api_key_source=api_key_source,
        max_steps=pick("MINIONS_MAX_STEPS", budgets, "max_steps", defaults.max_steps, _as_int),
        context_token_limit=pick(
            "MINIONS_CONTEXT_TOKEN_LIMIT",
            budgets,
            "context_token_limit",
            defaults.context_token_limit,
            _as_int,
        ),
        max_tool_output_chars=pick(
            "MINIONS_MAX_TOOL_OUTPUT_CHARS",
            budgets,
            "max_tool_output_chars",
            defaults.max_tool_output_chars,
            _as_int,
        ),
        max_completion_tokens=pick(
            "MINIONS_MAX_COMPLETION_TOKENS",
            budgets,
            "max_completion_tokens",
            defaults.max_completion_tokens,
            _as_int,
        ),
        temperature=pick(
            "MINIONS_TEMPERATURE", sampling, "temperature", defaults.temperature, _as_float
        ),
        request_timeout=pick(
            "MINIONS_REQUEST_TIMEOUT",
            provider,
            "request_timeout",
            defaults.request_timeout,
            _as_float,
        ),
        state_dir=Path(state_dir_raw).expanduser() if state_dir_raw else defaults.state_dir,
    )
