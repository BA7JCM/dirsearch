# dirsearch native PoC

This crate is an experimental Phase 5 native backend. It is not part of the
default Python package build yet.

It exposes two PyO3 functions:

- `generate_wordlist(...)` for deterministic ordered wordlist generation.
- `scan_http(...)` for a batch HTTP GET PoC using `reqwest` and `tokio`.

Build locally with a Rust toolchain and maturin:

```sh
python3 -m pip install maturin
python3 -m maturin develop --manifest-path native/Cargo.toml
```

Then compare native and Python paths:

```sh
python3 scripts/benchmark_phase5.py --include-native --json
```
