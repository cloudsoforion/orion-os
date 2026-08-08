#!/usr/bin/env python3
"""
vault_config.py — the one place that knows the vault's shape.

Reads `vault.json` at the vault root and hands every tool the same answers:
where the vault is, what the pillar folders are called, which tag prefixes the
frontmatter contract uses, and which directories to walk past. Reads nothing
else and writes nothing.

Why this module exists — the `archive-folders` post-mortem
(the `archive-folders` post-mortem) named the cause of death:

    "it encoded the vault's shape in 2026-02 and had no way to notice the vault
     had changed. A tool that hardcodes a taxonomy inherits every reorg as a
     silent bug."

Before this module, `find_vault_root` was copy-pasted into two tools and missing
from a third, and four tools each declared their own slightly different skip-dir
set. Any folder renumber had to be chased through all of them by hand.

Usage:
  # As a library, from a tool at 03-Resources/tools/<tool>/<tool>.py
  import sys
  from pathlib import Path
  sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
  import vault_config

  root = vault_config.find_vault_root(Path.cwd())
  cfg  = vault_config.load_config(root)

  # As a command, to see what a tool would resolve (which vault.json won?)
  python3 vault_config.py
  python3 vault_config.py --vault ~/notes/some-other-vault

Resolution rules:
  find_vault_root  walks up from `start` for the first directory containing
                   `.obsidian/`. Returns None if there is none — callers that
                   need a value supply their own fallback, so this function
                   never guesses.
  load_config      merges `<vault-root>/vault.json` over DEFAULTS, one level
                   deep. A missing or unreadable file is not an error: the
                   defaults describe a stock vault, so a bare clone works.
"""

import argparse
import copy
import json
import re
import sys
from datetime import datetime
from pathlib import Path

CONFIG_NAME = "vault.json"

# The vault's two date-in-name forms. YYYYMMDDHHMM is what `stamp-out` and
# `vault-indexer` write; YYYYMMDD is the plain note prefix.
TIMESTAMP_RE = re.compile(r"(?<!\d)(\d{12})(?!\d)")
DATE_RE = re.compile(r"(?<!\d)(\d{8})(?!\d)")

# A calendar-valid date can still be an identifier that happens to be 8 digits.
# Anything outside this range is treated as a number, not a date.
MIN_YEAR, MAX_YEAR = 1990, 2099

# A stock vault. Every key here is what a tool gets when there is no vault.json,
# which is also the shape the public template ships with.
DEFAULTS = {
    "pillars": {
        "inbox": "00-Inbox",
        "areas": "01-Areas",
        "projects": "02-Projects",
        "resources": "03-Resources",
        "archive": "04-Archive",
    },
    "log_dir": "Log",
    "changelog_dir": "CHANGELOG",
    "templates_dir": "templates",
    "tag_prefixes": {
        "created": "created/",
        "updated": "updated/",
        "archived": "archived/",
        "type": "type/",
        "domain": "domain/",
        "status": "status/",
    },
    "default_domain": "knowledge-management",
    "author": "",
    # Stale-prefix -> current-prefix rewrites for wikilink repair. Empty by design:
    # a baked-in remap is a hardcoded taxonomy, which is what killed archive-folders.
    "link_remaps": {},
    # Vault-relative globs whose links are reported but not actionable — generated
    # notes that cite historical paths on purpose.
    "exclude_paths": [],
    "skip_hidden_dirs": True,
    "skip_dirs": [
        ".git", ".obsidian", ".trash", ".idea", ".claude", ".venv",
        ".pytest_cache", "node_modules", "__pycache__",
    ],
}


def find_vault_root(start: Path) -> Path | None:
    """First directory at or above `start` that contains `.obsidian/`.

    Returns None rather than guessing — a tool that needs a definite path
    writes `find_vault_root(x) or x.resolve()` so the fallback is visible at
    the call site instead of hidden in here.
    """
    start = Path(start).resolve()
    for candidate in [start, *start.parents]:
        if (candidate / ".obsidian").is_dir():
            return candidate
    return None


def _merge(base: dict, override: dict) -> dict:
    """Override `base` with `override`, recursing into nested dicts.

    Nested rather than flat so a vault.json can rename one pillar without
    having to restate the other four.
    """
    result = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _merge(result[key], value)
        else:
            result[key] = value
    return result


def load_config(vault_root: Path | None = None, config_path: Path | None = None) -> dict:
    """DEFAULTS with `<vault_root>/vault.json` merged over the top.

    An absent file returns DEFAULTS unchanged. A malformed one raises — a
    typo in the taxonomy should stop the run, not silently fall back to a
    different taxonomy than the one the author wrote down.
    """
    if config_path is None:
        if vault_root is None:
            return copy.deepcopy(DEFAULTS)
        config_path = Path(vault_root) / CONFIG_NAME

    if not Path(config_path).is_file():
        return copy.deepcopy(DEFAULTS)

    with open(config_path, encoding="utf-8") as handle:
        override = json.load(handle)
    if not isinstance(override, dict):
        raise ValueError(f"{config_path}: expected a JSON object at the top level")

    return _merge(DEFAULTS, override)


def is_skipped_dir(name: str, config: dict) -> bool:
    """True if a directory named `name` should not be walked into.

    Hidden directories are skipped by default (`skip_hidden_dirs`), which is
    what keeps `.pytest_cache/README.md` and stale `.claude/worktrees/` copies
    out of vault scans. `skip_dirs` lists the rest by name and still names the
    hidden ones explicitly so the file documents itself.
    """
    if config.get("skip_hidden_dirs", True) and name.startswith("."):
        return True
    return name in set(config.get("skip_dirs", ()))


def prune_dirs(dirnames: list[str], config: dict) -> None:
    """In-place filter for the `dirnames` list yielded by os.walk()."""
    dirnames[:] = [d for d in dirnames if not is_skipped_dir(d, config)]


def date_from_text(text: str) -> str | None:
    """First `YYYYMMDD` in `text`, accepting the vault's `YYYYMMDDHHMM` stamp too.

    The 12-digit form is tried first, deliberately. A bare `\\d{8}` never matches
    inside a 12-digit run (a digit follows it), so those names looked undated;
    and where a name holds both — e.g.
    `202605291147-20250529-20260529-range-summary.md` — matching 8 digits first
    picks an embedded *content* date over the file's own creation stamp.

    Validated with `strptime`, so `20260231` is rejected rather than accepted as
    a plausible-looking string, and bounded to MIN_YEAR..MAX_YEAR so an 8-digit
    identifier like `12340506` is not mistaken for a date.
    """
    for pattern, fmt in ((TIMESTAMP_RE, "%Y%m%d%H%M"), (DATE_RE, "%Y%m%d")):
        for match in pattern.finditer(text):
            try:
                parsed = datetime.strptime(match.group(1), fmt)
            except ValueError:
                continue
            if not MIN_YEAR <= parsed.year <= MAX_YEAR:
                continue
            return match.group(1)[:8]
    return None


def tag(config: dict, kind: str, value: str) -> str:
    """Build a namespaced tag, e.g. tag(cfg, "created", "20260808") -> 'created/20260808'."""
    prefixes = config.get("tag_prefixes", {})
    if kind not in prefixes:
        raise KeyError(f"unknown tag prefix {kind!r}; known: {sorted(prefixes)}")
    return f"{prefixes[kind]}{value}"


def main():
    parser = argparse.ArgumentParser(
        description="Print the vault root and merged config a tool would resolve."
    )
    parser.add_argument("--vault", type=Path, help="Vault root (auto-detected from .obsidian if omitted)")
    parser.add_argument("--start", type=Path, default=Path.cwd(),
                        help="Where to start the upward search (default: cwd)")
    args = parser.parse_args()

    root = args.vault or find_vault_root(args.start)
    if root is None:
        print(f"No vault found at or above {args.start.resolve()} "
              f"(looking for a directory containing .obsidian/)", file=sys.stderr)
        return 1

    config_path = root / CONFIG_NAME
    print(f"vault root:  {root}", file=sys.stderr)
    print(f"config file: {config_path if config_path.is_file() else '(none — using DEFAULTS)'}",
          file=sys.stderr)
    print(json.dumps(load_config(root), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
