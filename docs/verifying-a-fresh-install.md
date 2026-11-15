---
created: "20260911"
updated: "20260911"
tags:
  - created/20260911
  - updated/20260911
  - type/how-to
  - domain/knowledge-management
  - domain/tooling
  - status/active
status: active
---

# Verifying a fresh install

The tooling is developed against a vault with thousands of notes and years of history. That is the
easy case. **The case that breaks is a brand-new vault with nothing in it**, and it is the first
thing every adopter runs.

This is a throwaway smoke test you can run in a few minutes, in a temp directory, with no risk to
any real vault. Run it after a clone, after upgrading the tools, and before you tell anyone else to
try them.

It is written for `second-brain` and `vault-indexer` because those two have the most moving parts —
an external service (Ollama), two generated artifacts, and a two-stage build.

---

## Why this exists

The first time this test was run, **it found two bugs that the development vault structurally could
not surface** — both on the empty-vault path:

- `search.py` exited with a traceback (`sqlite3.OperationalError: no such table: embeddings`) instead
  of reporting an empty index. The legacy title-only table is only created by `embed.py`; on a fresh
  install only `embed_chunks.py` has ever run, so the fallback query hit a table that did not exist.
  **The first command a new adopter runs was the one that crashed.**
- `embed_chunks.py --stats` printed a blank line instead of its coverage line when the vault was
  empty — a conditional wrapped the whole statement rather than just the percentage.

Neither could ever fire on a populated vault. Both fire on every new one. That asymmetry is the
entire argument for keeping this test.

---

## Test 1 — the empty vault

The point is that **every command must fail gracefully**, not that anything is found.

```bash
EMPTY=/tmp/orion-empty
rm -rf "$EMPTY" && mkdir -p "$EMPTY/03-Resources/tools"
echo '{}' > "$EMPTY/vault.json"   # the root marker; without it the tools refuse to guess

# Copy in just the tooling — this is what an adopter has before writing any notes
cp -R /path/to/orion-os/03-Resources/tools/second-brain  "$EMPTY/03-Resources/tools/"
cp -R /path/to/orion-os/03-Resources/tools/vault-indexer "$EMPTY/03-Resources/tools/"
cp    /path/to/orion-os/03-Resources/tools/vault_config.py "$EMPTY/03-Resources/tools/"

# Strip every markdown file so the files table is genuinely empty,
# and remove any generated artifacts that came along for the ride
find "$EMPTY" -name '*.md' -delete
find "$EMPTY" \( -name '*.db' -o -name '*.npy' \) -delete
find "$EMPTY" -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null

cd "$EMPTY/03-Resources/tools/vault-indexer" && python3 vault_indexer.py index
cd "$EMPTY/03-Resources/tools/second-brain"
python3 embed_chunks.py --dry-run
python3 embed_chunks.py
python3 embed_chunks.py --stats
python3 search.py "anything at all";            echo "exit=$?"
python3 search.py "anything at all" --json;     echo "exit=$?"
echo '{"prompt":"a question about anything"}' | python3 hook.py; echo "exit=$?"
python3 benchmark.py >/dev/null 2>&1;           echo "benchmark exit=$?"
```

### What passing looks like

| Command | Expected |
|---|---|
| `vault_indexer.py index` | `scanned=0 new=0` — not an error |
| `embed_chunks.py --dry-run` | `would embed : 0 chunks`, writes nothing |
| `embed_chunks.py` | completes, `chunks=0 errors=0` |
| `embed_chunks.py --stats` | `Files covered : 0 / 0 indexed` **and** `Index is empty : run vault_indexer.py index first`. Matrix shape `(0, 768)` |
| `search.py` | a plain-English "index may be empty" message with the two commands to fix it — **never a traceback** — and `exit=0` |
| `search.py --json` | the same message on stderr, `[]` on stdout, so a caller parsing JSON is not broken |
| `hook.py` | **`exit=0` and no output.** The hook sits in front of a human pressing enter and must never block a prompt |
| `benchmark.py` | `Probe file not found: …/probes.json` and **`exit=1`** |

🔴 **A traceback anywhere here is a bug**, even if the tool "obviously" can't work yet. Empty is a
state, not an error.

⚠️ `echo $?` after a pipeline reports the exit status of the *last* command in the pipe, not your
script. Use `cmd >/dev/null 2>&1; echo $?` when you actually mean to check an exit code — the first
version of this test got that wrong and reported `exit=0` for a command that correctly exits 1.

---

## Test 2 — a minimal real vault

Now check that retrieval actually works, with just enough content to be meaningful.

```bash
PG=/tmp/orion-playground
# ... same tooling copy as above, but keep the pillar folders ...
mkdir -p "$PG/02-Projects/apollo" "$PG/01-Areas/homelab" "$PG/00-Inbox"
```

Write two or three notes with **real heading structure**, and make sure at least one has an answer
buried in a body paragraph that its title does not mention. For example, a note titled
`backup-strategy.md` whose body says *"snapshots were running but the prune job had stopped, so the
pool filled and new snapshots failed without any error surfacing."*

```bash
cd "$PG/03-Resources/tools/vault-indexer"  && python3 vault_indexer.py index
cd "$PG/03-Resources/tools/second-brain"   && python3 embed_chunks.py
python3 embed_chunks.py --stats
python3 search.py "backups were running but silently failing" --top 2
```

### What passing looks like

- `--stats` reports **100% coverage** — every indexed file produced chunks.
- The buried-answer query returns **the right note**, and the snippet contains the sentence you were
  thinking of. This is the whole point of chunking: the query words appear in no title or heading.
- Typical scores on a vault this small land around **0.5 – 0.7**.

Then author probes and get a baseline:

```bash
cp probes.example.json probes.json      # replace the REPLACE ME signal queries
python3 benchmark.py
```

`separation` should be **positive and above ~0.10**. Keep the shipped noise probes — they are the
control, and they are vault-independent.

---

## Things that will surprise you

- **Scores are lower on a small vault, and that is expected.** With only a handful of notes there is
  little to rank against, so scores compress and unrelated tool documentation (the `CHANGELOG.md`
  files you copied in) can appear in results. Retrieval gets *better* with content, not worse. Do not
  tune thresholds against a first-day vault.
- **The tool's own docs get indexed.** Copying `second-brain/` into a test vault brings ~4 markdown
  files with it, so a "empty" vault is not empty unless you delete them. Test 1 deletes them
  deliberately for exactly this reason.
- **Two build stages, and neither runs automatically.** `vault_indexer.py index` populates the
  `files` table; `embed_chunks.py` turns those into chunks. A note written after the last run is
  invisible to search until both have run again.
- **`vault-vectors.npy` is a generated artifact** and can be large. It is gitignored; a fresh clone
  has no index until both stages have run.
- **`embed_chunks.py` needs Ollama running.** If it is not, embedding fails per chunk rather than
  up front — check `ollama list` first.

---

## Related

- [[docs/adopting-into-an-existing-vault]] — bringing OrionOs to a vault you already have
- [[03-Resources/tools/second-brain/README]] — architecture, setup, and the two integration modes
- [[03-Resources/tools/CONTRIBUTING]] — the tooling standard these scripts are held to
