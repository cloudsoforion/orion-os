---
created: "20260725"
updated: "20260725"
tags:
  - created/20260725
  - updated/20260725
  - type/changelog
  - domain/tooling
  - status/active
status: active
---

# Changelog

## 2026-04-23

### Added
- `pre-commit`: auto-adds staged files exceeding a size threshold to the local repo's `.gitignore`, stages the change, and unstages the large file so the commit can proceed cleanly
  - Default threshold: 10MB (configurable per-repo via `git config hooks.largeFileThreshold`)
  - Chains to `.git/hooks/pre-commit.local` for per-repo hook compatibility
