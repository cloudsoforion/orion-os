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

# Deploying second-brain

Everything in this repo runs **on one machine, against one vault, with no services beyond Ollama**.
That is a deliberate ceiling, not an unfinished state — and the first half of this document is about
why you probably should not raise it.

> ⚠️ **Read § The decision that comes first before anything else here.** Deployment questions look
> like infrastructure questions. This one is a data question, and getting the order wrong is how a
> personal journal ends up searchable by a team.

---

## The decision that comes first

**What does your index contain, and who should be able to read it?**

Since body-text chunking (v0.4.0) the answer changed materially. The `chunks` table stores the
**verbatim text of every note it indexes**, not just titles and headings. Concretely:

| | Before v0.4.0 | Now |
|---|---|---|
| What leaking the index would expose | a table of contents | **the content of every note** |

A personal vault is the worst case for sharing, because it is not curated for an audience. Working
notes accumulate credentials-adjacent detail, access procedures, incident specifics, customer and
colleague names, salary and performance material, half-formed opinions about people. None of that
was written to be read by anyone else, and no access-control layer fixes it after the fact.

So before choosing a deployment model, answer these:

- [ ] **Is the corpus the whole vault, or a subset?** If anything in it was written privately, the
      answer must be a subset.
- [ ] **Is the index derived data or a copy?** It is a copy. Treat `vault-index.db` and
      `vault-vectors.npy` with exactly the sensitivity of the notes they were built from.
- [ ] **Would you paste a random chunk into a team channel?** If not, the index does not belong on a
      shared host.

### Scoping the corpus

There is no per-folder include filter in `embed_chunks.py` today — it indexes whatever
`vault_indexer.py` put in the `files` table. Two honest options:

1. **Index a separate vault.** Point `SECOND_BRAIN_DB` at an index built from a vault that only
   contains shareable notes. Cleanest, and the only one with a hard boundary.
2. **Exclude at query time** — `exclude_prefixes` / `--no-archive` / `exclude_archive`. This shapes
   *results*, **not the index**. The sensitive chunks are still on disk and still one flag away.
   ⚠️ Do not mistake this for access control.

If you need a real include-filter, that is a feature to build, not a config to find.

---

## Model A — one machine (this is the supported one)

The default. Vault, index, Ollama and Claude Code all local; nothing leaves the machine.

```bash
ollama pull nomic-embed-text
pip install -r 03-Resources/tools/second-brain/requirements.txt
cd 03-Resources/tools/vault-indexer  && python3 vault_indexer.py index
cd ../second-brain                   && python3 embed_chunks.py
python3 register.py                  # writes the hook + MCP registrations
```

Verify it with [[docs/verifying-a-fresh-install]] before trusting it.

### Keeping it fresh — the part everyone skips

**Neither build stage runs automatically, and the index is only as good as its last run.** A note
written today is invisible to search until both have run again. This is not a rounding error: the
notes you most want to find are usually the ones you just wrote.

There is no incremental mode yet — `embed_chunks.py` is a full rebuild. Schedule it when you are not
using the machine:

```bash
# crontab -e   — nightly at 02:00
0 2 * * * cd /path/to/vault/03-Resources/tools/vault-indexer && /usr/bin/python3 vault_indexer.py index >> /tmp/sb.log 2>&1
5 2 * * * cd /path/to/vault/03-Resources/tools/second-brain && /usr/bin/python3 embed_chunks.py >> /tmp/sb.log 2>&1
```

### Sizing

Rough figures, scaling linearly with vault size:

| | Per unit | Example: ~5,000 notes |
|---|---|---|
| Chunks | ~8 per note | ~41,000 |
| Vector matrix | 3 KB per chunk | ~120 MB |
| Build time | ~20 ms per chunk | ~15 min |
| Query | one matmul | 20–30 ms |

**Both artifacts are generated and gitignored.** Never commit them — they are large, they change on
every rebuild, and per the section above they are a copy of your notes.

---

## Model B — several machines, one person

You want the same vault searchable on a laptop and a desktop.

**Sync the vault. Rebuild the index per machine.** Do not sync the index.

- The `.npy` is large and rewritten wholesale on each rebuild — a terrible fit for file sync, and a
  guaranteed conflict generator.
- Rebuilding is cheap and the result is deterministic.
- `SECOND_BRAIN_DB`, `SECOND_BRAIN_OLLAMA_URL` and `SECOND_BRAIN_EMBED_MODEL` mean a second machine
  needs no code edit. `register.py` resolves absolute paths for that checkout.

⚠️ **Every machine must run the same embedding model.** Vectors from different models still compare
— they just compare meaninglessly, and nothing warns you. This is why the model name is centralised
in `common.py`.

---

## Model C — shared with other people

**No supported path exists, and that is a judgement rather than a gap.**

What would actually be required, none of which is built:

- A real corpus include-filter, so "what is indexed" is enforced rather than remembered
- An identity model — the retrieval API has no concept of a user
- A hosted Ollama or equivalent, since embedding currently assumes localhost
- A shared vector store: this is the first case where Layer 2 (pgvector) earns its keep, because
  a memory-mapped file on one host does not serve concurrent readers well
- An answer to the question that has no technical solution: *whose notes are these, and did they
  agree to this?*

If the goal is to give colleagues this capability, **the far better answer is to give them the
tool, not your index.** It is a handful of Python files and a local model; everyone points it at
their own vault, and the privacy question disappears instead of being managed.

---

## Layers 2 and 3 — what they would take

The README sketches a pgvector layer and a Kubernetes layer. **Neither exists in this repo.** Stated
plainly so nobody plans against them:

| Layer | Status | What it would actually buy |
|---|---|---|
| **1 — SQLite + numpy matrix** | ✅ **shipped** | Everything below, for one user, at 20–30 ms |
| **2 — pgvector (Docker)** | ❌ not built | Concurrent readers and incremental upserts. Not speed — a mmap'd matmul already beats a network round-trip at this scale |
| **3 — Kubernetes (CloudNativePG, Argo Workflows)** | ❌ not built | Scheduled re-embedding and multi-user serving |

Be honest about the motivation. At ~41,000 chunks, Layer 1 answers in **20–30 ms**, which is faster
than any networked database will manage. Layer 2 is not a performance upgrade; it is a
*concurrency and incrementality* upgrade. Layer 3 is infrastructure for a demo or a multi-user
service, not for one person searching their notes.

**The thing that would most improve daily use is not a new layer — it is incremental indexing**, so
the index is current instead of nightly. That is a change to `embed_chunks.py`, not a deployment.

---

## Troubleshooting a deployment

| Symptom | Likely cause |
|---|---|
| Search returns nothing, no error | Index never built, or built for a different `SECOND_BRAIN_DB`. Run `embed_chunks.py --stats` |
| `Vector matrix : MISSING` | `chunks` rows exist but the `.npy` is gone — rebuild |
| Results feel stale | Both build stages need re-running; see *Keeping it fresh* |
| Scores all look low on a new vault | Expected. Small corpora compress scores — see [[docs/verifying-a-fresh-install]] |
| Embedding fails per chunk | Ollama is not running, or the model is not pulled (`ollama list`) |
| Hook produces no context and no error | By design — it fails open so it can never block a prompt. Test it directly: `echo '{"prompt":"..."}' \| python3 hook.py` |

---

## Related

- [[docs/verifying-a-fresh-install]] — the smoke test to run after any deployment
- [[docs/adopting-into-an-existing-vault]] — bringing OrionOs to a vault you already have
- [[docs/claude-code-setup]] — hook and MCP registration
- [[03-Resources/tools/second-brain/README]] — architecture and integration modes
