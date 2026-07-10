"""Managed edits to minions config files (`minions model`, `minions init`).

Edits are surgical, line-based replacements so hand-written comments survive;
the result is re-parsed and verified before the function returns. The full
config template is embedded here (not read from the repo) because the CLI is
typically installed with `uv tool install` far away from a checkout.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

from minions.config import ConfigError, default_user_config_path

CONFIG_BODY = """\
[provider]
# Any OpenAI-compatible endpoint. Currently developed and tested against omlx;
# other servers (vLLM, Ollama, LM Studio, ...) should work but are unverified.
#base_url = "http://127.0.0.1:8000/v1"          # MINIONS_BASE_URL

# Model id exactly as the server advertises it (`minions doctor` lists what it
# found). Tip: `minions model <name>` edits this line for you.
#model = "gpt-oss-20b-MXFP4-Q8"                 # MINIONS_MODEL

# API key, if the server requires one. With omlx, leave unset: the key is
# auto-discovered from the omlx settings file.
#api_key = ""                                   # MINIONS_API_KEY

# Seconds per model call.
#request_timeout = 180.0                        # MINIONS_REQUEST_TIMEOUT

[provider.omlx]
# omlx-only convenience: when no api_key is configured above, minions tries to
# read the key from omlx's own settings file. Irrelevant for other providers.
#settings_path = "~/.omlx/settings.json"        # MINIONS_OMLX_SETTINGS_PATH

[budgets]
#max_steps = 16                # tool calls per run    (MINIONS_MAX_STEPS)
#context_token_limit = 24000   # stop before server cap (MINIONS_CONTEXT_TOKEN_LIMIT)
#max_tool_output_chars = 8000  # per-tool-result cap   (MINIONS_MAX_TOOL_OUTPUT_CHARS)
#max_completion_tokens = 4096  # includes reasoning    (MINIONS_MAX_COMPLETION_TOKENS)

[sampling]
#temperature = 0.2                 # MINIONS_TEMPERATURE

[trace]
# Where run traces are written (never inside the investigated repository).
#state_dir = "~/.local/state/minions"           # MINIONS_STATE_DIR
"""

USER_CONFIG_TEMPLATE = (
    "# Machine-wide minions configuration (created by `minions init`).\n"
    "# Everything is commented out: built-in defaults apply until you uncomment.\n"
    "# Overridden by MINIONS_* env vars and by a `.env.toml` in the repo you run from;\n"
    "# file layers merge per key.\n\n" + CONFIG_BODY
)

_MODEL_NAME_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/:-]*")
_ACTIVE_MODEL_LINE = re.compile(r"^\s*model\s*=")
_COMMENTED_MODEL_LINE = re.compile(r"^\s*#\s*model\s*=")
_SECTION_LINE = re.compile(r"^\s*\[")
_PROVIDER_LINE = re.compile(r"^\s*\[provider\]\s*(#.*)?$")


def ensure_user_config(path: Path | None = None) -> str:
    """Create the global config (commented template) if absent.

    Returns "created" or "exists".
    """
    path = path or default_user_config_path()
    if path.exists():
        return "exists"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(USER_CONFIG_TEMPLATE, encoding="utf-8")
    return "created"


def set_model(name: str, path: Path) -> None:
    """Set provider.model in `path`, preserving comments and other keys."""
    if not _MODEL_NAME_PATTERN.fullmatch(name):
        raise ConfigError(f"not a valid model id: {name!r}")
    new_line = f'model = "{name}"\n'

    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"[provider]\n{new_line}", encoding="utf-8")
        return

    text = path.read_text(encoding="utf-8")
    try:
        tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"Refusing to edit invalid TOML in {path}: {exc}") from exc

    lines = text.splitlines(keepends=True)
    start = next((i for i, line in enumerate(lines) if _PROVIDER_LINE.match(line)), None)

    if start is None:
        suffix = "" if (not text or text.endswith("\n")) else "\n"
        updated = text + f"{suffix}\n[provider]\n{new_line}"
    else:
        end = next(
            (i for i in range(start + 1, len(lines)) if _SECTION_LINE.match(lines[i])),
            len(lines),
        )
        section = range(start + 1, end)
        active = next((i for i in section if _ACTIVE_MODEL_LINE.match(lines[i])), None)
        if active is not None:
            lines[active] = new_line
        else:
            commented = next((i for i in section if _COMMENTED_MODEL_LINE.match(lines[i])), None)
            if commented is not None:
                lines[commented] = new_line
            else:
                lines.insert(start + 1, new_line)
        updated = "".join(lines)

    parsed = tomllib.loads(updated)  # verify before writing
    if parsed.get("provider", {}).get("model") != name:
        raise ConfigError(f"internal error: failed to set provider.model in {path}")
    path.write_text(updated, encoding="utf-8")
