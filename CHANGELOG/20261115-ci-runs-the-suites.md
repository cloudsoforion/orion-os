---
created: "20261115"
updated: "20261115"
tags:
  - created/20261115
  - updated/20261115
  - type/changelog
  - domain/knowledge-management
  - status/done
status: done
author: Claude (claude-fable-5-1)
---

# 2026-11-15 — CI runs the suites

Until today the 410 tests ran only on the author's machine. `.github/workflows/tests.yml` now runs every tool's suite on each push to `main` and on every pull request, on Python 3.10 and 3.12.

## What changed

- **One workflow, eight suites.** The job loops over the tool directories and runs `python3 -m pytest tests/` in each, the same way [[03-Resources/tools/CONTRIBUTING]] § Tests says to run them by hand. It keeps going after a failure so one red suite does not hide another, then fails at the end.
- **Installs only what the suites import:** pytest, PyYAML (process_frontmatter), numpy and mcp (second-brain). No Ollama, no network, per the suites' own rule.
- **A new tool is added to the list in the workflow.** Noted in CONTRIBUTING § Tests and in the tools index.
- README carries the badge.

## Why now

The repo flips public this week and may become a template. Workflow files are copied into every repository generated from a template, so anyone who uses it gets the same check on day one. Before this, nothing ran on a pull request, which the author had assumed was not the case.
