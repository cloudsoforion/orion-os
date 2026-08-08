---
created: "<YYYYMMDD>"
updated: "<YYYYMMDD>"
tags:
  - created/<YYYYMMDD>
  - updated/<YYYYMMDD>
  - type/readme
  - domain/tooling
  - status/active
status: active
---

# <tool-name>

<Two sentences. What it does, and what it operates on.>

## How it works

- <The algorithm in 3-6 bullets. Not a feature list.>

## Commands

```bash
# <When you'd run this>
python3 <tool_name>.py --dry-run
```

## Flags

| Flag | Applies to | Meaning |
| --- | --- | --- |
| `--dry-run` | all | Preview only. **Default.** |
| `--apply` | all | Commit changes. |

## Output

<Exact path templates for anything written.>

## Tests

```bash
python3 -m pytest tests/
```

<N> tests, no network, never touches the live vault.

## Platform notes

<OS-specific behaviour, required privileges, known footguns. Delete if none.>

## First run / new machine

<Prerequisites and bootstrap steps.>

## Related

- [[03-Resources/tools/CONTRIBUTING]] — the standard
