#!/usr/bin/env python3
"""
process_frontmatter.py — stamp created/ and updated/ tags into markdown frontmatter.

Reads every `.md` file under a directory, works out the most accurate creation
date it can, and writes `created/YYYYMMDD` + `updated/YYYYMMDD` tags into the
YAML frontmatter. Tag prefixes and skip-dirs come from `vault_config`.

**Dry-run is the default.** The blast radius is every markdown file in the
vault, so nothing is written unless you pass `--apply`.

Usage:
  # Preview across the whole vault (auto-detected from vault.json)
  python3 process_frontmatter.py

  # Preview one subtree
  python3 process_frontmatter.py --directory 02-Projects

  # Write the changes you just previewed
  python3 process_frontmatter.py --apply

Date resolution (decision table — mirrored in tests/test_process_frontmatter.py):

  filename has date + existing tag        -> do nothing (filename is authoritative)
  filename has date, no existing tag      -> stamp with filename date
  no filename date, path date older       -> update existing tag to path date
  no filename date, path date newer/equal -> do nothing (existing tag is correct)
  no filename date, path date, no tag     -> stamp with path date
  no path date, git date older than tag   -> update existing tag to git date
  no path date, git date newer/equal      -> do nothing (existing tag is correct)
  no path date, no tag, tracked in git    -> stamp with git date
  no path date, no tag, untracked         -> skip, and say so

"Filename date" = YYYYMMDD in the bare filename (e.g. notes-20220411.md), or the
                  date part of a YYYYMMDDHHMM stamp (e.g. 202605261954-spike.md).
"Path date"     = the same, in a parent folder component (e.g. OOMKilled-20231024/notes.md).
"Git date"      = the date of the first commit that added the file.

Why git and not the filesystem:
  This tool used to fall back to `min(st_ctime, st_mtime)`. Vault mtimes do not
  survive bulk copies — see [[03-Resources/tools/20260605-filesystem-timestamps-unreliable]],
  which ranked the sources (path date > created/ tag > mtime ❌) and decided the
  mtime fallback should go. Measured on this vault 2026-08-08, mtime dated
  CLAUDE.md to 20260729 where git says 20250924: a fabricated date, ten months
  wrong, indistinguishable in the output from a real one. Switching to git also
  corrected two files still carrying the bogus 20241223 floor date.

  Known limitation: git reports when a path was *added*, so a file that was
  renamed or moved carries the move date, not its original creation date. Files
  moved in a bulk reorg are almost always dated by filename or path anyway, so
  they never reach this branch. Untracked files are skipped rather than guessed.
"""
import argparse
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import vault_config


def _prefix(config, kind):
    """Tag prefix for `kind`, falling back to the stock vocabulary."""
    return (config or vault_config.DEFAULTS)["tag_prefixes"][kind]


def extract_date_from_filename(filename):
    """Extract YYYYMMDD from anywhere in the given string (full path or bare name)."""
    match = re.search(r'(\d{8})', filename)
    if match:
        try:
            datetime.strptime(match.group(1), '%Y%m%d')
            return match.group(1)
        except ValueError:
            pass
    return None


# The vault's date-in-name convention lives in vault_config — vault-indexer reads
# the same one. Re-exported here so this module's public surface is unchanged.
date_from_text = vault_config.date_from_text


def get_filename_date(file_path):
    """Extract YYYYMMDD from the bare filename only (not parent folders)."""
    return date_from_text(Path(file_path).name)


def get_path_date(file_path):
    """Extract YYYYMMDD from parent folder components only (not the filename)."""
    for part in Path(file_path).parts[:-1]:
        found = date_from_text(part)
        if found:
            return found
    return None


def get_existing_created_date(frontmatter, config=None):
    """Return YYYYMMDD from an existing created/ tag or created: field, or None."""
    if not frontmatter:
        return None
    if 'created' in frontmatter:
        d = str(frontmatter['created']).replace('-', '').replace('/', '')
        if re.match(r'^\d{8}$', d):
            return d
    created_prefix = _prefix(config, 'created')
    for tag in frontmatter.get('tags', []) or []:
        if isinstance(tag, str) and tag.startswith(created_prefix):
            d = tag[len(created_prefix):]
            if re.match(r'^\d{8}$', d):
                return d
    return None


def git_add_dates(repo_root):
    """Map repo-relative path -> YYYYMMDD of the commit that first added it.

    One `git log` pass over the whole history rather than a subprocess per file:
    ~2s for a 96k-path repo versus minutes. `--reverse` means the first date
    seen for a path is the earliest. Returns {} if this isn't a git repo, which
    makes every fallback lookup miss and every affected file skip.
    """
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), "log", "--reverse", "--no-renames",
             "--diff-filter=A", "--format=@%ad", "--date=format:%Y%m%d", "--name-only"],
            capture_output=True, text=True, check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return {}

    dates = {}
    current = None
    for line in result.stdout.splitlines():
        if line.startswith("@"):
            current = line[1:]
        elif line and current and line not in dates:
            dates[line] = current
    return dates


def parse_frontmatter(content):
    """Parse YAML frontmatter from markdown content."""
    if not content.startswith('---\n'):
        return None, content
    end_match = re.search(r'\n---\n', content)
    if not end_match:
        return None, content
    frontmatter_text = content[4:end_match.start()]
    remaining_content = content[end_match.end():]
    try:
        frontmatter = yaml.safe_load(frontmatter_text)
        return frontmatter, remaining_content
    except yaml.YAMLError:
        return None, content


def has_created_tag_or_field(frontmatter):
    """Check if frontmatter already has a created tag or field."""
    return get_existing_created_date(frontmatter) is not None


def add_created_and_updated_tags(frontmatter, created_date, updated_date, config=None):
    """Add created/YYYYMMDD and updated/YYYYMMDD tags to frontmatter."""
    if not frontmatter:
        frontmatter = {}
    if 'created' in frontmatter:
        created_value = str(frontmatter['created']).replace('-', '').replace('/', '')
        if re.match(r'\d{8}', created_value):
            created_date = created_value
        del frontmatter['created']
    if 'tags' not in frontmatter or not isinstance(frontmatter['tags'], list):
        frontmatter['tags'] = []
    created_tag = f"{_prefix(config, 'created')}{created_date}"
    updated_tag = f"{_prefix(config, 'updated')}{updated_date}"
    if created_tag not in frontmatter['tags']:
        frontmatter['tags'].insert(0, created_tag)
    frontmatter['tags'].append(updated_tag)
    return frontmatter


def format_frontmatter(frontmatter):
    """Format frontmatter dict as a YAML front-matter block."""
    if not frontmatter:
        return ""
    yaml_content = yaml.dump(frontmatter, default_flow_style=False, sort_keys=False)
    return f"---\n{yaml_content}---\n"


def resolve_created_date(file_path, existing_date, git_date):
    """Decision table, as values in and a value out.

    Returns (created_date, reason). `created_date` is None when nothing should
    change; `reason` is "noop", "skip", or the branch that decided the date.
    """
    filename_date = get_filename_date(file_path)
    if filename_date:
        if existing_date:
            return None, "noop"
        return filename_date, "filename"

    path_date = get_path_date(file_path)
    if path_date:
        if existing_date and path_date >= existing_date:
            return None, "noop"
        return path_date, "path"

    if existing_date:
        if not git_date or git_date >= existing_date:
            return None, "noop"
        return git_date, "git"
    if not git_date:
        return None, "skip"
    return git_date, "git"


def process_file(file_path, dry_run=False, git_date=None, config=None):
    """Process a single markdown file per the date resolution decision table."""
    updated_date = datetime.now().strftime('%Y%m%d')

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        return f"Error reading {file_path}: {e}"

    frontmatter, body_content = parse_frontmatter(content)
    existing_date = get_existing_created_date(frontmatter, config)
    created_date, reason = resolve_created_date(file_path, existing_date, git_date)

    if reason == "skip":
        return f"Skipped (no date available): {file_path}"
    if created_date is None:
        return None

    created_prefix = _prefix(config, 'created')
    updated_prefix = _prefix(config, 'updated')

    # Build updated frontmatter — strip old created/ tags, insert new one
    if frontmatter is None:
        frontmatter = {}
    if 'created' in frontmatter:
        del frontmatter['created']
    if not isinstance(frontmatter.get('tags'), list):
        frontmatter['tags'] = []
    frontmatter['tags'] = [t for t in frontmatter['tags']
                           if not (isinstance(t, str) and t.startswith(created_prefix))]
    frontmatter['tags'].insert(0, f'{created_prefix}{created_date}')
    frontmatter['tags'].append(f'{updated_prefix}{updated_date}')

    new_content = format_frontmatter(frontmatter) + body_content
    action = "update" if existing_date else "add"
    desc = f"{created_prefix}{created_date}, {updated_prefix}{updated_date}"

    if dry_run:
        return f"Would {action} {desc} in {file_path}"

    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        return f"{action.capitalize()}d {desc} in {file_path}"
    except Exception as e:
        return f"Error writing {file_path}: {e}"


def collect_markdown(base_dir, config):
    """Every .md under base_dir whose parent directories aren't skipped."""
    files = []
    for path in base_dir.rglob('*.md'):
        try:
            parts = path.relative_to(base_dir).parts[:-1]
        except ValueError:
            continue
        if any(vault_config.is_skipped_dir(p, config) for p in parts):
            continue
        files.append(path)
    return sorted(files)


def main():
    parser = argparse.ArgumentParser(
        description='Add/update created/ and updated/ tags in markdown frontmatter. '
                    'Previews by default; pass --apply to write.'
    )
    parser.add_argument('--directory', type=Path, default=None,
                        help='Directory to process (default: the vault root, found via vault.json)')
    parser.add_argument('--apply', action='store_true',
                        help='Actually write the changes. Without this, nothing is written.')
    parser.add_argument('--dry-run', action='store_true',
                        help='Explicitly preview only. This is already the default; '
                             'if combined with --apply, nothing is written.')
    args = parser.parse_args()

    dry_run = args.dry_run or not args.apply

    vault_root = vault_config.find_vault_root(Path.cwd()) or Path.cwd()
    config = vault_config.load_config(vault_root)
    base_dir = (args.directory or vault_root).resolve()

    print(f"Vault:  {vault_root}")
    print(f"Target: {base_dir}")
    print(f"Mode:   {'DRY RUN — nothing will be written' if dry_run else 'APPLY — files will be rewritten'}")

    md_files = collect_markdown(base_dir, config)
    git_dates = git_add_dates(vault_root)
    print(f"Found {len(md_files)} markdown files to process "
          f"({len(git_dates)} paths have a git add-date)")

    changes_made = 0
    skipped = 0
    errors = []

    for i, file_path in enumerate(md_files):
        if i % 100 == 0:
            print(f"Processing file {i+1}/{len(md_files)}")
        try:
            rel = str(file_path.relative_to(vault_root))
        except ValueError:
            rel = None
        result = process_file(file_path, dry_run=dry_run,
                              git_date=git_dates.get(rel), config=config)
        if result is None:
            pass
        elif result.startswith("Error"):
            errors.append(result)
        elif result.startswith("Skipped"):
            skipped += 1
        else:
            changes_made += 1
            if dry_run or changes_made <= 10:
                print(result)

    print(f"\nSummary:")
    print(f"  Files processed: {len(md_files)}")
    print(f"  Changes {'pending' if dry_run else 'made'}:    {changes_made}")
    print(f"  Skipped:         {skipped}")
    print(f"  Errors:          {len(errors)}")
    if errors:
        print(f"\nFirst few errors:")
        for error in errors[:5]:
            print(f"  {error}")
    if dry_run and changes_made:
        print(f"\nNothing was written. Re-run with --apply to make these {changes_made} changes.")


if __name__ == '__main__':
    main()
