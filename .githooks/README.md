---
created: "20260725"
updated: "20260725"
tags:
  - created/20260725
  - updated/20260725
  - type/readme
  - domain/tooling
  - status/active
status: active
---

# git-hooks

Global git hooks wired up via `core.hooksPath` in `~/.gitconfig`.

## pre-commit

Detects staged files that exceed a size threshold, adds them to the local repo's `.gitignore` (anchored to the repo root), stages that change, and unstages the large file. The commit proceeds without the offending file.

### Configuration

| Setting | Default | Description |
|---|---|---|
| `hooks.largeFileThreshold` | `10485760` (10MB) | Max allowed staged file size in bytes |

Override per-repo:

```sh
git config hooks.largeFileThreshold 5242880   # 5MB
git config hooks.largeFileThreshold 52428800  # 50MB
```

### Per-repo hooks

This global hook chains to `.git/hooks/pre-commit.local` if it exists and is executable, so per-repo pre-commit logic still works.

### Installation

Already active — `~/.gitconfig` has `core.hooksPath` pointing here. To verify:

```sh
git config --global core.hooksPath
```
