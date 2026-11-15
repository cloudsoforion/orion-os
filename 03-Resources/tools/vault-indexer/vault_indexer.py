#!/usr/bin/env python3
"""
vault_indexer.py — incremental file tracker for Obsidian vault

Maintains a SQLite index of all markdown files: tracks inodes for move
detection, caches extracted sections so content reads only happen when
a file actually changes.

Commands:
  index    scan vault and update the index
  summary  write a work summary to the ops journal (Log/)

Usage:
  python vault_indexer.py index
  python vault_indexer.py index --reindex
  python vault_indexer.py index --folders 00-Inbox/work 02-Projects

  python vault_indexer.py summary
  python vault_indexer.py summary --date 2026-05-20
  python vault_indexer.py summary --from 2025-05-29 --to 2026-05-29
  python vault_indexer.py summary --from 2025-05-29 --to 2026-05-29 --folders 00-Inbox/work 02-Projects

Date logic:
  --date          uses file mtime  (what did I touch on this day?)
  --from / --to   uses the date in the path  (what work lived in this period?)
                  YYYYMMDD or the date part of a YYYYMMDDHHMM stamp, then the
                  frontmatter created/ tag. Recogniser shared with
                  process_frontmatter via vault_config.

Output layout (the ops journal — `log_dir` in vault.json, `Log/` by default;
override per-run with --output-dir):
  daily  -> <log>/<week-Monday>/<YYYYMMDD>-daily-summary.md
  range  -> <log>/<runtimestamp>-<from>-<to>-range-summary.md
"""

import argparse
import hashlib
import json
import os
import re
import sqlite3
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import vault_config


DB_NAME = "vault-index.db"

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
HEADING_RE = re.compile(r"^(#{1,3})\s+(.+)$", re.MULTILINE)
WORK_FOLDER_RE = re.compile(r"^\d{8}-")


def _content_hash(text: str) -> str:
    """Stable hash of file content — lets us tell a real edit from a pure move
    (a move bumps mtime but leaves content, and its hash, unchanged)."""
    return hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()


def week_monday(d: date) -> date:
    """Monday of the week containing d — the ops-journal week-folder name (YYYYMMDD)."""
    return d - timedelta(days=d.weekday())


def open_db(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS files (
            path          TEXT    NOT NULL PRIMARY KEY,
            inode         INTEGER NOT NULL,
            mtime         REAL    NOT NULL,
            size          INTEGER NOT NULL,
            extracted     TEXT,
            indexed_at    REAL    NOT NULL,
            content_hash  TEXT,
            content_mtime REAL
        )
    """)
    # Migrate pre-existing DBs (created before content_hash/content_mtime).
    cols = {r[1] for r in conn.execute("PRAGMA table_info(files)")}
    if "content_hash" not in cols:
        conn.execute("ALTER TABLE files ADD COLUMN content_hash TEXT")
    if "content_mtime" not in cols:
        conn.execute("ALTER TABLE files ADD COLUMN content_mtime REAL")
        # Best-effort backfill: assume existing rows' content changed at their mtime.
        conn.execute("UPDATE files SET content_mtime = mtime WHERE content_mtime IS NULL")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_inode ON files(inode)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_mtime ON files(mtime)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_content_mtime ON files(content_mtime)")
    conn.commit()
    return conn


def parse_frontmatter_tags(frontmatter: str) -> list[str]:
    """Extract tag values from YAML frontmatter tags block."""
    tags = []
    in_tags = False
    for line in frontmatter.splitlines():
        if re.match(r"^tags\s*:", line):
            in_tags = True
            # Inline list: tags: ["#a", "#b"]
            m = re.search(r"\[(.+)\]", line)
            if m:
                for t in m.group(1).split(","):
                    tags.append(t.strip().strip("\"'").lstrip("#"))
                in_tags = False
        elif in_tags:
            m = re.match(r'^\s*-\s+"?#?(.+?)"?\s*$', line)
            if m:
                tags.append(m.group(1).strip())
            elif line and line[0].isalpha():
                in_tags = False
    return tags


def extract_sections(content: str, path: str) -> dict:
    frontmatter_text = ""
    body = content
    m = FRONTMATTER_RE.match(content)
    if m:
        frontmatter_text = m.group(1)
        body = content[m.end():]

    title = Path(path).stem
    headings = []
    for hm in HEADING_RE.finditer(body):
        level = len(hm.group(1))
        text = hm.group(2).strip()
        headings.append({"level": level, "text": text})
        if level == 1 and title == Path(path).stem:
            title = text

    tags = parse_frontmatter_tags(frontmatter_text)

    return {"title": title, "headings": headings, "tags": tags}


def work_group(rel_path: str) -> str:
    """Return the work-item folder name for grouping related files."""
    for part in Path(rel_path).parts:
        if WORK_FOLDER_RE.match(part):
            return part
    return str(Path(rel_path).parent)


def path_date(rel_path: str, extracted_json: str | None = None,
              config: dict | None = None) -> str | None:
    """Extract YYYYMMDD from path prefix, then frontmatter created tag, or None.

    The date recogniser is shared with process_frontmatter via vault_config, so
    both tools agree on what a dated name looks like — including the vault's
    YYYYMMDDHHMM stamps, which an 8-digit-only pattern silently misses.
    """
    for part in Path(rel_path).parts:
        found = vault_config.date_from_text(part)
        if found:
            return found
    if extracted_json:
        created_prefix = (config or vault_config.DEFAULTS)["tag_prefixes"]["created"]
        try:
            ext = json.loads(extracted_json)
            for tag in ext.get("tags", []):
                if isinstance(tag, str) and tag.startswith(created_prefix):
                    d = tag[len(created_prefix):]
                    if re.match(r"^\d{8}$", d):
                        return d
        except (json.JSONDecodeError, TypeError):
            pass
    return None


def scan_vault(
    vault_root: Path,
    conn: sqlite3.Connection,
    folders: list[str] | None = None,
    reindex: bool = False,
    config: dict | None = None,
) -> dict:
    config = config or vault_config.DEFAULTS
    stats = {"scanned": 0, "new": 0, "updated": 0, "moved": 0, "unchanged": 0}

    cur = conn.execute("SELECT path, inode, mtime, size, content_hash, content_mtime FROM files")
    db_by_path: dict[str, dict] = {}
    db_by_inode: dict[int, str] = {}
    for path, inode, mtime, size, content_hash, content_mtime in cur:
        db_by_path[path] = {
            "inode": inode, "mtime": mtime, "size": size,
            "content_hash": content_hash, "content_mtime": content_mtime,
        }
        db_by_inode[inode] = path

    now = datetime.now().timestamp()

    for dirpath, dirnames, filenames in os.walk(vault_root):
        vault_config.prune_dirs(dirnames, config)

        for filename in filenames:
            if not filename.endswith(".md"):
                continue

            full_path = Path(dirpath) / filename
            rel_path = str(full_path.relative_to(vault_root))

            if folders and not any(rel_path.startswith(f) for f in folders):
                continue

            try:
                st = os.stat(full_path)
            except OSError:
                continue

            inode = st.st_ino
            mtime = st.st_mtime
            size = st.st_size
            stats["scanned"] += 1

            existing = db_by_path.get(rel_path)

            # Fast skip: same path, unchanged mtime + size → no content read.
            if not reindex and existing and existing["mtime"] == mtime and existing["size"] == size:
                stats["unchanged"] += 1
                continue

            # A move = the same inode seen at a different path.
            moved_from = db_by_inode.get(inode)
            if moved_from == rel_path:
                moved_from = None

            # Not skippable → read content and decide whether it *actually* changed.
            # (A move bumps mtime, so it fails the fast-skip and lands here — but its
            # content hash still matches, so we won't count it as a content change.)
            try:
                content = full_path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue

            new_hash = _content_hash(content)
            extracted_json = json.dumps(extract_sections(content, rel_path))

            prior = db_by_path.get(moved_from) if moved_from else existing
            content_changed = reindex or prior is None or prior.get("content_hash") != new_hash
            # content_mtime advances ONLY on a real content change; a pure move keeps
            # the prior value, so moved-only files don't surface in the daily summary.
            content_mtime_val = mtime if content_changed else prior.get("content_mtime", mtime)

            if moved_from:
                conn.execute(
                    "UPDATE files SET path=?, inode=?, mtime=?, size=?, extracted=?, "
                    "indexed_at=?, content_hash=?, content_mtime=? WHERE inode=?",
                    (rel_path, inode, mtime, size, extracted_json, now, new_hash, content_mtime_val, inode),
                )
                db_by_path.pop(moved_from, None)
                stats["moved"] += 1
            elif existing:
                conn.execute(
                    "UPDATE files SET inode=?, mtime=?, size=?, extracted=?, "
                    "indexed_at=?, content_hash=?, content_mtime=? WHERE path=?",
                    (inode, mtime, size, extracted_json, now, new_hash, content_mtime_val, rel_path),
                )
                stats["updated"] += 1
            else:
                conn.execute(
                    "INSERT INTO files (path, inode, mtime, size, extracted, indexed_at, content_hash, content_mtime) "
                    "VALUES (?,?,?,?,?,?,?,?)",
                    (rel_path, inode, mtime, size, extracted_json, now, new_hash, content_mtime_val),
                )
                stats["new"] += 1

            db_by_inode[inode] = rel_path
            db_by_path[rel_path] = {
                "inode": inode, "mtime": mtime, "size": size,
                "content_hash": new_hash, "content_mtime": content_mtime_val,
            }

    conn.commit()
    return stats


def build_summary_body(rows: list, title: str) -> str:
    """Render grouped work items as markdown body (no frontmatter)."""
    groups: dict[str, list] = {}
    for path, sort_key, extracted_json in rows:
        group = work_group(path)
        groups.setdefault(group, []).append((path, sort_key, extracted_json))

    lines = [
        f"# {title}",
        f"_{len(rows)} file(s) across {len(groups)} work item(s)_\n",
    ]

    for group, files in groups.items():
        lines.append(f"## {group}\n")
        for path, sort_key, extracted_json in files:
            ext = json.loads(extracted_json) if extracted_json else {}
            link = str(Path(path).with_suffix(""))
            h2s = [h["text"] for h in ext.get("headings", []) if h["level"] == 2]
            tags = ext.get("tags", [])
            sections_str = f" · {' · '.join(h2s)}" if h2s else ""
            tags_str = f"  `{'` `'.join(tags)}`" if tags else ""
            lines.append(f"- [[{link}]] · {sort_key}{sections_str}{tags_str}")
        lines.append("")

    return "\n".join(lines)


def summary_frontmatter(date_str: str, note_type: str, config: dict | None = None) -> str:
    """Frontmatter block for a generated summary note.

    Tag prefixes come from vault_config; `note_type` is the genre value that
    follows the `type/` prefix. The leading `#` and the quoting are this tool's
    output style, not part of the prefix.
    """
    config = config or vault_config.DEFAULTS
    created = vault_config.tag(config, "created", date_str)
    kind = vault_config.tag(config, "type", note_type)
    return (
        f"---\n"
        f"created: \"{date_str}\"\n"
        f"tags:\n"
        f"  - \"#{created}\"\n"
        f"  - \"#{kind}\"\n"
        f"---\n\n"
    )


def format_daily_summary(conn: sqlite3.Connection, target_date: date, folders: list[str] | None,
                         config: dict | None = None) -> str:
    """Summary for a single date — uses mtime."""
    day_start = datetime.combine(target_date, datetime.min.time()).timestamp()
    day_end = datetime.combine(target_date, datetime.max.time()).timestamp()

    # Filter on content_mtime (advances only on real content change), so files
    # that were merely moved — bumping filesystem mtime but not content — don't
    # show up as activity on the move day.
    query = "SELECT path, content_mtime, extracted FROM files WHERE content_mtime >= ? AND content_mtime <= ?"
    params: list = [day_start, day_end]
    if folders:
        placeholders = " OR ".join("path LIKE ?" for _ in folders)
        query += f" AND ({placeholders})"
        params.extend(f"{f}/%" for f in folders)
    query += " ORDER BY content_mtime DESC"

    rows = conn.execute(query, params).fetchall()
    rows_normalized = [(p, datetime.fromtimestamp(m).strftime("%H:%M"), e) for p, m, e in rows]

    date_str = target_date.strftime("%Y%m%d")
    frontmatter = summary_frontmatter(date_str, "daily-summary", config)

    if not rows:
        return frontmatter + f"# Vault activity: {target_date}\n\nNo files modified today."

    return frontmatter + build_summary_body(rows_normalized, f"Vault activity: {target_date}")


def format_range_summary(
    conn: sqlite3.Connection,
    from_date: date,
    to_date: date,
    folders: list[str] | None,
    command_str: str = "",
    config: dict | None = None,
) -> str:
    """Summary for a date range — uses YYYYMMDD- prefix in path."""
    from_str = from_date.strftime("%Y%m%d")
    to_str = to_date.strftime("%Y%m%d")

    all_rows = conn.execute("SELECT path, extracted FROM files").fetchall()

    matched = []
    for path, extracted_json in all_rows:
        if folders and not any(path.startswith(f) for f in folders):
            continue
        d = path_date(path, extracted_json, config)
        if d and from_str <= d <= to_str:
            matched.append((path, d, extracted_json))

    matched.sort(key=lambda r: r[1])

    date_str = datetime.now().strftime("%Y%m%d")
    frontmatter = summary_frontmatter(date_str, "range-summary", config)

    command_line = f"> `{command_str}`\n\n" if command_str else ""

    if not matched:
        return frontmatter + command_line + f"# Vault activity: {from_date} → {to_date}\n\nNo work items found in this range."

    return frontmatter + command_line + build_summary_body(matched, f"Vault activity: {from_date} → {to_date}")


def main():
    parser = argparse.ArgumentParser(
        description="Vault file indexer and work summarizer"
    )
    parser.add_argument("command", choices=["index", "summary"])
    parser.add_argument("--vault", type=Path, help="Vault root (auto-detected from vault.json if omitted)")
    parser.add_argument("--db", type=Path, help=f"Database path (default: <script-dir>/{DB_NAME})")
    parser.add_argument(
        "--folders", nargs="+", metavar="FOLDER",
        help="Restrict to files under these folders (e.g. 00-Inbox/work 02-Projects)"
    )
    parser.add_argument(
        "--output-dir", type=Path, default=None,
        help="Where summaries are written (default: the vault's log_dir from vault.json). "
             "Relative paths resolve against the vault root."
    )

    # index flags
    parser.add_argument("--reindex", action="store_true", help="Force re-read all files regardless of mtime")

    # summary flags (mutually exclusive: single date vs range)
    date_group = parser.add_mutually_exclusive_group()
    date_group.add_argument(
        "--date", type=lambda s: date.fromisoformat(s), default=None,
        help="Single date summary using mtime (YYYY-MM-DD, default: today)"
    )
    date_group.add_argument(
        "--from", dest="from_date", type=lambda s: date.fromisoformat(s),
        help="Range start date using path date (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--to", dest="to_date", type=lambda s: date.fromisoformat(s), default=date.today(),
        help="Range end date (YYYY-MM-DD, default: today). Use with --from."
    )

    args = parser.parse_args()

    script_dir = Path(__file__).parent
    db_path = args.db or (script_dir / DB_NAME)
    vault_root = args.vault or vault_config.find_vault_root(script_dir) or script_dir.resolve()
    config = vault_config.load_config(vault_root)

    # --output-dir wins, then vault.json's log_dir. A relative override resolves
    # against the vault root so `--output-dir Log/scratch` does what it reads like.
    output_dir = args.output_dir or Path(config["log_dir"])
    if not output_dir.is_absolute():
        output_dir = vault_root / output_dir

    print(f"Vault: {vault_root}", file=sys.stderr)
    print(f"DB:    {db_path}", file=sys.stderr)

    conn = open_db(db_path)

    if args.command == "index":
        stats = scan_vault(vault_root, conn, folders=args.folders,
                           reindex=args.reindex, config=config)
        print(
            f"scanned={stats['scanned']}  new={stats['new']}  "
            f"updated={stats['updated']}  moved={stats['moved']}  "
            f"unchanged={stats['unchanged']}",
            file=sys.stderr,
        )

    elif args.command == "summary":
        stats = scan_vault(vault_root, conn, folders=args.folders, config=config)
        print(
            f"indexed: new={stats['new']} updated={stats['updated']} moved={stats['moved']}",
            file=sys.stderr,
        )

        if args.from_date:
            # Range summary — timestamped filename prevents overwrite on re-runs
            command_str = "python vault_indexer.py summary" + \
                f" --from {args.from_date}" + \
                f" --to {args.to_date}" + \
                (f" --folders {' '.join(args.folders)}" if args.folders else "")
            content = format_range_summary(conn, args.from_date, args.to_date, args.folders,
                                           command_str, config)
            run_ts = datetime.now().strftime("%Y%m%d%H%M")
            from_str = args.from_date.strftime("%Y%m%d")
            to_str = args.to_date.strftime("%Y%m%d")
            # Range reports span weeks, so they live at the log root (not a week folder).
            out_path = output_dir / f"{run_ts}-{from_str}-{to_str}-range-summary.md"
        else:
            # Daily summary → <log>/<week-Monday>/<YYYYMMDD>-daily-summary.md (flat in the week folder)
            target = args.date or date.today()
            content = format_daily_summary(conn, target, args.folders, config)
            day_str = target.strftime("%Y%m%d")
            out_path = (
                output_dir / week_monday(target).strftime("%Y%m%d")
                / f"{day_str}-daily-summary.md"
            )

        # Nested Log/ folders may not exist yet — create them before writing.
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(content, encoding="utf-8")
        print(f"Written: {out_path}", file=sys.stderr)

    conn.close()


if __name__ == "__main__":
    main()
