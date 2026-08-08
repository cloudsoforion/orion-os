#!/usr/bin/env python3
"""
scan_broken_wikilinks.py — find wikilinks that don't resolve, and the ones that
resolve by luck.

Two problems, one pass:

  1. **Broken path links.** `[[02-Projects/foo/bar]]` where no such file exists.
     Optionally repaired by rewriting a stale top-level prefix to its current one,
     but *only* when the remapped target actually exists — so a repair never
     invents a new wrong link.
  2. **Bare-basename links.** `[[bar]]`. These are the ones that look fine and
     aren't: [[AGENTS]] § Markdown & Naming Conventions requires vault-absolute
     links because a basename with several candidates resolves unpredictably —
     Obsidian silently picks one — and a basename with none renders as
     unclickable text that is invisible in reading view.

**Dry-run is the default.** Nothing is written without `--apply` (repairs) or
`--promote-basenames` (rewrites unambiguous basenames to full paths).

Usage:
  # Report on the whole vault, write nothing
  python3 scan_broken_wikilinks.py

  # Same, plus a markdown report in the ops journal
  python3 scan_broken_wikilinks.py --report

  # Repair broken path links whose remapped target exists
  python3 scan_broken_wikilinks.py --remap 09-archive/=04-Archive/ --apply

  # Rewrite [[bar]] -> [[full/path/to/bar]] where exactly one candidate exists
  python3 scan_broken_wikilinks.py --promote-basenames

  # Just the counts, for a pre-commit or CI gate
  python3 scan_broken_wikilinks.py --quiet

Statuses in the report:

  fixable              broken path link; the remapped target exists  -> --apply fixes it
  remap-no-target      matched a remap prefix, but the target still doesn't exist
  no-remap             broken path link, no remap prefix matched     -> needs a human
  basename-ambiguous   bare basename with >1 candidate; Obsidian picks one, silently
  basename-unresolved  bare basename with no candidate at all        -> invisible break
  basename-single      bare basename with exactly 1 candidate        -> --promote-basenames

Deliberate exclusions, and why the count is much lower than a naive grep's:

  - Directories from `skip_dirs` in vault.json — `.trash/`, `.claude/worktrees/`
    (a stale pre-reorg vault copy), `.git/`. Scanning them produced most of the
    906 "broken" links a previous pass reported; none of them are real.
  - Fenced code blocks and inline code spans. `[[ -d "$dir" ]]` is bash, and the
    reorg write-ups quote illustrative paths like `[[04-Projects/foo/bar]]` on
    purpose. Both were false positives before.
  - Dotfiles. The basename index covers every other file type, not just `.md`,
    because Obsidian links attachments the same way — a markdown-only index
    reports `[[some-manifest.yaml]]` as an invisible break when it resolves fine.

What is *not* excluded, and is a real finding: a bare basename matching nothing in
the vault. Some of those point at Claude memory files under
`~/.claude/projects/.../memory/`, which live outside the vault and can never
resolve — [[AGENTS]] § Markdown & Naming Conventions calls that out specifically.
Reference them as plain text, not as links.

There is no remap baked in. A default remap is a hardcoded taxonomy, and the
retirement of `archive-folders` turned on exactly that mistake — see
the `archive-folders` post-mortem. Put durable remaps in
`vault.json` under `link_remaps`; pass one-off ones with `--remap`.
"""

import argparse
import fnmatch
import os
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import vault_config

LINK_RE = re.compile(r"(!?)\[\[([^\[\]]+?)\]\]")
FENCE_RE = re.compile(r"^\s*(```|~~~)")

PATH_STATUSES = ("fixable", "remap-no-target", "no-remap")
BASENAME_STATUSES = ("basename-ambiguous", "basename-unresolved", "basename-single")


# --------------------------------------------------------------------------
# pure functions
# --------------------------------------------------------------------------

def split_link(inner: str) -> tuple[str, str, str, bool]:
    """Split `path#heading|alias` into (path, heading, alias, escaped_pipe).

    An escaped pipe (`\\|`) is how an alias survives inside a markdown table
    cell; it has to be preserved on the way back out or the table breaks.
    """
    escaped = False
    if "\\|" in inner:
        escaped = True
        target, _, alias = inner.partition("\\|")
    else:
        target, _, alias = inner.partition("|")
    target, _, heading = target.partition("#")
    return target.strip(), heading, alias, escaped


def rebuild(target: str, heading: str, alias: str, escaped: bool, embed: str) -> str:
    inner = target
    if heading:
        inner += "#" + heading
    if alias:
        inner += ("\\|" if escaped else "|") + alias
    return f"{embed}[[{inner}]]"


def mask_code(line: str) -> list[bool]:
    """Per-character mask of inline-code spans, so `[[link]]` inside backticks
    isn't treated as a link. An unbalanced backtick masks to end of line."""
    mask = [False] * len(line)
    in_code = False
    for i, ch in enumerate(line):
        if ch == "`":
            in_code = not in_code
            mask[i] = True
            continue
        mask[i] = in_code
    return mask


def parse_remap(specs: list[str]) -> dict[str, str]:
    """`["04-Projects/=02-Projects/"]` -> `{"04-Projects/": "02-Projects/"}`."""
    remap = {}
    for spec in specs:
        if "=" not in spec:
            raise ValueError(f"--remap expects OLD/=NEW/, got: {spec}")
        old, new = spec.split("=", 1)
        if not old or not new:
            raise ValueError(f"--remap expects OLD/=NEW/, got: {spec}")
        remap[old] = new
    return remap


def resolves(vault: Path, target: str) -> bool:
    """True if `target`, or `target.md`, is a file under the vault root."""
    candidates = [target]
    if not os.path.splitext(target)[1]:
        candidates.append(target + ".md")
    return any((vault / c).is_file() for c in candidates)


def classify_path_link(vault: Path, target: str, remap: dict) -> tuple[str, str | None]:
    """(status, proposed) for a link that names a directory."""
    if resolves(vault, target):
        return "ok", None
    for old, new in remap.items():
        if target.startswith(old):
            candidate = new + target[len(old):]
            if resolves(vault, candidate):
                return "fixable", candidate
            return "remap-no-target", candidate
    return "no-remap", None


def classify_basename_link(target: str, by_name: dict[str, list[str]]) -> tuple[str, str | None]:
    """(status, proposed) for a bare basename — the case that resolves by luck.

    A root-level file is the exception: for `[[AGENTS]]` the bare name already *is*
    the vault-absolute path, so it satisfies the standard rather than violating it.
    [[AGENTS]] § Markdown & Naming Conventions calls this out — "root-level file,
    path IS the name". Without this branch the tool nags about correct links and
    every reference to OrionOs, AGENTS, or CLAUDE inflates the count.
    """
    candidates = by_name.get(target, [])
    if not candidates:
        return "basename-unresolved", None
    if len(candidates) == 1:
        proposed = os.path.splitext(candidates[0])[0]
        if proposed == target:
            return "ok", None
        return "basename-single", proposed
    return "basename-ambiguous", None


def is_excluded(rel_path: str, patterns: list[str]) -> bool:
    """True if `rel_path` matches any glob in `patterns`.

    Exists because a link report is only useful if it is actionable, and on this
    vault **57% of the broken path links live in two auto-generated files** — the
    `work-chronology` notes, which cite historical paths on purpose. Counting them
    every run buries the ~150 findings a human could actually fix. Patterns live in
    `vault.json` under `exclude_paths`; `--exclude` adds more.
    """
    return any(fnmatch.fnmatch(rel_path, pattern) for pattern in patterns)


def top_prefix(target: str) -> str:
    """`02-Projects/foo/bar` -> `02-Projects/`; a bare name -> `(basename)`."""
    return target.split("/")[0] + "/" if "/" in target else "(basename)"


# --------------------------------------------------------------------------
# I/O
# --------------------------------------------------------------------------

def iter_files(vault: Path, config: dict, only_md: bool = False):
    """Files under the vault, skipping the directories vault.json names and dotfiles."""
    for dirpath, dirnames, filenames in os.walk(vault):
        vault_config.prune_dirs(dirnames, config)
        for filename in sorted(filenames):
            if filename.startswith("."):
                continue
            if only_md and not filename.endswith(".md"):
                continue
            yield Path(dirpath) / filename


def iter_md_files(vault: Path, config: dict):
    """Every `.md` under the vault — the files whose links get scanned."""
    return iter_files(vault, config, only_md=True)


def index_basenames(vault: Path, config: dict) -> dict[str, list[str]]:
    """basename and stem -> [vault-relative paths]. Feeds the basename analysis.

    Indexes **every** file, not just `.md`. Obsidian links attachments the same
    way notes are linked — `[[GlobalAddress-accounts.yaml]]`, `[[Postmortem.pdf]]` —
    so a markdown-only index reports every one of those as an invisible break.
    That mistake accounted for the bulk of a 1,092-link "unresolved" count.
    """
    by_name: dict[str, list[str]] = defaultdict(list)
    for path in iter_files(vault, config):
        rel = path.relative_to(vault).as_posix()
        name = path.name
        by_name[name].append(rel)
        stem = path.stem
        if stem != name:
            by_name[stem].append(rel)
    return by_name


def scan(vault: Path, config: dict, remap: dict, by_name: dict,
         check_basenames: bool = True, apply_repairs: bool = False,
         promote_basenames: bool = False,
         exclude: list[str] | None = None) -> tuple[list[dict], int]:
    """Walk the vault and classify every wikilink. Returns (findings, files_written)."""
    findings: list[dict] = []
    files_written = 0
    exclude = exclude or []

    for path in iter_md_files(vault, config):
        if is_excluded(path.relative_to(vault).as_posix(), exclude):
            continue
        try:
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines(keepends=True)
        except OSError:
            continue

        rel_file = path.relative_to(vault).as_posix()
        changed = False
        in_fence = False

        for index, line in enumerate(lines):
            if FENCE_RE.match(line):
                in_fence = not in_fence
                continue
            if in_fence or "[[" not in line:
                continue

            mask = mask_code(line)

            def replace(match, _line_no=index + 1):
                nonlocal changed
                if any(mask[match.start():match.end()]):
                    return match.group(0)      # inside inline code

                embed, inner = match.group(1), match.group(2)
                target, heading, alias, escaped = split_link(inner)
                if not target:
                    return match.group(0)

                if "/" in target:
                    status, proposed = classify_path_link(vault, target, remap)
                    if status == "ok":
                        return match.group(0)
                    rewrite = apply_repairs and status == "fixable"
                else:
                    if not check_basenames:
                        return match.group(0)
                    status, proposed = classify_basename_link(target, by_name)
                    if status == "ok":
                        return match.group(0)
                    rewrite = promote_basenames and status == "basename-single"

                findings.append({
                    "file": rel_file, "line": _line_no, "target": target,
                    "proposed": proposed, "status": status,
                })

                if rewrite and proposed:
                    changed = True
                    # A promoted basename keeps its old name as the alias, so prose
                    # reads the same after the path is spelled out.
                    if status == "basename-single" and not alias:
                        alias = target
                    return rebuild(proposed, heading, alias, escaped, embed)
                return match.group(0)

            lines[index] = LINK_RE.sub(replace, line)

        if changed:
            path.write_text("".join(lines), encoding="utf-8")
            files_written += 1

    return findings, files_written


def summarize(findings: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for finding in findings:
        counts[finding["status"]] += 1
    return dict(counts)


def format_report(vault: Path, findings: list[dict], counts: dict, remap: dict,
                  applied: int, config: dict, exclude: list[str] | None = None) -> str:
    exclude = exclude or []
    today = datetime.now().strftime("%Y%m%d")
    lines = [
        "---",
        f"created: \"{today}\"",
        f"updated: \"{today}\"",
        "tags:",
        f"  - {vault_config.tag(config, 'created', today)}",
        f"  - {vault_config.tag(config, 'updated', today)}",
        f"  - {vault_config.tag(config, 'type', 'report')}",
        f"  - {vault_config.tag(config, 'domain', config['default_domain'])}",
        f"  - {vault_config.tag(config, 'status', 'active')}",
        "status: active",
        "author: scan-broken-wikilinks",
        "---",
        "",
        f"# Broken wikilink report — {datetime.now():%Y-%m-%d %H:%M}",
        "",
        f"- Vault: `{vault}`",
        f"- Mode: {'APPLIED — files were rewritten' if applied else 'dry run — nothing written'}",
    ]
    if applied:
        lines.append(f"- Files rewritten: **{applied}**")
    lines += [
        f"- Remaps: {', '.join(f'`{o}`→`{n}`' for o, n in remap.items()) or '_none_'}",
        f"- Skipped directories: {', '.join(f'`{d}`' for d in config['skip_dirs'])}"
        + (", plus anything hidden" if config.get("skip_hidden_dirs", True) else ""),
        f"- Excluded paths: {', '.join(f'`{p}`' for p in exclude) or '_none_'}",
        "",
        "Fenced code blocks and inline code spans are not scanned — `[[ -d \"$dir\" ]]` is bash,"
        " and reorg write-ups quote illustrative paths on purpose.",
        "",
        "## Summary",
        "",
        "| Status | Count | Meaning |",
        "|---|---|---|",
    ]
    meanings = {
        "fixable": "broken path link; the remapped target exists — `--apply` fixes it",
        "remap-no-target": "matched a remap prefix, but the target still doesn't exist",
        "no-remap": "broken path link, no remap matched — needs a human",
        "basename-ambiguous": "bare basename with >1 candidate; Obsidian picks one, silently",
        "basename-unresolved": "bare basename with no candidate — an invisible break",
        "basename-single": "bare basename with exactly 1 candidate — `--promote-basenames` fixes it",
    }
    for status in (*PATH_STATUSES, *BASENAME_STATUSES):
        lines.append(f"| `{status}` | **{counts.get(status, 0)}** | {meanings[status]} |")

    lines += ["", f"**Total findings: {len(findings)}**", "", "## By link prefix", ""]
    buckets: dict[str, int] = defaultdict(int)
    for finding in findings:
        buckets[top_prefix(finding["target"])] += 1
    lines += ["| Prefix | Count |", "|---|---|"]
    for prefix, count in sorted(buckets.items(), key=lambda kv: -kv[1]):
        lines.append(f"| `[[{prefix}…]]` | {count} |")

    for status in (*PATH_STATUSES, *BASENAME_STATUSES):
        rows = [f for f in findings if f["status"] == status]
        lines += ["", f"## {status} ({len(rows)})", ""]
        if not rows:
            lines.append("_None._")
            continue
        lines += ["| File | Line | Target | Proposed |", "|---|---|---|---|"]
        for row in rows:
            lines.append(f"| `{row['file']}` | {row['line']} | `{row['target']}` | "
                         f"`{row['proposed'] or ''}` |")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Find wikilinks that don't resolve, and bare basenames that resolve by luck. "
                    "Previews by default.")
    parser.add_argument("--vault", type=Path, default=None,
                        help="Vault root (default: found by walking up for .obsidian/)")
    parser.add_argument("--remap", action="append", default=[], metavar="OLD/=NEW/",
                        help="Prefix remap, repeatable. Adds to `link_remaps` in vault.json.")
    parser.add_argument("--apply", action="store_true",
                        help="Rewrite broken path links whose remapped target exists.")
    parser.add_argument("--promote-basenames", action="store_true",
                        help="Rewrite [[name]] to [[full/path|name]] where exactly one file matches.")
    parser.add_argument("--no-basenames", action="store_true",
                        help="Only check path-style links; skip the basename analysis.")
    parser.add_argument("--exclude", action="append", default=[], metavar="GLOB",
                        help="Skip files matching this vault-relative glob, repeatable. "
                             "Adds to `exclude_paths` in vault.json. Use for generated notes "
                             "that cite historical paths on purpose.")
    parser.add_argument("--report", nargs="?", const="auto", metavar="PATH",
                        help="Write a markdown report. Bare --report puts it in the log dir.")
    parser.add_argument("--quiet", action="store_true", help="Print counts only.")
    args = parser.parse_args()

    vault = (args.vault.resolve() if args.vault
             else vault_config.find_vault_root(Path.cwd()))
    if vault is None:
        print("error: could not locate the vault root (.obsidian); pass --vault", file=sys.stderr)
        return 1

    config = vault_config.load_config(vault)
    try:
        remap = {**config.get("link_remaps", {}), **parse_remap(args.remap)}
    except ValueError as exc:
        parser.error(str(exc))

    writing = args.apply or args.promote_basenames
    check_basenames = not args.no_basenames
    exclude = [*config.get("exclude_paths", []), *args.exclude]

    if not args.quiet:
        print(f"Vault: {vault}")
        print(f"Mode:  {'APPLY — files will be rewritten' if writing else 'DRY RUN — nothing will be written'}")
        if exclude:
            print(f"Excl:  {', '.join(exclude)}")

    by_name = index_basenames(vault, config) if check_basenames else {}

    findings, written = scan(vault, config, remap, by_name,
                             check_basenames=check_basenames,
                             apply_repairs=args.apply,
                             promote_basenames=args.promote_basenames,
                             exclude=exclude)

    if writing:
        # Re-scan the post-write state so the summary reports what REMAINS,
        # never the work that was just done.
        by_name = index_basenames(vault, config) if check_basenames else {}
        findings, _ = scan(vault, config, remap, by_name,
                           check_basenames=check_basenames, exclude=exclude)

    counts = summarize(findings)

    if writing:
        print(f"Rewrote {written} file(s).")
    for status in (*PATH_STATUSES, *BASENAME_STATUSES):
        if status in ("fixable", "basename-single") and counts.get(status):
            flag = "--apply" if status == "fixable" else "--promote-basenames"
            suffix = f"  (re-run with {flag} to fix)" if not writing else ""
        else:
            suffix = ""
        print(f"  {counts.get(status, 0):5d}  {status}{suffix}")
    print(f"  {len(findings):5d}  TOTAL")

    if args.report:
        if args.report == "auto":
            stamp = datetime.now().strftime("%Y%m%d%H%M")
            out_path = vault / config["log_dir"] / f"{stamp}-broken-wikilinks-report.md"
        else:
            out_path = Path(args.report)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            format_report(vault, findings, counts, remap, written, config, exclude),
            encoding="utf-8")
        print(f"\nReport: {out_path}")

    if not writing and (counts.get("fixable") or counts.get("basename-single")):
        print("\nNothing was written.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
