# Building

## Building from Source

You can build standalone executables using PyInstaller. This creates a single binary file that includes all dependencies.

Requirements:

- Python 3.11-3.14
- PyInstaller 6.20.0+
- Dependencies from `requirements.txt` and `requirements/db.txt`

## Quick Build

```sh
pip install -r requirements.txt -r requirements/db.txt
pip install pyinstaller==6.20.0
pyinstaller pyinstaller/dirsearch.spec
./dist/dirsearch --version
```

## Manual Build on Linux or macOS

```sh
pyinstaller \
  --onefile \
  --name dirsearch \
  --paths=. \
  --collect-submodules=lib \
  --add-data "db:db" \
  --add-data "config.ini:." \
  --add-data "lib/report:lib/report" \
  --hidden-import=requests \
  --hidden-import=httpx \
  --hidden-import=urllib3 \
  --hidden-import=jinja2 \
  --hidden-import=colorama \
  --strip \
  --clean \
  dirsearch.py
```

## Manual Build on Windows

```powershell
pyinstaller `
  --onefile `
  --name dirsearch `
  --paths=. `
  --collect-submodules=lib `
  --add-data "db;db" `
  --add-data "config.ini;." `
  --add-data "lib/report;lib/report" `
  --hidden-import=requests `
  --hidden-import=httpx `
  --hidden-import=urllib3 `
  --hidden-import=jinja2 `
  --hidden-import=colorama `
  --clean `
  dirsearch.py
```

Windows uses `;` instead of `:` as the path separator in `--add-data`.

## Build Output

- Linux/macOS: `dist/dirsearch`
- Windows: `dist/dirsearch.exe`

The binary includes:

- All Python dependencies
- `db/` directory with wordlists and blacklists
- `config.ini` default configuration
- `lib/report/` Jinja2 templates for reports

## GitHub Workflows

dirsearch uses GitHub Actions for continuous integration and automated builds.

| Workflow | Trigger | Description |
|----------|---------|-------------|
| Inspection (CI) | Push, PR | Runs tests, linting, and codespell on Python 3.11/3.14 across Ubuntu and Windows |
| PyInstaller Linux | Manual, Workflow call | Builds `dirsearch-linux-amd64` binary |
| PyInstaller Windows | Manual, Workflow call | Builds `dirsearch-windows-x64.exe` binary |
| PyInstaller macOS Intel | Manual, Workflow call | Builds `dirsearch-macos-intel` binary |
| PyInstaller macOS Silicon | Manual, Workflow call | Builds `dirsearch-macos-silicon` binary |
| PyInstaller Draft Release | Manual | Builds all platforms and creates a draft GitHub release |
| Docker Image | Push, PR | Builds and tests Docker image |
| CodeQL Analysis | Push, PR, Schedule | Security scanning with GitHub CodeQL |
| Semgrep Analysis | Push, PR | Static analysis with Semgrep |

## Running Workflows Manually

PyInstaller builds can be triggered manually from the GitHub Actions tab:

1. Go to Actions and select a workflow, such as PyInstaller Linux.
2. Click Run workflow.
3. Download artifacts from the completed run.

## Creating a Release

To create a release with all platform binaries:

1. Go to Actions > PyInstaller Draft Release.
2. Click Run workflow.
3. Enter the tag, such as `v5.0.0`.
4. Select the target branch.
5. Optionally mark it as a prerelease.
6. Review and publish the draft release.

## Build Matrix

The CI workflow tests on:

- Python versions: 3.11, 3.14
- Operating systems: Ubuntu latest and Windows latest
