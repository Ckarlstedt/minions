from __future__ import annotations

import json
from pathlib import Path

import pytest

from minions.config import ConfigError, load_settings

NO_OMLX = Path("/nonexistent/omlx-settings.json")
NO_CONFIG = Path("/nonexistent/.env.toml")


def test_defaults() -> None:
    settings = load_settings({}, config_path=NO_CONFIG, omlx_settings_path=NO_OMLX)
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
        config_path=NO_CONFIG,
        omlx_settings_path=NO_OMLX,
    )
    assert settings.base_url == "http://localhost:9999/v1"  # trailing slash stripped
    assert settings.model == "other-model"
    assert settings.api_key == "sk-test"
    assert settings.api_key_source == "MINIONS_API_KEY env"
    assert settings.max_steps == 5
    assert settings.temperature == 0.7
    assert settings.state_dir == Path("/tmp/minions-test-state")


def test_bad_env_int_raises() -> None:
    with pytest.raises(ConfigError, match="MINIONS_MAX_STEPS"):
        load_settings(
            {"MINIONS_MAX_STEPS": "many"}, config_path=NO_CONFIG, omlx_settings_path=NO_OMLX
        )


def test_config_file_values(tmp_path: Path) -> None:
    config = tmp_path / ".env.toml"
    config.write_text(
        """
        [provider]
        base_url = "http://filehost:1234/v1"
        model = "file-model"
        api_key = "sk-file"
        request_timeout = 60.0

        [budgets]
        max_steps = 4

        [sampling]
        temperature = 0.9

        [trace]
        state_dir = "~/minions-traces"
        """,
        encoding="utf-8",
    )
    settings = load_settings({}, config_path=config, omlx_settings_path=NO_OMLX)
    assert settings.base_url == "http://filehost:1234/v1"
    assert settings.model == "file-model"
    assert settings.api_key == "sk-file"
    assert settings.api_key_source.endswith(".env.toml provider.api_key")
    assert settings.request_timeout == 60.0
    assert settings.max_steps == 4
    assert settings.temperature == 0.9
    assert settings.state_dir == Path("~/minions-traces").expanduser()


def test_env_beats_config_file(tmp_path: Path) -> None:
    config = tmp_path / ".env.toml"
    config.write_text('[provider]\nmodel = "from-file"\n\n[budgets]\nmax_steps = 3\n')
    settings = load_settings(
        {"MINIONS_MAX_STEPS": "7"}, config_path=config, omlx_settings_path=NO_OMLX
    )
    assert settings.model == "from-file"
    assert settings.max_steps == 7  # process env wins


def test_missing_config_file_is_fine() -> None:
    settings = load_settings({}, config_path=NO_CONFIG, omlx_settings_path=NO_OMLX)
    assert settings.model == "gpt-oss-20b-MXFP4-Q8"


def test_malformed_config_file_raises(tmp_path: Path) -> None:
    config = tmp_path / ".env.toml"
    config.write_text("[provider\nmodel = ", encoding="utf-8")
    with pytest.raises(ConfigError, match="Invalid TOML"):
        load_settings({}, config_path=config, omlx_settings_path=NO_OMLX)


def test_wrong_type_in_config_file_raises(tmp_path: Path) -> None:
    config = tmp_path / ".env.toml"
    config.write_text('[budgets]\nmax_steps = "lots"\n', encoding="utf-8")
    with pytest.raises(ConfigError, match="max_steps"):
        load_settings({}, config_path=config, omlx_settings_path=NO_OMLX)


def test_user_config_used_when_no_local(tmp_path: Path) -> None:
    user = tmp_path / "config.toml"
    user.write_text('[provider]\nmodel = "global-model"\n', encoding="utf-8")
    settings = load_settings(
        {}, config_path=NO_CONFIG, user_config_path=user, omlx_settings_path=NO_OMLX
    )
    assert settings.model == "global-model"


def test_local_beats_user_per_key_not_per_file(tmp_path: Path) -> None:
    user = tmp_path / "config.toml"
    user.write_text(
        '[provider]\nmodel = "global-model"\napi_key = "sk-global"\n'
        "[budgets]\nmax_steps = 9\n",
        encoding="utf-8",
    )
    local = tmp_path / ".env.toml"
    local.write_text('[provider]\nmodel = "repo-model"\n', encoding="utf-8")
    settings = load_settings(
        {}, config_path=local, user_config_path=user, omlx_settings_path=NO_OMLX
    )
    assert settings.model == "repo-model"  # local wins the contested key
    assert settings.api_key == "sk-global"  # sibling key inherited from global
    assert "config.toml provider.api_key" in settings.api_key_source
    assert settings.max_steps == 9  # whole table inherited from global


def test_env_beats_both_files(tmp_path: Path) -> None:
    user = tmp_path / "config.toml"
    user.write_text('[provider]\nmodel = "global-model"\n', encoding="utf-8")
    local = tmp_path / ".env.toml"
    local.write_text('[provider]\nmodel = "repo-model"\n', encoding="utf-8")
    settings = load_settings(
        {"MINIONS_MODEL": "env-model"},
        config_path=local,
        user_config_path=user,
        omlx_settings_path=NO_OMLX,
    )
    assert settings.model == "env-model"


def test_default_user_config_path_respects_xdg(monkeypatch, tmp_path: Path) -> None:
    from minions.config import default_user_config_path

    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    assert default_user_config_path() == tmp_path / "xdg" / "minions" / "config.toml"


def test_omlx_subtable_merges_across_files(tmp_path: Path) -> None:
    omlx = tmp_path / "custom-omlx.json"
    omlx.write_text(json.dumps({"auth": {"api_key": "sk-global-omlx"}}), encoding="utf-8")
    user = tmp_path / "config.toml"
    user.write_text(f'[provider.omlx]\nsettings_path = "{omlx}"\n', encoding="utf-8")
    settings = load_settings({}, config_path=NO_CONFIG, user_config_path=user)
    assert settings.api_key == "sk-global-omlx"


def test_omlx_key_discovery(tmp_path: Path) -> None:
    omlx = tmp_path / "settings.json"
    omlx.write_text(json.dumps({"auth": {"api_key": "sk-from-omlx"}}), encoding="utf-8")
    settings = load_settings({}, config_path=NO_CONFIG, omlx_settings_path=omlx)
    assert settings.api_key == "sk-from-omlx"
    assert "omlx settings" in settings.api_key_source


def test_omlx_settings_path_via_config_file(tmp_path: Path) -> None:
    omlx = tmp_path / "custom-omlx.json"
    omlx.write_text(json.dumps({"auth": {"api_key": "sk-custom"}}), encoding="utf-8")
    config = tmp_path / ".env.toml"
    config.write_text(f'[provider.omlx]\nsettings_path = "{omlx}"\n', encoding="utf-8")
    settings = load_settings({}, config_path=config)
    assert settings.api_key == "sk-custom"


def test_env_key_beats_omlx(tmp_path: Path) -> None:
    omlx = tmp_path / "settings.json"
    omlx.write_text(json.dumps({"auth": {"api_key": "sk-from-omlx"}}), encoding="utf-8")
    settings = load_settings(
        {"MINIONS_API_KEY": "sk-env"}, config_path=NO_CONFIG, omlx_settings_path=omlx
    )
    assert settings.api_key == "sk-env"


def test_corrupt_omlx_settings_ignored(tmp_path: Path) -> None:
    omlx = tmp_path / "settings.json"
    omlx.write_text("{not json", encoding="utf-8")
    settings = load_settings({}, config_path=NO_CONFIG, omlx_settings_path=omlx)
    assert settings.api_key is None
