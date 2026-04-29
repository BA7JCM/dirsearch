# v5.0.0 Release TODO

## Current Status

Phase 1 is implemented for optional database dependencies. The codebase can now import the CLI entry module, session store, report manager, and non-database reports without `mysql-connector-python` or `psycopg[binary]` installed.

This is a useful foundation for a future MCP server or REST API because import-time side effects are lower and base installs no longer require database drivers. It is not yet a full supported API surface; that starts in Phase 3 with the importable agent API.

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

## Verification Run

- `/home/mauro/dirsearch/.venv/bin/python -m unittest tests.test_optional_db_dependencies tests.controller.test_session_store`
- `/home/mauro/dirsearch/.venv/bin/python -m unittest tests.connection.test_requester tests.connection.test_dns tests.core.test_scanner tests.test_optional_db_dependencies tests.controller.test_session_store`
- `/home/mauro/dirsearch/.venv/bin/python testing.py`
- `/home/mauro/dirsearch/.venv/bin/python -m pip wheel . --no-deps --no-build-isolation -w /tmp/dirsearch-wheel`
- `docker build -t dirsearch:optional-db-test .`
- `docker run --rm --entrypoint python3 dirsearch:optional-db-test -m unittest tests.test_optional_db_dependencies tests.controller.test_session_store`
- `docker run --rm --entrypoint python3 dirsearch:optional-db-test -c "import importlib.util; print(importlib.util.find_spec('mysql')); print(importlib.util.find_spec('psycopg'))"`

## Next Phase

### Phase 2: Python 3.14 Release Base

- Update package version to `5.0.0`.
- Update Python metadata and classifiers.
- Update Docker base image and supported Python version docs.
- Update CI matrix, PyInstaller workflow, Nuitka workflow, and release docs.
- Review dependency pins for Python 3.14-compatible current versions.
- Run release-base validation:
  - Docker build with Python 3.14.
  - `python3 testing.py`.
  - CLI smoke test.
  - packaged install smoke test.

### Phase 3: Importable Agent API

- Add public imports for:
  - `FuzzerConfig`
  - `DirsearchFuzzer`
  - `FuzzerResult`
  - `Wordlist`
  - `WordlistTemplate`
  - `WordlistState`
- Remove supported API dependence on caller-mutated global options.
- Add local script-style tests that import dirsearch, build template dictionaries, run a fuzzer, and receive structured results/callbacks.
- Add an isolation test proving two fuzzer configs do not leak state in one process.

### Later Phases

- Template wordlists and generation limits.
- Native wordlist backend with Python/native parity tests.
- Opt-in large dictionary performance benchmark.
- Final Docker release gate for base install, DB extras, Python backend, native backend, smoke tests, and importable API tests.
