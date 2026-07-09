"""CLI adapter: `minions investigate` and `minions doctor`.

Exit codes (stable contract for GRU-side scripting, see AGENTS.md):
  0  investigation complete or partial (report on stdout)
  1  configuration / infrastructure error (message on stderr)
  2  investigation ran but failed to produce a report
"""

from __future__ import annotations

import argparse
import dataclasses
import logging
import sys
from pathlib import Path

from minions import __version__
from minions.config import ConfigError, Settings, load_settings
from minions.providers.base import ProviderError
from minions.providers.openai_compat import OpenAICompatProvider
from minions.service import InvestigationService
from minions.tools.workspace import Workspace


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )
    try:
        settings = load_settings()
        if args.command == "investigate":
            return _investigate(args, settings)
        return _doctor(args, settings)
    except (ConfigError, ProviderError, NotADirectoryError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="minions",
        description="Delegate repository investigation to a cheap local model; "
        "get a compact, citation-verified report back.",
    )
    parser.add_argument("--version", action="version", version=f"minions {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    investigate = subparsers.add_parser("investigate", help="run one investigation")
    investigate.add_argument("question", help="the question to investigate")
    investigate.add_argument("--repo", default=".", help="repository root (default: cwd)")
    investigate.add_argument("--json", action="store_true", help="emit the full JSON report")
    investigate.add_argument("--max-steps", type=int, default=None, help="tool-call budget")
    investigate.add_argument("-v", "--verbose", action="store_true")

    doctor = subparsers.add_parser("doctor", help="check server, config and environment")
    doctor.add_argument("--repo", default=".", help="repository root to check (default: cwd)")
    doctor.add_argument("-v", "--verbose", action="store_true")
    return parser


def _investigate(args: argparse.Namespace, settings: Settings) -> int:
    if args.max_steps is not None:
        settings = dataclasses.replace(settings, max_steps=args.max_steps)
    service = InvestigationService(settings)
    report = service.investigate(args.question, repo=args.repo)

    if args.json:
        print(report.model_dump_json(indent=2))
    else:
        print(report.to_markdown())
    if report.stats and report.stats.trace_path:
        print(f"trace: {report.stats.trace_path}", file=sys.stderr)
    return 0 if report.status in ("complete", "partial") else 2


def _doctor(args: argparse.Namespace, settings: Settings) -> int:
    failed = False

    def check(label: str, ok: bool, detail: str, *, critical: bool = True) -> None:
        nonlocal failed
        mark = "ok" if ok else ("FAIL" if critical else "warn")
        failed = failed or (not ok and critical)
        print(f"[{mark:>4}] {label}: {detail}")

    check(
        "python",
        sys.version_info >= (3, 12),
        f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
    )
    print(f"[info] server: {settings.base_url}")
    print(f"[info] model: {settings.model}")
    check(
        "api key",
        settings.api_key is not None,
        settings.api_key_source
        if settings.api_key
        else "not found — set MINIONS_API_KEY (or run omlx, whose key is auto-discovered)",
        critical=False,
    )

    provider = OpenAICompatProvider(settings)
    try:
        models = provider.list_models()
        check("server reachable", True, f"{len(models)} model(s) listed")
        check(
            "model available",
            settings.model in models,
            settings.model if settings.model in models else f"not in {models}",
            critical=False,
        )
    except ProviderError as exc:
        check("server reachable", False, str(exc))
    finally:
        provider.close()

    try:
        workspace = Workspace.discover(Path(args.repo))
        kind = "git" if workspace.is_git else "not a git repo — git tools disabled"
        check("workspace", True, f"{workspace.root} ({kind})")
    except NotADirectoryError as exc:
        check("workspace", False, str(exc))

    try:
        runs_dir = settings.state_dir / "runs"
        runs_dir.mkdir(parents=True, exist_ok=True)
        probe = runs_dir / ".doctor-probe"
        probe.write_text("ok")
        probe.unlink()
        check("state dir writable", True, str(settings.state_dir))
    except OSError as exc:
        check("state dir writable", False, f"{settings.state_dir}: {exc}")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
