#!/usr/bin/env python3
"""
test_chunker.py — the chunking contract from chunker.py, enforced.

This file is the specification. The table it encodes:

| Decision            | Expected behaviour                                        |
| ------------------- | --------------------------------------------------------- |
| Frontmatter         | Stripped from body; `tags:` list returned separately       |
| `---` mid-document  | NOT frontmatter — it is a horizontal rule, body preserved  |
| Unterminated `---`  | Whole file treated as body, no crash                       |
| Headings            | Start a new section; trail is `H1 > H2 > H3`               |
| Deeper→shallower    | Deeper levels cleared from the trail                       |
| `#` inside a fence  | A shell comment, NOT a heading                             |
| Context prefix      | `title > heading | tags` prepended to embedded text        |
| Oversized paragraph | Hard-split at target_chars                                 |
| Per-file cap        | Never exceeds max_chunks                                   |
| Tiny/empty chunks   | Dropped                                                    |
| Purity              | Same input → identical output                              |

No network, no filesystem, no DB — chunking is pure.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from chunker import Chunk, chunk_markdown, strip_frontmatter  # noqa: E402


class TestStripFrontmatter:
    def test_removes_leading_block_and_returns_tags(self):
        text = "---\ntags:\n  - created/20260911\n  - type/note\n---\n\n# Title\n\nBody."
        body, tags = strip_frontmatter(text)
        assert "tags:" not in body
        assert "Body." in body
        assert tags == ["created/20260911", "type/note"]

    def test_horizontal_rule_mid_document_is_not_frontmatter(self):
        text = "# Title\n\nIntro.\n\n---\n\nMore body."
        body, tags = strip_frontmatter(text)
        assert body == text
        assert tags == []

    def test_unterminated_block_returns_whole_text(self):
        text = "---\ntags:\n  - x\n\nno closing delimiter"
        body, tags = strip_frontmatter(text)
        assert body == text
        assert tags == []

    def test_no_frontmatter_is_passthrough(self):
        text = "# Just a heading\n\nand text"
        assert strip_frontmatter(text) == (text, [])


class TestHeadingTrail:
    def test_nested_headings_build_a_trail(self):
        text = "# Top\n\n" + "a" * 40 + "\n\n## Middle\n\n" + "b" * 40 + "\n\n### Deep\n\n" + "c" * 40
        chunks = chunk_markdown(text, title="Doc")
        trails = [c.heading for c in chunks]
        assert "Top" in trails
        assert "Top > Middle" in trails
        assert "Top > Middle > Deep" in trails

    def test_returning_to_shallower_level_clears_deeper(self):
        text = ("# A\n\n" + "x" * 40 + "\n\n## B\n\n" + "y" * 40 +
                "\n\n### C\n\n" + "z" * 40 + "\n\n## D\n\n" + "w" * 40)
        chunks = chunk_markdown(text, title="Doc")
        trails = [c.heading for c in chunks]
        assert "A > D" in trails
        # C must not leak into D's trail
        assert not any(t.endswith("C > D") or "C > D" in t for t in trails)

    def test_hash_inside_code_fence_is_not_a_heading(self):
        text = ("# Real\n\n" + "intro text here padded out\n\n"
                "```bash\n# this is a shell comment\nkubectl get pods\n```\n\n"
                "trailing prose that is long enough to keep\n")
        chunks = chunk_markdown(text, title="Doc")
        assert all(c.heading in ("Real", "") for c in chunks)
        assert any("shell comment" in c.body for c in chunks)


class TestContextPrefix:
    def test_embedded_text_carries_title_and_heading(self):
        text = "---\ntags:\n  - domain/k8s\n---\n\n# Findings\n\n" + "detail " * 20
        chunks = chunk_markdown(text, title="My Note")
        assert chunks
        assert chunks[0].text.startswith("My Note > Findings")
        assert "domain/k8s" in chunks[0].text

    def test_body_excludes_the_prefix(self):
        text = "# H\n\n" + "payload " * 20
        c = chunk_markdown(text, title="T")[0]
        assert not c.body.startswith("T > H")
        assert c.body in c.text

    def test_no_title_or_heading_still_produces_a_chunk(self):
        chunks = chunk_markdown("just some prose with no structure at all", title="")
        assert len(chunks) == 1
        assert chunks[0].heading == ""


class TestSizing:
    def test_short_document_is_one_chunk(self):
        chunks = chunk_markdown("# H\n\nshort but definitely long enough", title="T")
        assert len(chunks) == 1

    def test_long_document_splits(self):
        para = "word " * 100          # ~500 chars
        text = "# H\n\n" + "\n\n".join([para] * 10)
        chunks = chunk_markdown(text, title="T", target_chars=600)
        assert len(chunks) > 1

    def test_oversized_single_paragraph_is_hard_split(self):
        text = "# H\n\n" + ("x" * 5000)
        chunks = chunk_markdown(text, title="T", target_chars=1000)
        assert len(chunks) >= 5
        assert all(len(c.body) <= 1000 for c in chunks)

    def test_respects_max_chunks_cap(self):
        # The git-status.md case: a huge file must not flood the index.
        text = "# H\n\n" + "\n\n".join(["para " * 100] * 200)
        chunks = chunk_markdown(text, title="T", target_chars=500, max_chunks=10)
        assert len(chunks) == 10

    def test_ordinals_are_sequential_from_zero(self):
        text = "# H\n\n" + "\n\n".join(["block " * 60] * 6)
        chunks = chunk_markdown(text, title="T", target_chars=400)
        assert [c.ordinal for c in chunks] == list(range(len(chunks)))


class TestDropsEmpty:
    def test_whitespace_only_document_yields_nothing(self):
        assert chunk_markdown("   \n\n  \n", title="T") == []

    def test_frontmatter_only_document_yields_nothing(self):
        assert chunk_markdown("---\ntags:\n  - a\n---\n", title="T") == []

    def test_heading_with_no_body_yields_nothing(self):
        assert chunk_markdown("# Heading\n\n## Another\n", title="T") == []

    def test_tiny_fragment_is_dropped(self):
        assert chunk_markdown("# H\n\nok\n", title="T") == []


class TestPurity:
    def test_same_input_gives_identical_output(self):
        text = "# A\n\n" + "content " * 50 + "\n\n## B\n\n" + "more " * 50
        first = chunk_markdown(text, title="T")
        second = chunk_markdown(text, title="T")
        assert [(c.ordinal, c.heading, c.body, c.text) for c in first] == \
               [(c.ordinal, c.heading, c.body, c.text) for c in second]

    def test_returns_chunk_instances(self):
        chunks = chunk_markdown("# H\n\nlong enough body text here", title="T")
        assert all(isinstance(c, Chunk) for c in chunks)
