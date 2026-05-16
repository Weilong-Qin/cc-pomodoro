# Backend Development Guidelines

> Best practices for backend development in this project.

---

## Overview

This directory contains guidelines for backend development. Fill in each file with your project's specific conventions.

---

## Guidelines Index

| Guide | Description | Status |
|-------|-------------|--------|
| [Quality Guidelines](./quality-guidelines.md) | Design decisions, required/forbidden patterns, testing | ✅ Filled |
| [Error Handling](./error-handling.md) | Error patterns, common mistakes, edge case matrix | ✅ Filled |
| [Directory Structure](./directory-structure.md) | Module organization and file layout | To fill |
| [Database Guidelines](./database-guidelines.md) | N/A — cc-pomodoro uses file storage (JSONL), no database | Skip |
| [Logging Guidelines](./logging-guidelines.md) | Structured logging, log levels | To fill |

---

## Quick Reference: cc-pomodoro Conventions

- **Zero external deps** — stdlib only. `pytest` is the sole dev dependency.
- **File-backed state** — no HTTP daemon. `state.json` is the single source of truth.
- **Atomic writes** — write-to-tmp-then-rename for all file writes.
- **Hook scripts as thin shells** — 2-3 lines, all logic in `hooks.py`.
- **Safe defaults on failure** — hook crash = pass-through (don't block the user).
- **Config: define → implement → document** — all three in one commit.
- **`.sh` + `.bat` for every hook script** — Windows and POSIX both needed.
