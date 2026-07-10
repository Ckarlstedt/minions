from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

from minions.cli import main
from minions.config import ConfigError
from minions.config_edit import CONFIG_BODY, ensure_user_config, set_model


def test_ensure_user_config_creates_valid_commented_template(tmp_path: Path) -> None:
    path = tmp_path / "config" / "minions" / "config.toml"
    assert ensure_user_config(path) == "created"
    parsed = tomllib.loads(path.read_text())
    # Fully commented: parses to empty tables, so built-in defaults apply.
    assert parsed == {"provider": {"omlx": {}}, "budgets": {}, "sampling": {}, "trace": {}}
    assert ensure_user_config(path) == "exists"


def test_example_file_matches_embedded_template() -> None:
    example = Path(__file__).parent.parent / ".env.example.toml"
    assert example.read_text().endswith(CONFIG_BODY)


def test_set_model_creates_file(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "config.toml"
    set_model("my-model", path)
    assert tomllib.loads(path.read_text())["provider"]["model"] == "my-model"


def test_set_model_uncomments_template_line(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    ensure_user_config(path)
    set_model("new-model", path)
    text = path.read_text()
    assert tomllib.loads(text)["provider"]["model"] == "new-model"
    # Comments elsewhere survived, and no duplicate model lines appeared.
    assert "# omlx-only convenience" in text
    assert text.count('model = "new-model"') == 1


def test_set_model_replaces_active_line_preserving_rest(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    path.write_text(
        "# my comment\n[provider]\nmodel = \"old\"\napi_key = \"sk-x\"\n\n"
        "[budgets]\nmax_steps = 4\n",
        encoding="utf-8",
    )
    set_model("new", path)
    parsed = tomllib.loads(path.read_text())
    assert parsed["provider"] == {"model": "new", "api_key": "sk-x"}
    assert parsed["budgets"] == {"max_steps": 4}
    assert path.read_text().startswith("# my comment")


def test_set_model_appends_provider_section_when_missing(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    path.write_text("[budgets]\nmax_steps = 4\n", encoding="utf-8")
    set_model("m", path)
    parsed = tomllib.loads(path.read_text())
    assert parsed["provider"]["model"] == "m"
    assert parsed["budgets"]["max_steps"] == 4


def test_set_model_does_not_touch_omlx_subtable(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    path.write_text('[provider.omlx]\nsettings_path = "/x"\n', encoding="utf-8")
    set_model("m", path)
    parsed = tomllib.loads(path.read_text())
    assert parsed["provider"]["model"] == "m"
    assert parsed["provider"]["omlx"]["settings_path"] == "/x"


def test_set_model_rejects_bad_name(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="not a valid model id"):
        set_model('bad"name\n[x]', tmp_path / "config.toml")


def test_set_model_refuses_invalid_toml(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    path.write_text("[provider\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="Refusing to edit"):
        set_model("m", path)


def test_cli_model_show_and_set(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)  # keep --local writes inside the tmp dir
    monkeypatch.delenv("MINIONS_MODEL", raising=False)

    assert main(["model"]) == 0
    assert "built-in default" in capsys.readouterr().out

    assert main(["model", "global-model"]) == 0
    out = capsys.readouterr().out
    assert "(global)" in out and "config.toml" in out

    assert main(["model", "repo-model", "--local"]) == 0
    assert "(this repo)" in capsys.readouterr().out
    assert tomllib.loads((tmp_path / ".env.toml").read_text())["provider"]["model"] == "repo-model"

    assert main(["model"]) == 0
    out = capsys.readouterr().out
    assert "repo-model" in out and ".env.toml" in out


def test_cli_init_creates_global_config(tmp_path: Path, monkeypatch, capsys) -> None:
    from minions.config import default_user_config_path

    repo = tmp_path / "repo"
    repo.mkdir()
    assert main(["init", "--repo", str(repo)]) == 0
    out = capsys.readouterr().out
    assert default_user_config_path().exists()
    assert "created" in out and "config.toml" in out
