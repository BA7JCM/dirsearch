# v5.0.0 Release TODO

## Current Status

Phase 1 is implemented for optional database dependencies. Phase 2 is implemented for the Python 3.14 / `5.0.0` release baseline. Phase 3 is implemented for the first importable Python API.

This is a useful foundation for a future MCP server or REST API because import-time side effects are lower, base installs no longer require database drivers, and the first supported Python API surface is now available. The next work expands wordlist templates and generation controls.

## Completed

- Moved MySQL/PostgreSQL drivers out of required runtime dependency files.
- Added optional dependency groups:
  - `dirsearch[mysql]`
  - `dirsearch[postgresql]`
  - `dirsearch[db]`
- Added `requirements/db.txt` for database-output installs.
- Changed report manager DB handlers to lazy-load database report modules only when DB output is selected.
- Moved DB driver imports inside the actual connection paths.
- Removed controller/session top-level references to DB driver exception classes.
- Added optional dependency regression tests in `tests/test_optional_db_dependencies.py`.
- Verified the base Docker image builds without DB drivers.
- Updated package version to `5.0.0`.
- Added Python 3.10-3.14 classifiers while keeping `requires-python = ">=3.9"`.
- Updated Docker to use `python:3.14-alpine`.
- Updated CI to test Python 3.9, 3.11, and 3.14.
- Updated PyInstaller release builds to Python 3.14 and PyInstaller 6.20.0.
- Updated Nuitka release builds to Python 3.14 and Nuitka 4.0.8.
- Updated release binary workflows/scripts to install `requirements/db.txt` so standalone builds keep DB report support.
- Updated release docs and changelog for `5.0.0`.
- Removed the Python 3.14 `SyntaxWarning` from threaded fuzzer shutdown handling.
- Updated newer verified pins:
  - `requests==2.33.1`
  - `pyopenssl==26.1.0`
  - `setuptools==82.0.1`
  - `mysql-connector-python==9.6.0`
  - `psycopg[binary]==3.3.3`
- Added public imports:
  - `FuzzerConfig`
  - `DirsearchFuzzer`
  - `FuzzerResult`
  - `Wordlist`
  - `WordlistTemplate`
  - `WordlistState`
- Added an importable API that runs from `FuzzerConfig` without caller-mutated CLI globals.
- Added structured result and callback support.
- Added template wordlist expansion for Python callers, including `%EXT%` and custom placeholders.
- Added isolation coverage proving two configs do not leak state in one process.
- Added packaged install smoke coverage for the public API imports.
- Added optional DB and importable API coverage to `testing.py`.

## Verification Run

- `/home/mauro/dirsearch/.venv/bin/python -m unittest tests.test_optional_db_dependencies tests.controller.test_session_store`
- `/home/mauro/dirsearch/.venv/bin/python -m unittest tests.connection.test_requester tests.connection.test_dns tests.core.test_scanner tests.test_optional_db_dependencies tests.controller.test_session_store`
- `/home/mauro/dirsearch/.venv/bin/python testing.py`
- `/home/mauro/dirsearch/.venv/bin/python -m pip wheel . --no-deps --no-build-isolation -w /tmp/dirsearch-wheel`
- `docker build -t dirsearch:optional-db-test .`
- `docker run --rm --entrypoint python3 dirsearch:optional-db-test -m unittest tests.test_optional_db_dependencies tests.controller.test_session_store`
- `docker run --rm --entrypoint python3 dirsearch:optional-db-test -c "import importlib.util; print(importlib.util.find_spec('mysql')); print(importlib.util.find_spec('psycopg'))"`
- `/home/mauro/dirsearch/.venv/bin/python -m py_compile lib/core/fuzzer.py lib/core/settings.py setup.py tests/test_optional_db_dependencies.py`
- `/home/mauro/dirsearch/.venv/bin/python -m unittest tests.test_optional_db_dependencies tests.controller.test_session_store tests.core.test_scanner`
- `/home/mauro/dirsearch/.venv/bin/python dirsearch.py --version`
- `/home/mauro/dirsearch/.venv/bin/python testing.py`
- `/home/mauro/dirsearch/.venv/bin/python -m pip wheel . --no-deps --no-build-isolation -w /tmp/dirsearch-wheel-v5`
- Wheel metadata inspection confirmed `Version: 5.0.0`, `Requires-Python: >=3.9`, Python 3.14 classifier, and DB extras.
- `docker build -t dirsearch:v5-release-base .`
- `docker run --rm dirsearch:v5-release-base --version`
- `docker run --rm --entrypoint python3 dirsearch:v5-release-base testing.py`
- `docker run --rm --entrypoint python3 dirsearch:v5-release-base dirsearch.py -u https://example.com -w tests/static/wordlist.txt -q`
- `docker run --rm --entrypoint sh dirsearch:v5-release-base -c "python3 -m pip install . && python3 tests/check_packaged_install.py"`
- `/home/mauro/dirsearch/.venv/bin/python -m unittest tests.core.test_importable_api`
- `/home/mauro/dirsearch/.venv/bin/python testing.py` (33 tests)
- `/home/mauro/dirsearch/.venv/bin/python tests/check_packaged_install.py`
- `docker build -t dirsearch:v5-importable-api .`
- `docker run --rm --entrypoint python3 dirsearch:v5-importable-api testing.py`
- `docker run --rm --entrypoint sh dirsearch:v5-importable-api -c "python3 -m pip install . && python3 tests/check_packaged_install.py"`

## Next Phase

### Phase 4: Template Wordlists

- Add named placeholder expansion for `%SUBJECT%`, `%CRUD_OP%`, `%AUTH_OP%`, `%ADMIN_OP%`, `%ENV%`, `%SEP%`, date tokens, DB/archive tokens, `%API_VERSION%`, and `%CATEGORY:name%`.
- Add curated template files under `db/templates/`.
- Add `--wordlist-status`.
- Add generation limits to prevent accidental huge expansions.

### Later Phases

### Phase 5: Native Wordlist Backend

- Add backend interface with Python backend first.
- Add optional native backend with `auto|python|native` selection.
- Keep native output byte-for-byte compatible with Python output for ordering and deduplication.
- Add opt-in large dictionary benchmark for generation time, iteration throughput, memory, and startup cost.

### Phase 6: Final Docker Gate

- Validate Docker base install without DB extras.
- Validate Docker install with `dirsearch[db]`.
- Run Python backend tests.
- Run native backend tests.
- Run large dictionary performance benchmark.
- Run CLI smoke tests and importable API tests.
