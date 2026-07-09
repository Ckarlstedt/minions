from __future__ import annotations

import json
from pathlib import Path

import pytest

from minions.config import ConfigError, load_settings

NO_OMLX = Path("/nonexistent/omlx-settings.json")


def test_defaults() -> None:
    settings = load_settings({}, omlx_settings_path=NO_OMLX)
    assert settings.base_url == "http://127.0.0.1:8000/v1"
    assert settings.model == "gpt-oss-20b-MXFP4-Q8"
    assert settings.api_key is None
    assert settings.api_key_source == "none"
    assert settings.max_steps == 16


def test_env_overrides() -> None:
    settings = load_settings(
        {
            "MINIONS_BASE_URL": "http://localhost:9999/v1/",
            "MINIONS_MODEL": "other-model",
            "MINIONS_API_KEY": "sk-test",
            "MINIONS_MAX_STEPS": "5",
            "MINIONS_TEMPERATURE": "0.7",
            "MINIONS_STATE_DIR": "/tmp/minions-test-state",
        },
        omlx_settings_path=NO_OMLX,
    )
    assert settings.base_url == "http://localhost:9999/v1"  # trailing slash stripped
    assert settings.model == "other-model"
    assert settings.api_key == "sk-test"
    assert settings.api_key_source == "MINIONS_API_KEY env"
    assert settings.max_steps == 5
    assert settings.temperature == 0.7
    assert settings.state_dir == Path("/tmp/minions-test-state")


def test_bad_int_raises() -> None:
    with pytest.raises(ConfigError, match="MINIONS_MAX_STEPS"):
        load_settings({"MINIONS_MAX_STEPS": "many"}, omlx_settings_path=NO_OMLX)


def test_omlx_key_discovery(tmp_path: Path) -> None:
    omlx = tmp_path / "settings.json"
    omlx.write_text(json.dumps({"auth": {"api_key": "sk-from-omlx"}}), encoding="utf-8")
    settings = load_settings({}, omlx_settings_path=omlx)
    assert settings.api_key == "sk-from-omlx"
    assert "omlx settings" in settings.api_key_source


def test_env_key_beats_omlx(tmp_path: Path) -> None:
    omlx = tmp_path / "settings.json"
    omlx.write_text(json.dumps({"auth": {"api_key": "sk-from-omlx"}}), encoding="utf-8")
    settings = load_settings({"MINIONS_API_KEY": "sk-env"}, omlx_settings_path=omlx)
    assert settings.api_key == "sk-env"


def test_corrupt_omlx_settings_ignored(tmp_path: Path) -> None:
    omlx = tmp_path / "settings.json"
    omlx.write_text("{not json", encoding="utf-8")
    settings = load_settings({}, omlx_settings_path=omlx)
    assert settings.api_key is None
