# Installation

## Supported Platforms

dirsearch runs on multiple platforms and can be used either via Python or standalone binaries.

| Platform | Python | Standalone Binary |
|----------|--------|-------------------|
| Linux (x86_64) | Python 3.11-3.14 | `dirsearch-linux-amd64` |
| Windows (x64) | Python 3.11-3.14 | `dirsearch-windows-x64.exe` |
| macOS (Intel) | Python 3.11-3.14 | `dirsearch-macos-intel` |
| macOS (Apple Silicon) | Python 3.11-3.14 | `dirsearch-macos-silicon` |

Standalone binaries are self-contained executables that do not require a Python installation.

## Install from Source

Requirement: Python 3.11 or higher.

```sh
git clone https://github.com/maurosoria/dirsearch.git --depth 1
cd dirsearch
python3 dirsearch.py -u https://example.com -w tests/static/wordlist.txt -q
```

## Other Install Methods

- ZIP archive: [Download the master branch](https://github.com/maurosoria/dirsearch/archive/master.zip).
- PyPI: `pip3 install dirsearch` or `pip install dirsearch`.
- Docker: `docker build -t "dirsearch:v5.0.0" .`.
- Kali Linux: `sudo apt-get install dirsearch` (deprecated).

## Standalone Binaries

Pre-built standalone binaries are available for all major platforms. Download them from [Releases](https://github.com/maurosoria/dirsearch/releases).

| Platform | Binary Name | Architecture |
|----------|-------------|--------------|
| Linux | `dirsearch-linux-amd64` | x86_64 |
| Windows | `dirsearch-windows-x64.exe` | x64 |
| macOS Intel | `dirsearch-macos-intel` | x86_64 |
| macOS Apple Silicon | `dirsearch-macos-silicon` | ARM64 |

Linux and macOS usage:

```sh
chmod +x dirsearch-linux-amd64
./dirsearch-linux-amd64 -u https://target
```

Windows usage:

```sh
dirsearch-windows-x64.exe -u https://target
```

Standalone binaries include bundled `db/` wordlists and `config.ini`. Session files are stored in `$HOME/.dirsearch/sessions/` when using bundled builds.

## Docker

Install Docker on Linux:

```sh
curl -fsSL https://get.docker.com | bash
```

Docker may require superuser permissions.

Build the image:

```sh
docker build -t "dirsearch:v5.0.0" .
```

Run dirsearch from the image:

```sh
docker run -it --rm "dirsearch:v5.0.0" -u target -e php,html,js,zip
```
