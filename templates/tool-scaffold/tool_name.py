#!/usr/bin/env python3
"""<One line: what this tool does.>

Reads:  <what it reads — vault paths, a DB, stdin>
Writes: <what it writes — exact path template, or "nothing without --apply">

<If behaviour is a decision table (date resolution, path mapping, link rewriting), write the
table HERE and mirror it in the test module. The test module is the specification of record.
See process_frontmatter.py for the pattern.>

Usage:
    # Preview every change without touching the vault (default)
    python3 <tool_name>.py --dry-run

    # Actually apply
    python3 <tool_name>.py --apply

    # Restrict to part of the vault
    python3 <tool_name>.py --dry-run --folders 00-Inbox/work 02-Projects

Configuration:
    Folder names, tag prefixes, `author`, and skip-dirs all come from vault.json via
    vault_config. Do not hardcode them — see CONTRIBUTING § The shared config module.
"""

import argparse
import sys
from pathlib import Path

def _tools_dir() -> Path:
    """Locate 03-Resources/tools/ so `vault_config` can be imported.

    The only bootstrap allowed to walk the tree itself — it runs *before* the module
    that owns walking the tree is importable. Two cases, in order:

      1. Already copied into a tool directory: `parent.parent` is the tools dir.
      2. Still sitting in templates/tool-scaffold/: walk up for `vault.json` and
         take the tools dir from the vault root, so the scaffold's own suite runs
         in place instead of failing on the import.

    Note what this deliberately does *not* do: count directories. `parents[3]` is
    correct at exactly one depth and wrong silently everywhere else — from this
    file's own location it resolved to `~/Documents`.
    """
    here = Path(__file__).resolve()
    sibling = here.parent.parent
    if (sibling / "vault_config.py").is_file():
        return sibling
    for candidate in here.parents:
        if (candidate / "vault.json").is_file():
            return candidate / "03-Resources" / "tools"
    return sibling


# The one shared module. It owns vault-root discovery, the pillar folder names, the
# frontmatter tag prefixes, the default `author`, and the skip-dir set — declare none
# of those here. See CONTRIBUTING § The shared config module.
sys.path.insert(0, str(_tools_dir()))
import vault_config  # noqa: E402

VAULT_ROOT = vault_config.find_vault_root(Path(__file__)) or Path.cwd()
CONFIG = vault_config.load_config(VAULT_ROOT)


# --- pure functions -------------------------------------------------------
# Keep parsing/mapping/formatting free of I/O so they are cheap to test.
# This split is what makes the existing suites small and fast.


def transform(value: str) -> str:
    """<What this computes, and the one edge case that isn't obvious.>"""
    raise NotImplementedError


# --- I/O ------------------------------------------------------------------


def collect_targets(root: Path, folders: list[str] | None,
                    config: dict | None = None) -> list[Path]:
    """Return the files this run would act on. Never mutates.

    Skip-dirs come from vault_config, which is what keeps `.pytest_cache/README.md`
    and stale `.claude/worktrees/` copies out of a vault scan. process_frontmatter
    walked into them for two months and stamped seven cache files.
    """
    config = config or CONFIG
    scope = [root / f for f in folders] if folders else [root]
    targets = []
    for base in scope:
        for path in base.rglob("*.md"):
            if not path.is_file():
                continue
            parts = path.relative_to(base).parts[:-1]
            if any(vault_config.is_skipped_dir(part, config) for part in parts):
                continue
            targets.append(path)
    return sorted(targets)


def run(root: Path, folders: list[str] | None, apply: bool) -> int:
    """Do the work. Returns the number of files changed (or that would change)."""
    changed = 0
    for path in collect_targets(root, folders):
        # ... compute the change ...
        would_change = False
        if not would_change:
            continue
        changed += 1
        # Print WHAT changes, not just how many -- AGENTS treats dry-run output
        # as the acceptance test.
        print(f"{'CHANGED' if apply else 'WOULD CHANGE'}: {path.relative_to(root)}")
        if apply:
            pass  # write here
    return changed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--vault", type=Path, default=VAULT_ROOT,
                        help="vault root (default: found by walking up for vault.json)")
    parser.add_argument("--folders", nargs="*", default=None,
                        help="restrict to these top-level folder prefixes")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", default=True,
                      help="preview only (default)")
    mode.add_argument("--apply", action="store_true",
                      help="actually write changes")
    args = parser.parse_args()

    count = run(args.vault, args.folders, apply=args.apply)
    verb = "changed" if args.apply else "would change"
    print(f"\n{count} file(s) {verb}.")
    if not args.apply:
        print("Dry run - nothing written. Re-run with --apply to commit.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
