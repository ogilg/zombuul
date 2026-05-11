#!/usr/bin/env python3
"""Validate plugin.json, marketplace.json, and every SKILL.md frontmatter.

Stdlib-only. Exits non-zero on any failure with one FAIL line per issue.
Intended to run in CI before a release ships.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

FAILURES: list[str] = []

MAIN_VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")
DEV_VERSION_RE = re.compile(r"^\d+\.\d+\.\d+-dev(?:\.\d+)?$")
MAIN_MARKETPLACE_NAME = "ogilg-marketplace"
DEV_MARKETPLACE_NAME = "ogilg-marketplace-dev"


def fail(msg: str) -> None:
    FAILURES.append(msg)


def validate_target_branch(target: str) -> None:
    """Assert plugin.json version and marketplace.json name match the target branch's
    invariants. Prevents dev-only state from leaking into a main release (or vice versa)."""
    plugin_path = REPO_ROOT / ".claude-plugin" / "plugin.json"
    market_path = REPO_ROOT / ".claude-plugin" / "marketplace.json"
    try:
        plugin = json.loads(plugin_path.read_text())
        market = json.loads(market_path.read_text())
    except (FileNotFoundError, json.JSONDecodeError) as e:
        fail(f"target={target}: cannot read manifests — {e}")
        return
    version = plugin.get("version", "")
    name = market.get("name", "")
    if target == "main":
        if not MAIN_VERSION_RE.match(version):
            fail(
                f"{plugin_path}: version '{version}' is not strict semver (X.Y.Z). "
                "Main must not carry a '-dev' suffix — did a dev→main release skip "
                "`git checkout main -- .claude-plugin/{marketplace,plugin}.json`?"
            )
        if name != MAIN_MARKETPLACE_NAME:
            fail(
                f"{market_path}: marketplace name is '{name}', expected "
                f"'{MAIN_MARKETPLACE_NAME}'. Dev's marketplace rename leaked into main."
            )
    elif target == "dev":
        if not DEV_VERSION_RE.match(version):
            fail(
                f"{plugin_path}: version '{version}' must match "
                "'X.Y.Z-dev' or 'X.Y.Z-dev.N' on the dev branch."
            )
        if name != DEV_MARKETPLACE_NAME:
            fail(
                f"{market_path}: marketplace name is '{name}', expected "
                f"'{DEV_MARKETPLACE_NAME}' on the dev branch."
            )
    else:
        fail(f"validate_target_branch: unknown target '{target}'")


def validate_plugin_json() -> None:
    path = REPO_ROOT / ".claude-plugin" / "plugin.json"
    if not path.exists():
        fail(f"{path}: missing")
        return
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as e:
        fail(f"{path}: invalid JSON — {e}")
        return
    for key in ("name", "version", "description", "repository", "license"):
        if key not in data:
            fail(f"{path}: missing required key '{key}'")


def validate_marketplace_json() -> None:
    path = REPO_ROOT / ".claude-plugin" / "marketplace.json"
    if not path.exists():
        fail(f"{path}: missing")
        return
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as e:
        fail(f"{path}: invalid JSON — {e}")
        return
    for key in ("name", "owner", "plugins"):
        if key not in data:
            fail(f"{path}: missing required key '{key}'")
    plugins = data.get("plugins", [])
    if not isinstance(plugins, list) or not plugins:
        fail(f"{path}: 'plugins' must be a non-empty array")
        return
    for i, p in enumerate(plugins):
        for key in ("name", "source", "description"):
            if key not in p:
                fail(f"{path}: plugins[{i}] missing required key '{key}'")


_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL)
_TOP_LEVEL_KEY_RE = re.compile(r"^([a-zA-Z][a-zA-Z0-9_-]*):", re.MULTILINE)


def split_frontmatter(text: str) -> tuple[str, str] | None:
    """Return (frontmatter_block, body) or None if no frontmatter."""
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return None
    return m.group(1), m.group(2)


def frontmatter_keys(frontmatter: str) -> set[str]:
    """Return the set of top-level keys (lines starting at column 0 with `key:`).

    This is a permissive parser: it ignores values, multi-line folded scalars,
    and comments. We only need to know which keys are present.
    """
    return {m.group(1) for m in _TOP_LEVEL_KEY_RE.finditer(frontmatter)}


def frontmatter_value(frontmatter: str, key: str) -> str | None:
    """Return the raw single-line value for `key`, or None if not single-line."""
    pat = re.compile(rf"^{re.escape(key)}:\s*(.+?)\s*$", re.MULTILINE)
    m = pat.search(frontmatter)
    if not m:
        return None
    val = m.group(1).strip()
    # Skip multi-line indicators (folded/literal scalars).
    if val in (">", "|", ">-", "|-"):
        return None
    return val


def validate_skills() -> None:
    skills_dir = REPO_ROOT / "skills"
    if not skills_dir.exists():
        fail(f"{skills_dir}: missing")
        return
    for skill_dir in sorted(skills_dir.iterdir()):
        if not skill_dir.is_dir():
            continue
        skill_md = skill_dir / "SKILL.md"
        rel = skill_md.relative_to(REPO_ROOT)
        if not skill_md.exists():
            fail(f"{rel}: missing")
            continue
        text = skill_md.read_text()
        split = split_frontmatter(text)
        if split is None:
            fail(f"{rel}: missing or malformed YAML frontmatter (expected ---/---)")
            continue
        frontmatter, body = split
        keys = frontmatter_keys(frontmatter)
        for required in ("name", "description", "user-invocable"):
            if required not in keys:
                fail(f"{rel}: missing required frontmatter field '{required}'")
        name_val = frontmatter_value(frontmatter, "name")
        expected_name = f"zombuul:{skill_dir.name}"
        if name_val is not None and name_val != expected_name:
            fail(
                f"{rel}: name '{name_val}' does not match expected "
                f"'{expected_name}' (skill directory: {skill_dir.name})"
            )
        if "argument-hint" in keys and "$ARGUMENTS" not in body:
            fail(
                f"{rel}: declares 'argument-hint' but body does not reference "
                f"$ARGUMENTS"
            )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--target",
        choices=("main", "dev"),
        help="Also assert version/marketplace-name invariants for the given target branch.",
    )
    args = parser.parse_args()

    validate_plugin_json()
    validate_marketplace_json()
    validate_skills()
    if args.target:
        validate_target_branch(args.target)
    if FAILURES:
        for line in FAILURES:
            print(f"FAIL: {line}")
        print(f"\n{len(FAILURES)} validation failure(s).", file=sys.stderr)
        return 1
    suffix = f" (target={args.target})" if args.target else ""
    print(f"OK: plugin.json, marketplace.json, and all SKILL.md files validate{suffix}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
