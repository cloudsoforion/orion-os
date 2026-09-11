#!/usr/bin/env python3
"""
chunker.py — split a markdown note into embeddable, heading-aware chunks.

Pure functions only: text in, chunks out. No I/O, no network, no DB — so the whole
chunking contract is testable without Ollama or the vault (see tests/test_chunker.py).

Why this exists: `embed.py` embeds only `path | title | headings | tags`, never the
body, which makes that index a table of contents rather than a search index. With
headings alone, notes that share a structural vocabulary (Findings / Impact /
Decision) all look equally similar to any query, and nonsense input can score above
the retrieval floor.

The chunking contract:

| Decision | Behaviour | Why |
| --- | --- | --- |
| Frontmatter | Stripped from the body; `tags:` kept as context | YAML keys are noise; tags are signal |
| Split points | Markdown headings first, then paragraph breaks | A heading is the author's own topic boundary |
| Chunk size | Flush once a section exceeds `target_chars` at the last blank line | Paragraph-aligned chunks read as prose, not fragments |
| Context prefix | `title > H1 > H2 > H3` prepended to every chunk | A chunk about "Root cause" is meaningless without its doc |
| Oversized paragraph | Hard-split at `target_chars` | One 40 KB table must not become one 40 KB chunk |
| Per-file cap | `max_chunks` (default 40) | One pasted terminal dump can be megabytes and would alone produce thousands of chunks |
| Empty/whitespace | Dropped | Never embed an empty string |

Usage:
  # Not an entrypoint — import it.
  from chunker import chunk_markdown
  chunks = chunk_markdown(text, title="My Note", target_chars=1500)

  # Inspect chunking for one file without embedding anything:
  python3 chunker.py --file path/to/note.md --target 1500
"""

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

DEFAULT_TARGET_CHARS = 1500
DEFAULT_MAX_CHUNKS = 40
MIN_CHUNK_CHARS = 20  # below this a chunk carries no retrievable signal

HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
FENCE_RE = re.compile(r"^\s*(```|~~~)")


@dataclass
class Chunk:
    """One embeddable unit: `text` is what gets embedded, the rest is metadata."""
    ordinal: int
    heading: str      # the heading trail, e.g. "Findings > Root cause"
    body: str         # the raw chunk body, used as the returned snippet
    text: str         # context prefix + body — the string actually embedded


def strip_frontmatter(text: str) -> tuple[str, list[str]]:
    """Remove a leading YAML frontmatter block, returning (body, tags).

    Only a block that starts on line 1 counts — a `---` further down is a horizontal
    rule, and treating it as frontmatter would silently swallow the top of the note.
    """
    if not text.startswith("---"):
        return text, []
    lines = text.splitlines()
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            block = "\n".join(lines[1:i])
            tags = re.findall(r"^\s*-\s*([\w/\-.]+)\s*$", block, re.MULTILINE)
            return "\n".join(lines[i + 1:]), tags
    return text, []  # unterminated block: treat the whole file as body


def _heading_trail(stack: list[str]) -> str:
    return " > ".join(h for h in stack if h)


def _flush(buf: list[str], target: int) -> list[str]:
    """Split an accumulated section into paragraph-aligned pieces of ~`target` chars.

    Splits on blank lines so a chunk boundary never lands mid-sentence. A single
    paragraph longer than `target` is hard-split rather than emitted whole, which is
    what keeps a giant table or terminal dump from becoming one unsearchable blob.
    """
    text = "\n".join(buf).strip()
    if not text:
        return []
    if len(text) <= target:
        return [text]

    pieces: list[str] = []
    current: list[str] = []
    size = 0
    for para in re.split(r"\n\s*\n", text):
        para = para.strip()
        if not para:
            continue
        if len(para) > target:
            if current:
                pieces.append("\n\n".join(current))
                current, size = [], 0
            for i in range(0, len(para), target):
                pieces.append(para[i:i + target])
            continue
        if size + len(para) > target and current:
            pieces.append("\n\n".join(current))
            current, size = [], 0
        current.append(para)
        size += len(para) + 2
    if current:
        pieces.append("\n\n".join(current))
    return [p for p in pieces if p.strip()]


def chunk_markdown(
    text: str,
    title: str = "",
    target_chars: int = DEFAULT_TARGET_CHARS,
    max_chunks: int = DEFAULT_MAX_CHUNKS,
) -> list[Chunk]:
    """Split `text` into heading-aware chunks. Pure: same input, same output."""
    body, tags = strip_frontmatter(text)

    stack: list[str] = [""] * 6
    sections: list[tuple[str, list[str]]] = []
    buf: list[str] = []
    trail = ""
    in_fence = False

    for line in body.splitlines():
        if FENCE_RE.match(line):
            in_fence = not in_fence
        # A '#' inside a fence is a shell comment, not a heading.
        m = None if in_fence else HEADING_RE.match(line)
        if m:
            if buf:
                sections.append((trail, buf))
                buf = []
            level = len(m.group(1))
            stack[level - 1] = m.group(2).strip()
            for i in range(level, 6):
                stack[i] = ""
            trail = _heading_trail(stack)
            continue
        buf.append(line)
    if buf:
        sections.append((trail, buf))

    tag_ctx = " ".join(tags[:5])
    chunks: list[Chunk] = []
    ordinal = 0
    for heading, lines in sections:
        for piece in _flush(lines, target_chars):
            if len(piece.strip()) < MIN_CHUNK_CHARS:
                continue
            if ordinal >= max_chunks:
                return chunks
            context = " > ".join(p for p in (title, heading) if p)
            prefix = " | ".join(p for p in (context, tag_ctx) if p)
            chunks.append(Chunk(
                ordinal=ordinal,
                heading=heading,
                body=piece,
                text=f"{prefix}\n\n{piece}" if prefix else piece,
            ))
            ordinal += 1
    return chunks


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Show how a markdown file would be chunked (no embedding, no writes)")
    parser.add_argument("--file", type=Path, required=True, help="Markdown file to chunk")
    parser.add_argument("--target", type=int, default=DEFAULT_TARGET_CHARS,
                        help=f"Target chunk size in chars (default: {DEFAULT_TARGET_CHARS})")
    parser.add_argument("--max-chunks", type=int, default=DEFAULT_MAX_CHUNKS,
                        help=f"Per-file chunk cap (default: {DEFAULT_MAX_CHUNKS})")
    args = parser.parse_args()

    if not args.file.exists():
        print(f"No such file: {args.file}", file=sys.stderr)
        sys.exit(1)

    text = args.file.read_text(encoding="utf-8", errors="replace")
    chunks = chunk_markdown(text, title=args.file.stem,
                            target_chars=args.target, max_chunks=args.max_chunks)
    print(f"{args.file}: {len(chunks)} chunks ({len(text)} chars)\n")
    for c in chunks:
        print(f"--- [{c.ordinal}] {c.heading or '(no heading)'} — {len(c.body)} chars")
        print(c.body[:200].replace("\n", " ") + ("…" if len(c.body) > 200 else ""))
        print()


if __name__ == "__main__":
    main()
