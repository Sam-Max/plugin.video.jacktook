# AGENTS.md

Guidance for agentic coding assistants working in `plugin.video.jacktook`.

## 1) Project Context

- Project type: Kodi video addon (`plugin.video.jacktook`)
- Main language: Python
- Runtime target: Kodi Python runtime (`xbmc.python` 3.00.0 in `addon.xml`)
- Practical local interpreter: `python3` (the `python` command is not available here)
- Primary entry points:
  - `jacktook.py` (plugin source entry)
  - `service.py` (background service entry)

## 2) Repository Structure (high-value paths)

- `lib/` core addon code
  - `lib/router.py` action dispatcher with lazy imports
  - `lib/navigation.py` menu/actions wiring
  - `lib/clients/` integrations (Jackett, Stremio, debrid providers, etc.)
  - `lib/api/` API wrappers
  - `lib/utils/` utility functions, Kodi helpers, parsing, playback helpers
  - `lib/gui/` Kodi windows/dialogs
  - `lib/domain/` domain models (example: `TorrentStream`)
- `resources/` settings XML, localization strings, skins, artwork
- `tests/` pytest tests + manual scripts
- `scripts/` utility scripts (release packaging, label conversion, py37 compatibility)

## 3) Cursor/Copilot Rules

- Checked for Cursor rules:
  - `.cursor/rules/` -> not present
  - `.cursorrules` -> not present
- Checked for GitHub Copilot instructions:
  - `.github/copilot-instructions.md` -> not present
- Therefore: no repository-specific Cursor/Copilot rule files are currently defined.

## 4) Setup Commands

Use `python3` commands from repo root.

```bash
python3 -m pip install -r requirements-test.txt
```

Optional editable-style convenience for local imports is not required because tests already adjust `sys.path` in `tests/conftest.py`.

## 5) Build / Package Commands

There is no traditional compile/build pipeline. Packaging is done via script:

```bash
python3 scripts/create_release.py
```

Notes:
- `scripts/create_release.py` uses hard-coded absolute paths for source and destination.
- It creates a zip artifact under `/home/spider/Desktop/jacktook/releases/plugin.video.jacktook.zip`.
- It excludes `.git`, `.venv`, `.agent`, `.worktrees`, `__pycache__`, `.pytest_cache`, and `*.pyc`.

## 6) Test Commands

Run tests from repository root.

### Run full suite

```bash
python3 -m pytest -q
```

### Run a single file

```bash
python3 -m pytest tests/unit/test_jackett.py -q
```

### Run a single test (node id)

```bash
python3 -m pytest tests/unit/test_general_utils.py::test_is_url -q
```

### Run tests by keyword expression

```bash
python3 -m pytest -k "jackett and search_movie" tests/unit -q
```

### Run with coverage

```bash
python3 -m pytest --cov=lib --cov-report=term-missing
```

### Collect-only (debug discovery)

```bash
python3 -m pytest --collect-only -q
```

### Manual/integration helper scripts

```bash
python3 tests/manual_easynews_test.py
python3 tests/verify_debrid.py
```

Notes:
- These manual scripts require credentials/tokens and are not CI-safe.
- Kodi modules are mocked in tests via `tests/conftest.py` and per-test stubs.

## 7) Lint / Static Checks

No dedicated linter config (`pyproject.toml`, `setup.cfg`, `tox.ini`, `pytest.ini`) is present.

Recommended lightweight checks:

```bash
python3 -m py_compile jacktook.py service.py
python3 scripts/check_py37_compat.py .
```

`scripts/check_py37_compat.py` scans for syntax/features that break Python 3.7 compatibility assumptions.

## 8) Known Test Environment Caveats

- In this environment, `python3 -m pytest -q` currently has one failing test:
  - `tests/unit/test_general_utils.py::test_supported_video_extensions`
- Root cause is environment/mocking behavior of `xbmc.getSupportedMedia` (returns empty without specific mock setup).
- If touching video extension logic, ensure deterministic mocking of `getSupportedMedia`.

## 9) Code Style Guidelines

Follow existing codebase conventions first; avoid style-only churn.

### Imports

- Prefer grouped imports in this order:
  1. Standard library
  2. Third-party
  3. Local `lib.*`
  4. Kodi modules (`xbmc`, `xbmcgui`, `xbmcplugin`, etc.)
- Keep import names explicit; avoid wildcard imports.
- Lazy-import heavy modules inside functions when startup cost matters (see `lib/router.py`).

### Formatting

- 4-space indentation, no tabs.
- Keep functions focused; extract helpers for repeated routing/action maps.
- Preserve readability over strict line-length refactors (project has mixed line widths).
- Avoid large reformat-only diffs.

### Types and Data Modeling

- Type hints are used but not universally enforced; add hints for new/edited public helpers when practical.
- Use `typing` compatibility style seen in repo (`List`, `Dict`, `Optional`) for consistency.
- Preserve existing payload field names where external APIs demand them (e.g., `infoHash`, `isPack`).
- Use dataclasses for small structured models (see `lib/domain/torrent.py`).

### Naming

- Functions/variables: `snake_case`
- Classes: `PascalCase`
- Constants: `UPPER_SNAKE_CASE`
- Keep compatibility with existing action names and query params used by router/navigation.

### Error Handling and Logging

- Fail gracefully in UI/user-facing paths; avoid crashing Kodi navigation.
- Wrap network/IO boundaries with defensive error handling.
- Use Kodi-friendly messaging/logging patterns:
  - `notification(...)` for user-visible failures
  - `kodilog(...)` for diagnostics
- Prefer specific exceptions when practical; broad `except` is tolerated only where Kodi API instability requires resilience.

### Kodi-Specific Practices

- Respect addon flow: build list items, set content type/category, then close directory correctly.
- Use utility wrappers in `lib.utils.kodi.utils` instead of duplicating Kodi API calls.
- Be careful with module-level side effects due to Kodi imports; tests rely on pre-import mocks.

### Testing Practices

- For pure logic, add/extend pytest unit tests in `tests/unit/`.
- Mock Kodi modules before importing code under test when required.
- Prefer deterministic fixtures over live network calls.
- For debrid/provider behavior, keep unit tests isolated and use manual scripts for credentialed checks.

## 10) Change Workflow for Agents

- Make minimal, targeted changes.
- Do not rewrite unrelated files for style consistency.
- When changing routing/action names, update all call sites and query param builders.
- Run relevant tests first (single-test command), then broader suite when feasible.
- If tests fail due to known environment stubs, document clearly in your handoff.
