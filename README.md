# clean_dns

A command-line tool to process and manage DNS zone files. For each file it receives, it removes duplicate records, sorts records alphabetically (PTR records are sorted numerically), increments the SOA serial, and writes the result back — creating a timestamped backup of the original before any changes are made.

## Requirements

- Python ≥ 3.12
- pip (included with Python)

## Installation

### Standard (internet-connected)

```bash
python -m venv venv
source venv/bin/activate
pip install -e ".[dev]"
```

### Offline (air-gapped environment)

All dependencies are pre-downloaded in the `vendor/` directory and pinned in `requirements.lock`. No network access is needed after cloning.

> **Platform note:** `pyinstaller` has a platform-specific wheel. The `vendor/` directory currently contains the **Linux x86_64** build. If your target host runs a different OS or CPU architecture, regenerate the vendor directory on a machine that matches the target before transferring the repository (see [Updating dependencies](#updating-dependencies)).

```bash
python -m venv venv
source venv/bin/activate
pip install --no-index --find-links=vendor/ -e ".[dev,build]"
```

## Usage

```
cleandns -f <file> [<file> ...]
```

| Flag | Description |
|------|-------------|
| `-f`, `--files` | One or more zone files to process (required) |
| `--omit-ttl` | Omit the `$TTL` directive from the output |
| `--omit-record-ttl` | Omit the TTL column from individual records |
| `--omit-origin` | Omit the `$ORIGIN` directive from the output |
| `--human-readable` | Format TTL and SOA timing values as `1h30m` instead of raw seconds |

`--omit-ttl` and `--omit-record-ttl` are mutually exclusive.

**Examples**

```bash
cleandns -f example.com.zone
cleandns -f zone1.dns zone2.dns --human-readable
cleandns -f zone.dns --omit-ttl
cleandns -f zone.dns --omit-record-ttl
cleandns -f zone.dns --omit-origin
```

## Building a standalone binary

PyInstaller bundles the project and all its dependencies into a single executable that requires no Python installation on the target machine. The `clean-dns.spec` file at the root of the repository contains the build configuration.

`pyinstaller` is included in the `.[build]` optional dependency group and is available in the `vendor/` directory.

```bash
# Ensure the build group is installed
pip install --no-index --find-links=vendor/ -e ".[dev,build]"

# Build the binary
pyinstaller clean-dns.spec
```

The executable is written to `dist/clean-dns`. It is platform-specific: a binary built on Linux will not run on macOS or Windows.

## Development

**Run tests**

```bash
pytest
```

**Type checking**

```bash
pyright
```

## Updating dependencies

When `pyproject.toml` changes (new dependency, version bump), regenerate the lock file and vendor directory on an **internet-connected machine that matches the target platform**, then commit the result.

`pip-tools` is required for this step and must be installed on the internet-connected machine:

```bash
pip install pip-tools
```

Regenerate the lock file and re-download all wheels:

```bash
pip-compile --extra=dev --extra=build --output-file=requirements.lock pyproject.toml
pip download -r requirements.lock -d vendor/
```

Commit the updated `requirements.lock` and `vendor/`:

```bash
git add requirements.lock vendor/
git commit -m "Update pinned dependencies"
```
