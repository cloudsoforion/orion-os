#!/usr/bin/env python3
"""
register.py — wire second-brain into Claude Code without hand-typing paths.

Writes the `UserPromptSubmit` hook into `<vault>/.claude/settings.json` and the
`vault-search` MCP server into `<vault>/.mcp.json`, with this checkout's absolute
paths resolved. These two files are the only place in the vault where an absolute
path is genuinely required: the client launches the process, so neither the vault
root nor the working directory is guaranteed.

**Dry-run is the default.** These are live config files that may already carry
hooks and servers you care about, so nothing is written without `--apply`.

Usage:
  python3 register.py                 # preview the exact diff
  python3 register.py --apply         # write both files
  python3 register.py --apply --mcp-only
  python3 register.py --apply --name vault-search-personal   # a second vault

Merge policy — additive, never destructive:
  - Other `UserPromptSubmit` hook entries are kept; only an entry whose command
    already points at *this* hook.py is replaced.
  - Other hook events and every other settings key are left untouched.
  - Other MCP servers are kept; only the same server name is replaced.
  - Anything that would change an existing value is printed as `~` in the preview
    so you can see it before it happens.
"""

import argparse
import json
import sys
from pathlib import Path

HOOK_EVENT = "UserPromptSubmit"
HOOK_TIMEOUT = 15
HOOK_STATUS = "Searching vault..."
DEFAULT_SERVER_NAME = "vault-search"

TOOL_DIR = Path(__file__).resolve().parent


def find_vault_root(start: Path) -> Path | None:
    """Nearest ancestor containing `.obsidian/`. Duplicated deliberately: this
    script must work when run from a bare checkout before anything else is set up."""
    start = Path(start).resolve()
    for candidate in [start, *start.parents]:
        if (candidate / ".obsidian").is_dir():
            return candidate
    return None


def load_json(path: Path) -> dict:
    """Existing config, or {} if absent. A malformed file raises — overwriting a
    file we couldn't parse is how you lose someone's hook configuration."""
    if not path.is_file():
        return {}
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return {}
    return json.loads(text)


def hook_command(hook_path: Path, python: str) -> str:
    return f"{python} {hook_path}"


def merge_hook(settings: dict, hook_path: Path, python: str) -> tuple[dict, str]:
    """Add or refresh our UserPromptSubmit entry. Returns (settings, action)."""
    settings = json.loads(json.dumps(settings))  # copy; never mutate the caller's dict
    entry = {
        "type": "command",
        "command": hook_command(hook_path, python),
        "timeout": HOOK_TIMEOUT,
        "statusMessage": HOOK_STATUS,
    }

    hooks = settings.setdefault("hooks", {})
    groups = hooks.setdefault(HOOK_EVENT, [])

    # Ours is any entry whose command mentions this hook.py, however it was spelled.
    marker = str(hook_path)
    for group in groups:
        inner = group.get("hooks", [])
        for i, existing in enumerate(inner):
            command = existing.get("command", "")
            if marker in command or command.endswith("second-brain/hook.py"):
                if existing == entry:
                    return settings, "unchanged"
                inner[i] = entry
                return settings, "replaced"

    groups.append({"hooks": [entry]})
    return settings, "added"


def merge_server(mcp: dict, server_path: Path, python: str, name: str,
                 db: Path | None) -> tuple[dict, str]:
    """Add or refresh our MCP server entry. Returns (mcp, action)."""
    mcp = json.loads(json.dumps(mcp))
    args = [str(server_path)]
    if db:
        args += ["--db", str(db)]
    if name != DEFAULT_SERVER_NAME:
        args += ["--name", name]
    entry = {"command": python, "args": args}

    servers = mcp.setdefault("mcpServers", {})
    if servers.get(name) == entry:
        return mcp, "unchanged"
    action = "replaced" if name in servers else "added"
    servers[name] = entry
    return mcp, action


def preview(path: Path, before: dict, after: dict) -> None:
    """Print the file and its new content, flagging whether it's new or changed."""
    state = "new file" if not path.is_file() else ("unchanged" if before == after else "changed")
    print(f"\n{'~' if state == 'changed' else '+' if state == 'new file' else '='} {path}  ({state})")
    if state == "unchanged":
        return
    for line in json.dumps(after, indent=2).splitlines():
        print(f"    {line}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Register second-brain's hook and MCP server with resolved paths. "
                    "Previews by default; pass --apply to write.")
    parser.add_argument("--vault", type=Path, default=None,
                        help="Vault root (default: found by walking up for .obsidian/)")
    parser.add_argument("--python", default="python3",
                        help="Interpreter to invoke in the generated commands (default: python3)")
    parser.add_argument("--name", default=DEFAULT_SERVER_NAME,
                        help=f"MCP server name (default: {DEFAULT_SERVER_NAME}). "
                             "Give a second vault its own.")
    parser.add_argument("--db", type=Path, default=None,
                        help="Index path to pass as --db (default: leave it to the tool)")
    parser.add_argument("--hook-only", action="store_true", help="Only touch .claude/settings.json")
    parser.add_argument("--mcp-only", action="store_true", help="Only touch .mcp.json")
    parser.add_argument("--apply", action="store_true", help="Write the files. Without this, nothing is written.")
    args = parser.parse_args()

    if args.hook_only and args.mcp_only:
        print("error: --hook-only and --mcp-only are mutually exclusive", file=sys.stderr)
        return 2

    vault = args.vault.resolve() if args.vault else find_vault_root(TOOL_DIR)
    if vault is None:
        print("error: could not locate the vault root (.obsidian); pass --vault", file=sys.stderr)
        return 1

    hook_path = TOOL_DIR / "hook.py"
    server_path = TOOL_DIR / "mcp_server.py"
    for required in (hook_path, server_path):
        if not required.is_file():
            print(f"error: missing {required}", file=sys.stderr)
            return 1

    print(f"Vault:  {vault}")
    print(f"Mode:   {'APPLY — files will be written' if args.apply else 'DRY RUN — nothing will be written'}")

    writes: list[tuple[Path, dict]] = []
    actions: list[str] = []

    if not args.mcp_only:
        path = vault / ".claude" / "settings.json"
        before = load_json(path)
        after, action = merge_hook(before, hook_path, args.python)
        actions.append(f"hook: {action}")
        preview(path, before, after)
        if before != after:
            writes.append((path, after))

    if not args.hook_only:
        path = vault / ".mcp.json"
        before = load_json(path)
        after, action = merge_server(before, server_path, args.python, args.name, args.db)
        actions.append(f"mcp server '{args.name}': {action}")
        preview(path, before, after)
        if before != after:
            writes.append((path, after))

    print(f"\n{' · '.join(actions)}")

    if not writes:
        print("Already registered; nothing to do.")
        return 0

    if not args.apply:
        print(f"\nNothing was written. Re-run with --apply to write {len(writes)} file(s).")
        return 0

    for path, content in writes:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(content, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {path}")
    print("\nRestart Claude Code for the hook and MCP server to load.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
