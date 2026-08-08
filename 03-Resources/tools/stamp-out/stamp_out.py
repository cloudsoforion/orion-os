#!/usr/bin/env python3
"""Stamp out a timestamped copy of a vault folder with wikilinks repointed at the copy.

A plain `cp -R` produces a copy whose wikilinks still resolve to the *original*
folder: vault-absolute links keep their old path, and bare-basename links become
ambiguous because the basenames now exist twice. Either way you end up reading
one file and annotating another.

This tool copies the folder, then rewrites wikilinks inside the copy's markdown
files so every link that resolves to a file *inside* the copied set points at the
copy. Links to notes elsewhere in the vault are left alone.

Deliberate constraints:
  * Nothing is renamed. Filenames stay byte-identical, so `kubectl apply -f`
    paths, NN- apply ordering, and script-to-script `source` calls keep working.
  * Only `.md` files are edited. yaml/sh/txt are copied verbatim -- `[[ ... ]]`
    is also bash test syntax, and rewriting it would corrupt shell scripts.
  * Fenced code blocks and inline code spans are skipped.
  * Unresolvable links are reported, never guessed at.

Usage:
    python stamp_out.py <source-folder> [--dry-run]
    python stamp_out.py <source-folder> --timestamp 202607290947
    python stamp_out.py --rewrite-existing <already-copied-folder> --source <original>
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import vault_config

WIKILINK_RE = re.compile(r"(!?)\[\[([^\[\]]+?)\]\]")
FENCE_RE = re.compile(r"^\s*(```|~~~)")
TIMESTAMP_FMT = "%Y%m%d%H%M"

# Vault-root discovery lives in vault_config; re-exported so the public surface
# of this module is unchanged for callers and tests.
find_vault_root = vault_config.find_vault_root


def index_folder(root: Path, config: dict | None = None) -> tuple[set[str], dict[str, list[str]]]:
    """Index files under `root`.

    Returns (set of posix paths relative to root, basename/stem -> [rel paths]).
    """
    config = config or vault_config.DEFAULTS
    rel_paths: set[str] = set()
    by_name: dict[str, list[str]] = defaultdict(list)
    for dirpath, dirnames, filenames in os.walk(root):
        vault_config.prune_dirs(dirnames, config)
        for fname in filenames:
            if fname.startswith("."):
                continue
            rel = (Path(dirpath) / fname).relative_to(root).as_posix()
            rel_paths.add(rel)
            by_name[fname].append(rel)
            stem = Path(fname).stem
            if stem != fname:
                by_name[stem].append(rel)
    return rel_paths, by_name


def index_vault(vault: Path, exclude: Path, config: dict | None = None) -> tuple[set[str], set[str]]:
    """Index the whole vault, ignoring `exclude`.

    Returns (filenames and stems, posix paths relative to the vault root).
    """
    config = config or vault_config.DEFAULTS
    names: set[str] = set()
    rel_paths: set[str] = set()
    exclude_str = str(exclude)
    for dirpath, dirnames, filenames in os.walk(vault):
        vault_config.prune_dirs(dirnames, config)
        if dirpath == exclude_str or dirpath.startswith(exclude_str + os.sep):
            continue
        for fname in filenames:
            if fname.startswith("."):
                continue
            names.add(fname)
            names.add(Path(fname).stem)
            rel_paths.add((Path(dirpath) / fname).relative_to(vault).as_posix())
    return names, rel_paths


# --------------------------------------------------------------------------
# link parsing
# --------------------------------------------------------------------------

def split_link_body(body: str) -> tuple[str, str | None, str | None, bool]:
    """Split a wikilink body into (path, anchor, alias, alias_pipe_was_escaped)."""
    escaped_pipe = False
    alias = None
    target = body

    # Find the first pipe that separates target from alias, honouring `\|`.
    idx = 0
    while idx < len(body):
        ch = body[idx]
        if ch == "\\" and idx + 1 < len(body) and body[idx + 1] == "|":
            target, alias = body[:idx], body[idx + 2:]
            escaped_pipe = True
            break
        if ch == "|":
            target, alias = body[:idx], body[idx + 1:]
            break
        idx += 1

    anchor = None
    if "#" in target:
        target, anchor = target.split("#", 1)

    return target.strip(), anchor, alias, escaped_pipe


def mask_inline_code(line: str) -> list[bool]:
    """Return a per-character mask; True where the char sits inside a code span."""
    mask = [False] * len(line)
    in_code = False
    for i, ch in enumerate(line):
        if ch == "`":
            in_code = not in_code
            mask[i] = True
            continue
        mask[i] = in_code
    return mask


# --------------------------------------------------------------------------
# resolution
# --------------------------------------------------------------------------

class Resolver:
    def __init__(self, source_rel: str, dest_rel: str, copied: set[str],
                 by_name: dict[str, list[str]], vault_names: set[str],
                 vault_paths: set[str]):
        self.source_rel = source_rel.rstrip("/")
        self.dest_rel = dest_rel.rstrip("/")
        self.copied = copied
        self.by_name = by_name
        self.vault_names = vault_names
        self.vault_paths = vault_paths

    def _exact(self, rel: str) -> str | None:
        rel = rel.strip("/")
        if not rel:
            return None
        if rel in self.copied:
            return rel
        if f"{rel}.md" in self.copied:
            return f"{rel}.md"
        return None

    def resolve(self, path_part: str, containing_dir: str) -> tuple[str, str | None]:
        """Classify a link target.

        Returns (kind, rel-path-in-copy). kind is one of:
          internal        -- resolves inside the copied set, needs rewriting
          already-stamped -- already points at the copy, leave as-is
          external        -- a name that exists elsewhere in the vault
          broken          -- resolves nowhere
        """
        p = path_part.strip().lstrip("./")
        if not p:
            return "broken", None

        # Already pointing into the stamped copy -> idempotent no-op.
        if p == self.dest_rel or p.startswith(self.dest_rel + "/"):
            return "already-stamped", None

        # Vault-absolute path into the original folder.
        if p == self.source_rel or p.startswith(self.source_rel + "/"):
            rel = self._exact(p[len(self.source_rel):])
            return ("internal", rel) if rel else ("broken", None)

        # Relative to the file doing the linking (handles ../ too).
        joined = os.path.normpath(os.path.join(containing_dir, p)) if containing_dir else os.path.normpath(p)
        if not joined.startswith(".."):
            rel = self._exact(joined)
            if rel:
                return "internal", rel

        # Path relative to the copy root.
        rel = self._exact(p)
        if rel:
            return "internal", rel

        # Bare-basename fallback -- ONLY when the link names no directory. A link
        # that does name a directory has to match it; retargeting on basename
        # alone would silently change which file the link means.
        if "/" not in p:
            hits = self.by_name.get(p) or self.by_name.get(Path(p).stem) or []
            if len(hits) == 1:
                return "internal", hits[0]
            if len(hits) > 1:
                return "broken", None  # ambiguous inside the copy; refuse to guess

        # Not in the copy -- does it resolve anywhere else in the vault?
        if p in self.vault_paths or f"{p}.md" in self.vault_paths:
            return "external", None
        if "/" not in p and (p in self.vault_names or Path(p).stem in self.vault_names):
            return "external", None

        # Resolve the link relative to the linking file's position in the vault,
        # so `../sibling-folder/file.yaml` is checked against the real tree.
        vault_joined = os.path.normpath(os.path.join(self.dest_rel, containing_dir, p))
        if vault_joined in self.vault_paths or f"{vault_joined}.md" in self.vault_paths:
            return "external", None

        return "broken", None


def build_path_patterns(vault: Path, source: Path, dest: Path) -> list[tuple[re.Pattern, str]]:
    """Patterns swapping filesystem references to `source` for `dest`.

    Covers the absolute, `~/`, and vault-relative spellings. Each pattern ends in
    a `(?![\\w-])` guard so a sibling folder that merely starts with the same name
    -- `runbook-eu-cluster-failover-CLAIM` vs `runbook-eu-cluster-failover` -- is
    never caught by a substring match.
    """
    home = str(Path.home())
    pairs = [(str(source), str(dest)),
             (source.relative_to(vault).as_posix(), dest.relative_to(vault).as_posix())]
    if str(source).startswith(home):
        pairs.append((f"~{str(source)[len(home):]}", f"~{str(dest)[len(home):]}"))
    pairs.sort(key=lambda pair: len(pair[0]), reverse=True)
    return [(re.compile(re.escape(old) + r"(?![\w-])"), new) for old, new in pairs]


def rewrite_paths(path: Path, patterns: list[tuple[re.Pattern, str]]) -> tuple[str, int] | None:
    """Swap source-folder path strings for dest-folder ones. None if unchanged/binary."""
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return None
    total = 0
    for pattern, replacement in patterns:
        text, n = pattern.subn(replacement, text)
        total += n
    return (text, total) if total else None


def build_target(dest_rel: str, rel: str) -> str:
    """Vault-absolute link target for a file in the copy (.md loses its suffix)."""
    if rel.endswith(".md"):
        rel = rel[: -len(".md")]
    return f"{dest_rel}/{rel}"


# --------------------------------------------------------------------------
# rewriting
# --------------------------------------------------------------------------

def rewrite_file(md_path: Path, dest_root: Path, resolver: Resolver,
                 dest_rel: str, records: list[dict]) -> str | None:
    """Rewrite links in one markdown file. Returns new text if changed."""
    original = md_path.read_text(encoding="utf-8")
    containing_dir = md_path.parent.relative_to(dest_root).as_posix()
    if containing_dir == ".":
        containing_dir = ""
    file_label = md_path.relative_to(dest_root).as_posix()

    out_lines: list[str] = []
    in_fence = False
    changed = False

    for lineno, line in enumerate(original.splitlines(keepends=True), start=1):
        if FENCE_RE.match(line):
            in_fence = not in_fence
            out_lines.append(line)
            continue
        if in_fence or "[[" not in line:
            out_lines.append(line)
            continue

        code_mask = mask_inline_code(line)
        table_row = line.lstrip().startswith("|")
        result: list[str] = []
        cursor = 0

        for match in WIKILINK_RE.finditer(line):
            if code_mask[match.start()]:
                continue

            body = match.group(2)
            path_part, anchor, alias, escaped = split_link_body(body)
            kind, rel = resolver.resolve(path_part, containing_dir)

            records.append({
                "file": file_label,
                "line": lineno,
                "kind": kind,
                "old": match.group(0),
                "new": "",
            })

            if kind != "internal" or rel is None:
                continue

            new_path = build_target(dest_rel, rel)
            if new_path == path_part:
                records[-1]["kind"] = "already-stamped"
                continue

            # Preserve display text: reuse the alias, else the old short target.
            display = alias if alias is not None else path_part
            sep = "\\|" if (escaped or (alias is None and table_row)) else "|"
            new_body = new_path + (f"#{anchor}" if anchor else "") + sep + display
            replacement = f"{match.group(1)}[[{new_body}]]"

            result.append(line[cursor:match.start()])
            result.append(replacement)
            cursor = match.end()
            changed = True
            records[-1]["new"] = replacement

        result.append(line[cursor:])
        out_lines.append("".join(result))

    return "".join(out_lines) if changed else None


# --------------------------------------------------------------------------
# report
# --------------------------------------------------------------------------

def write_report(path: Path, source: Path, dest: Path, records: list[dict],
                 ts: str, dry_run: bool, path_hits: list[tuple[str, int]] | None = None,
                 config: dict | None = None, author: str | None = None) -> None:
    config = config or vault_config.DEFAULTS
    today = datetime.now().strftime("%Y%m%d")
    buckets: dict[str, list[dict]] = defaultdict(list)
    for r in records:
        buckets[r["kind"]].append(r)

    # The report is generated by this script, so `author` names whoever runs it —
    # taken from vault.json. It used to be hardcoded to a specific Claude model
    # version, which credited the wrong party and went stale on every release.
    author = author or config.get("author") or "stamp-out"

    lines = [
        "---",
        "tags:",
        f"  - {vault_config.tag(config, 'created', today)}",
        f"  - {vault_config.tag(config, 'updated', today)}",
        f"  - {vault_config.tag(config, 'type', 'report')}",
        f"  - {vault_config.tag(config, 'domain', config['default_domain'])}",
        f"author: {author}",
        f"source-folder: {source.name}",
        f"stamped-folder: {dest.name}",
        f"stamp-timestamp: {ts}",
        "---",
        "",
        f"# Stamp-out report — {dest.name}",
        "",
        f"- **Source:** `{source}`",
        f"- **Copy:** `{dest}`",
        f"- **Mode:** {'DRY RUN (nothing written)' if dry_run else 'applied'}",
        f"- **Wikilinks seen:** {len(records)}",
        "",
        "Filenames were not changed. Only `.md` files were edited; yaml/sh/txt were",
        "copied verbatim so apply-paths and script `source` calls keep working.",
        "",
    ]

    rewritten = buckets.get("internal", [])
    lines += [f"## Repointed at the copy ({len(rewritten)})", ""]
    if rewritten:
        lines += ["| File | Line | Before | After |", "| --- | --- | --- | --- |"]
        for r in rewritten:
            old = r["old"].replace("|", "\\|")
            new = r["new"].replace("|", "\\|")
            lines.append(f"| `{r['file']}` | {r['line']} | `{old}` | `{new}` |")
    else:
        lines.append("_None._")
    lines.append("")

    external = buckets.get("external", [])
    grouped: dict[str, list[str]] = defaultdict(list)
    for r in external:
        grouped[r["old"]].append(f"`{r['file']}`:{r['line']}")
    lines += [
        f"## Left pointing outside the copy ({len(grouped)} unique, {len(external)} occurrences)",
        "",
        "These resolve to notes elsewhere in the vault and were intentionally not touched.",
        "",
    ]
    if grouped:
        lines += ["| Link | Seen in |", "| --- | --- |"]
        for link, sites in grouped.items():
            lines.append(f"| `{link.replace('|', chr(92) + '|')}` | {', '.join(sites)} |")
    else:
        lines.append("_None._")
    lines.append("")

    path_hits = path_hits or []
    lines += [
        f"## Filesystem path references repointed ({sum(n for _, n in path_hits)})",
        "",
        "Shell variables and apply-paths inside code fences — these point at a real",
        "directory, so a stale one would apply manifests from the *original* folder.",
        "",
    ]
    if path_hits:
        lines += ["| File | Refs |", "| --- | --- |"]
        lines += [f"| `{rel}` | {n} |" for rel, n in path_hits]
    else:
        lines.append("_None._")
    lines.append("")

    stamped = buckets.get("already-stamped", [])
    if stamped:
        lines += [f"## Already correct ({len(stamped)})", "",
                  "Already pointed at the copy — no change needed.", ""]

    broken = buckets.get("broken", [])
    lines += [
        f"## ⚠️ Unresolved — pre-existing in the source ({len(broken)})",
        "",
        "These resolve to nothing, in the copy or the wider vault. **Not** introduced by",
        "the stamp-out; they are broken in the original too. Left untouched deliberately —",
        "fixing them means guessing at intent.",
        "",
    ]
    if broken:
        lines += ["| Link | Seen in |", "| --- | --- |"]
        for r in broken:
            lines.append(f"| `{r['old'].replace('|', chr(92) + '|')}` | `{r['file']}`:{r['line']} |")
    else:
        lines.append("_None._")
    lines.append("")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Stamp out a timestamped copy of a vault folder, repointing its wikilinks.")
    ap.add_argument("folder", type=Path,
                    help="Folder to copy (or, with --rewrite-existing, the existing copy).")
    ap.add_argument("--source", type=Path,
                    help="With --rewrite-existing: the original folder the copy came from.")
    ap.add_argument("--rewrite-existing", action="store_true",
                    help="Skip the copy step and rewrite links in an already-copied folder.")
    # TIMESTAMP_FMT is doubled because argparse runs %-formatting over help text,
    # and a bare %Y raises "unsupported format character". This crashed --help.
    ap.add_argument("--timestamp",
                    help=f"Timestamp for the copy name (default: now, "
                         f"{TIMESTAMP_FMT.replace('%', '%%')}).")
    ap.add_argument("--dest-parent", type=Path, help="Where to place the copy (default: source's parent).")
    ap.add_argument("--vault", type=Path, help="Vault root (default: auto-detect via .obsidian).")
    ap.add_argument("--dry-run", action="store_true", help="Report what would change; write nothing.")
    ap.add_argument("--no-rewrite-paths", action="store_true",
                    help="Skip repointing filesystem path references (shell vars, apply paths).")
    ap.add_argument("--no-report", action="store_true", help="Skip writing the report note.")
    ap.add_argument("--author", help="author: value for the report note (default: author from vault.json).")
    args = ap.parse_args(argv)

    folder = args.folder.resolve()
    if not folder.is_dir():
        print(f"error: not a directory: {folder}", file=sys.stderr)
        return 1

    vault = (args.vault.resolve() if args.vault else find_vault_root(folder))
    if vault is None:
        print("error: could not locate vault root (.obsidian); pass --vault", file=sys.stderr)
        return 1

    config = vault_config.load_config(vault)
    ts = args.timestamp or datetime.now().strftime(TIMESTAMP_FMT)

    if args.rewrite_existing:
        if not args.source:
            print("error: --rewrite-existing requires --source", file=sys.stderr)
            return 1
        source, dest = args.source.resolve(), folder
        intended_dest = dest
        if not source.is_dir():
            print(f"error: --source is not a directory: {source}", file=sys.stderr)
            return 1
    else:
        source = folder
        parent = (args.dest_parent.resolve() if args.dest_parent else source.parent)
        dest = parent / f"{ts}-{source.name}"
        intended_dest = dest
        if dest.exists() and not args.dry_run:
            print(f"error: destination already exists: {dest}", file=sys.stderr)
            return 1
        if args.dry_run:
            if dest.exists():
                print(f"[dry-run] note: {dest} already exists; a real run would refuse")
            print(f"[dry-run] would copy {source} -> {dest}")
            dest = source  # analyse the source in place
        else:
            shutil.copytree(source, dest, symlinks=True)
            print(f"copied {source} -> {dest}")

    try:
        source_rel = source.relative_to(vault).as_posix()
        dest_rel = dest.relative_to(vault).as_posix()
    except ValueError:
        print("error: source and destination must both live inside the vault", file=sys.stderr)
        return 1

    if args.dry_run and not args.rewrite_existing:
        dest_rel = f"{source.parent.relative_to(vault).as_posix()}/{ts}-{source.name}"

    copied, by_name = index_folder(dest, config)
    vault_names, vault_paths = index_vault(vault, exclude=dest, config=config)
    resolver = Resolver(source_rel, dest_rel, copied, by_name, vault_names, vault_paths)

    records: list[dict] = []
    edited = 0
    for rel in sorted(copied):
        if not rel.endswith(".md"):
            continue
        md_path = dest / rel
        new_text = rewrite_file(md_path, dest, resolver, dest_rel, records)
        if new_text is None:
            continue
        edited += 1
        if args.dry_run:
            print(f"[dry-run] would rewrite links in {rel}")
        else:
            md_path.write_text(new_text, encoding="utf-8")
            print(f"rewrote links in {rel}")

    # Second pass: filesystem path references (shell vars, apply paths). These
    # live in code fences, which the wikilink pass deliberately skips, and they
    # matter most -- a stale `DR=` applies manifests from the original folder.
    path_hits: list[tuple[str, int]] = []
    if not args.no_rewrite_paths:
        patterns = build_path_patterns(vault, source, intended_dest)
        for rel in sorted(copied):
            if rel.endswith("-stamp-out-report.md"):
                continue
            result = rewrite_paths(dest / rel, patterns)
            if result is None:
                continue
            new_text, n = result
            path_hits.append((rel, n))
            if args.dry_run:
                print(f"[dry-run] would repoint {n} path ref(s) in {rel}")
            else:
                (dest / rel).write_text(new_text, encoding="utf-8")
                print(f"repointed {n} path ref(s) in {rel}")

    kinds = defaultdict(int)
    for r in records:
        kinds[r["kind"]] += 1
    print(f"\n{len(records)} wikilinks: "
          f"{kinds['internal']} repointed, {kinds['external']} external, "
          f"{kinds['already-stamped']} already correct, {kinds['broken']} unresolved")
    print(f"{edited} markdown file(s) {'would be ' if args.dry_run else ''}edited")

    if path_hits:
        print(f"{sum(n for _, n in path_hits)} filesystem path ref(s) repointed "
              f"across {len(path_hits)} file(s)")

    if not args.no_report:
        report_name = f"{ts}-stamp-out-report.md"
        report_path = (Path.cwd() / report_name) if args.dry_run else (dest / report_name)
        write_report(report_path, source, intended_dest, records, ts, args.dry_run, path_hits,
                     config=config, author=args.author)
        print(f"report: {report_path}")

    if kinds["broken"]:
        print(f"\n⚠️  {kinds['broken']} unresolved link(s) — see the report. "
              f"These are broken in the source too; nothing was guessed at.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
