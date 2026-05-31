# Installation

## Supported Platforms

dirsearch runs on Python 3.11-3.14 and is distributed as source, installable from GitHub with pip, Docker image, PyInstaller binary, or portable folder. Release-equivalent native builds use Python 3.14.

| Platform | Architecture | PyInstaller | Portable folder |
|----------|--------------|-------------|-----------------|
| Windows | x64 | Yes | Yes |
| Linux | x64 | Yes | Yes |
| Linux | ARM64 | Yes | Yes |
| macOS | Intel x86_64 | Yes | Yes |
| macOS | Apple Silicon ARM64 | Yes | Yes |

## Install from Source

Requirement: Python 3.11 or higher.

```sh
git clone https://github.com/maurosoria/dirsearch.git --depth 1
cd dirsearch
python3 dirsearch.py -u https://example.com -w tests/static/wordlist.txt -q
```

## Other Install Methods

- ZIP archive: [Download the master branch](https://github.com/maurosoria/dirsearch/archive/master.zip).
- GitHub with pip, Python stack: `pip3 install git+https://github.com/maurosoria/dirsearch.git`.
- Docker: `docker pull ghcr.io/maurosoria/dirsearch:v0.5.0-rc1-async`.
- Kali Linux: `sudo apt-get install dirsearch` (deprecated).

## Choose an Install Path

- Use release artifacts when you do not want to compile anything. Single-file PyInstaller binaries and portable archives with bundled dependencies are available for Windows x64, Linux x64, Linux ARM64, macOS Intel, and macOS Apple Silicon.
- Use `pip install git+https://github.com/maurosoria/dirsearch.git` when you want the Python stack from the current GitHub source. This does not compile the Rust native backend.
- Use the native source build steps when you want `--request-backend native` and `--wordlist-backend native` from a source checkout.
- Use the `native-rust` release artifact when you want the Rust backend without installing a Rust toolchain.

## Platform Setup

### Ubuntu and Debian, amd64 or arm64

Install prerequisites for the Python stack:

```sh
sudo apt-get update
sudo apt-get install -y git ca-certificates python3 python3-venv python3-pip
python3 -m venv ~/.venvs/dirsearch
. ~/.venvs/dirsearch/bin/activate
python -m pip install --upgrade pip
python -m pip install "git+https://github.com/maurosoria/dirsearch.git"
dirsearch --version
```

Add these packages before building the native Rust backend:

```sh
sudo apt-get install -y build-essential curl python3-dev
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --profile minimal
. "$HOME/.cargo/env"
```

Use Linux `x64` release assets on amd64 and Linux `arm64` release assets on ARM64/aarch64.

### Red Hat and Fedora, amd64 or arm64

Install prerequisites for the Python stack:

```sh
sudo dnf install -y git ca-certificates python3 python3-pip
python3 -m venv ~/.venvs/dirsearch
. ~/.venvs/dirsearch/bin/activate
python -m pip install --upgrade pip
python -m pip install "git+https://github.com/maurosoria/dirsearch.git"
dirsearch --version
```

Add these packages before building the native Rust backend:

```sh
sudo dnf install -y gcc gcc-c++ make curl python3-devel
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --profile minimal
. "$HOME/.cargo/env"
```

If your distribution splits Python by minor version, install the matching `python3.x-devel` package for the interpreter used by the virtual environment. Use Linux `x64` release assets on amd64 and Linux `arm64` release assets on ARM64/aarch64.

### macOS 26, Apple Silicon or Intel, with Homebrew

Install prerequisites for the Python stack:

```sh
brew install python git
python3 -m venv ~/.venvs/dirsearch
. ~/.venvs/dirsearch/bin/activate
python -m pip install --upgrade pip
python -m pip install "git+https://github.com/maurosoria/dirsearch.git"
dirsearch --version
```

Add these tools before building the native Rust backend:

```sh
xcode-select --install
brew install rust
```

Use macOS `silicon` release assets on Apple Silicon and macOS `intel` release assets on Intel.

### macOS 26, Apple Silicon or Intel, without Homebrew

Install Apple's command line tools, Python 3.11 or newer from python.org, and Rust from rustup:

```sh
xcode-select --install
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --profile minimal
. "$HOME/.cargo/env"
python3 -m venv ~/.venvs/dirsearch
. ~/.venvs/dirsearch/bin/activate
python -m pip install --upgrade pip
python -m pip install "git+https://github.com/maurosoria/dirsearch.git"
dirsearch --version
```

Use the same virtual environment for the native Rust build steps below.

### Windows 10 and 11, x64

For no-compile installs, download the Windows x64 PyInstaller `.exe` or portable `.zip` from the Releases page. The portable archive bundles dependencies and can be preferable when antivirus software flags PyInstaller bootloaders.

For the Python stack, install Python 3.11 or newer for x64 and Git for Windows, then run PowerShell:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install "git+https://github.com/maurosoria/dirsearch.git"
dirsearch --version
```

Before building the native Rust backend, install Microsoft C++ Build Tools with the Desktop development with C++ workload and a Windows SDK, then install Rust through rustup. If `winget` is unavailable, download and run `rustup-init.exe` from rustup.rs.

```powershell
winget install --id Rustlang.Rustup -e
rustup default stable
python -m pip install maturin
```

Open a new PowerShell session if `rustup` is not found immediately after installation.

## Native Rust from Source

The GitHub pip command installs the Python stack only. To build the Rust native request and wordlist backends from source, use Python 3.14, install Rust and `maturin`, then build the native wheel from a clone:

```sh
git clone https://github.com/maurosoria/dirsearch.git --depth 1
cd dirsearch
python3.14 -m pip install .
python3.14 -m pip install maturin
python3.14 scripts/build_native.py --out dist/native-wheels
dirsearch -u https://example.com -w tests/static/wordlist.txt --request-backend native --wordlist-backend native -q
```

On Windows PowerShell, use backslashes for local paths:

```powershell
git clone https://github.com/maurosoria/dirsearch.git --depth 1
cd dirsearch
py -3.14 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install .
python -m pip install maturin
python scripts\build_native.py --out dist\native-wheels
dirsearch -u https://example.com -w tests\static\wordlist.txt --request-backend native --wordlist-backend native -q
```

Without the native wheel, source installs keep the Python request backend and automatic Python wordlist fallback defaults.

Optional MySQL and PostgreSQL report dependencies are separate from the scanner runtime. Install them only when needed:

```sh
python -m pip install "dirsearch[db] @ git+https://github.com/maurosoria/dirsearch.git"
```

## Release Artifacts

Pre-built release assets are available on the [Releases page](https://github.com/maurosoria/dirsearch/releases).

Each platform has three stack variants:

| Variant | Default behavior |
|---------|------------------|
| `async` | Recommended Python async runtime |
| `threaded` | Legacy threaded Python runtime |
| `native-rust` | Rust request and wordlist backends |

PyInstaller examples:

```text
dirsearch-v0.5.0-rc1-linux-x64-async
dirsearch-v0.5.0-rc1-linux-arm64-native-rust
dirsearch-v0.5.0-rc1-windows-x64-threaded.exe
dirsearch-v0.5.0-rc1-macos-intel-async
dirsearch-v0.5.0-rc1-macos-silicon-native-rust
```

Portable examples:

```text
dirsearch-v0.5.0-rc1-linux-x64-async-portable.tar.gz
dirsearch-v0.5.0-rc1-windows-x64-native-rust-portable.zip
```

PyInstaller binaries are single files. Portable archives are larger, but bundle CPython and compiled dependencies and are less likely to trigger antivirus false positives caused by PyInstaller bootloader heuristics.

Linux and macOS PyInstaller usage:

```sh
chmod +x dirsearch-v0.5.0-rc1-linux-x64-async
./dirsearch-v0.5.0-rc1-linux-x64-async -u https://target
```

Windows PyInstaller usage:

```sh
dirsearch-v0.5.0-rc1-windows-x64-async.exe -u https://target
```

Portable usage:

```sh
tar -xzf dirsearch-v0.5.0-rc1-linux-x64-async-portable.tar.gz
./dirsearch-v0.5.0-rc1-linux-x64-async-portable/dirsearch -u https://target
```

On Windows, extract the `.zip` and run `dirsearch.cmd`.

## Docker

Docker images are published for Linux x64 in GitHub Container Registry:

```sh
docker pull ghcr.io/maurosoria/dirsearch:v0.5.0-rc1-async
docker run -it --rm ghcr.io/maurosoria/dirsearch:v0.5.0-rc1-async -u target -e php,html,js,zip
```

Available tags for the prerelease:

- `ghcr.io/maurosoria/dirsearch:v0.5.0-rc1-async`
- `ghcr.io/maurosoria/dirsearch:v0.5.0-rc1-threaded`
- `ghcr.io/maurosoria/dirsearch:v0.5.0-rc1-native-rust`

Build locally:

```sh
docker build --build-arg DIRSEARCH_STACK=async -t dirsearch:v0.5.0-rc1-async .
docker build --build-arg DIRSEARCH_STACK=native-rust -t dirsearch:v0.5.0-rc1-native-rust .
```
