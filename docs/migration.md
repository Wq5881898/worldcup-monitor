# Migration Guide

This package is intended to be copied to another Windows machine and run there.

## Included

- Source code in `worldcup_monitor/`
- Tests in `tests/`
- Main docs:
  - `README.md`
  - `docs/requirements.md`
  - `docs/migration.md`
- Config files:
  - `match.json`
  - `match.local.json`
  - `summary.curl`
  - `config.example.json`
- Python dependency list:
  - `requirements.txt`

## Not Included

- `.git/`
- `logs/`
- `__pycache__/`
- Temporary HTML/debug files such as `tmp_*.html`

## Target Machine Setup

Recommended Python version:

- Python 3.11 or 3.13 on Windows

Install dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Run

Use the current local config:

```powershell
.\.venv\Scripts\python.exe -m worldcup_monitor run --config match.local.json
```

Or use system Python:

```powershell
python -m worldcup_monitor run --config match.local.json
```

## Before Running

Check these files on the new machine:

- `match.local.json`
- `summary.curl`

If the match changes, replace the `summary.curl` content or regenerate it from a known FlashScore match page.

## Notes

- `match.local.json` may contain real Telegram credentials.
- Keep this package private if those credentials should not be exposed.
