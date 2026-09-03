# clean-dns

A command-line tool for managing BIND9 DNS zone files.  It removes
duplicate records, sorts records into a predictable order, and can add or
remove records from a YAML file.  Every modification atomically replaces
the zone file (with a timestamped backup) and increments the SOA serial.

## Features

- **Deduplication** — removes duplicate records within a zone
- **Sorting** — alphabetical for A/AAAA/CNAME/NS/TXT, numeric for PTR, priority-then-exchange for MX
- **Add records** — append new records from a YAML file; zone files are discovered automatically via `named-checkconf`
- **Remove records** — delete specific records from a YAML file using the same format as add
- **Dry-run** — preview what would change without writing anything
- **Change summary** — always printed, whether or not changes are applied
- **BIND reload** — optionally trigger `rndc reload` after a successful write

Supported record types: **A, AAAA, CNAME, MX, NS, PTR, TXT**.

## Requirements

- Python ≥ 3.14 (the version shipped as `python3` on Ubuntu 26.04)
- [dnspython](https://www.dnspython.org/) ≥ 2.0
- [PyYAML](https://pyyaml.org/) ≥ 6.0
- BIND9 (`named-checkconf`) must be on PATH when using `--add-from` or `--remove-from`
- BIND9 (`rndc`) must be on PATH when using `--reload`

For Python 3.8 through 3.13, use the `python-3.8-compat` branch instead.

## Installation

On Ubuntu, install the venv module first — it is not part of the base
Python package:

```bash
sudo apt install python3.14-venv
```

A virtual environment is **required**, not merely recommended: Ubuntu marks
its system Python as externally managed (PEP 668), so `pip install` outside
a venv is refused.  Note also that Ubuntu ships no unversioned `python`
binary; use `python3`.

### Standard installation (internet-connected)

```bash
python3 -m venv venv
source venv/bin/activate
pip install --editable .
```

### Air-gapped installation (offline environments)

The `vendor/` directory contains pre-downloaded wheel files for all Python dependencies, allowing installation without internet access.

**Prerequisites:**
- Python 3.14 installed on the system
- The entire project directory (including `vendor/`) copied to the air-gapped system
- The filesystem the project lives in doesn't have `noexec`

**Installation steps:**

```bash
# Create a virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install all dependencies from the vendor directory
pip install --no-index --find-links vendor -e .
```

**Regenerating `vendor/`:**

Three wheels are the irreducible minimum for the command above to work:

| Wheel | Why it is needed |
|---|---|
| `dnspython` | runtime dependency |
| `PyYAML` | runtime dependency |
| `setuptools` | **build** dependency — `pip install -e .` builds the package in an isolated environment, which resolves `build-system.requires` from `vendor/` too |

`setuptools` is easy to miss because nothing imports it at runtime. Omitting
it fails the install before either runtime dependency is even considered
(see Troubleshooting).

Run this on an internet-connected machine; the full set including the test,
type-check, and binary-build tooling is:

```bash
pip download --dest vendor --only-binary=:all: \
  "dnspython>=2.0" "PyYAML>=6.0" "setuptools>=61" \
  "pytest>=7.0" "pyright>=1.1" "pyinstaller>=6.16"
```

Drop the second line's three arguments for a runtime-only deployment.
`--only-binary=:all:` matters: without it pip may fetch a source archive that
then needs a compiler on the offline machine.

Copy the resulting directory to the air-gapped system and follow the
installation steps above. `requirements.lock` records the exact versions the
checked-in directory was generated from.

**Platform compatibility:**

The vendored wheels target **Python 3.14 on Linux x86_64**. Most are
pure-Python and portable, but PyYAML ships a compiled extension and is
therefore tied to both the interpreter ABI (`cp314`) and the platform — it
alone determines whether `vendor/` is usable.

The command above infers those tags from the machine it runs on, so prefer to
run it on a host matching the target. When that is not possible, state the
target explicitly:

```bash
pip download --dest vendor --only-binary=:all: \
  --python-version 3.14 --platform manylinux2014_x86_64 --abi cp314 \
  "dnspython>=2.0" "PyYAML>=6.0" "setuptools>=61"
```

**Troubleshooting:**

`ERROR: Could not find a version that satisfies the requirement setuptools>=61`
(reported under `installing build dependencies did not run successfully`) means
`vendor/` has no `setuptools` wheel. Add one — see the table above.

`ERROR: Could not find a version that satisfies the requirement PyYAML (from
versions: none)` means the vendored PyYAML wheel does not match the running
interpreter. Check that:
- The Python version matches (the vendored wheels are for Python 3.14; the
  wheel filename must read `cp314`)
- The platform matches (Linux x86_64)
- All required `.whl` files are present in the `vendor/` directory

Note that `pyright` is not usable offline even when vendored: it downloads a
Node runtime on first run. The test suite (`pytest`) has no such limitation.

## Building a standalone binary

`clean-dns.spec` builds a single self-contained executable that needs no
Python installation on the target host:

```bash
pip install --editable ".[build]"
pyinstaller clean-dns.spec
./dist/clean-dns --help
```

The binary embeds the interpreter it was built with, so build it on a host
running the same Python version and architecture as the deployment target.

## Usage

### Process existing zone files

```bash
cleandns --files /etc/bind/example.com.zone /etc/bind/other.net.zone
```

Reads each file, removes duplicates, sorts records, and writes the result
back.  The original is backed up with a timestamped name before replacement
(e.g. `example.com.zone.2024-06-01_14-30-00-123456`).

### Add records from a YAML file

```bash
cleandns --add-from records.yaml
```

Zone files are discovered automatically by running `named-checkconf -p`.
Only `master`/`primary` zones are considered.

### Remove records from a YAML file

```bash
cleandns --remove-from records.yaml
```

Uses the same YAML formats as `--add-from`.  Zone files are discovered via
`named-checkconf -p`.  Records are matched by **type, name, and rdata**
(TTL is ignored).  A record listed in the YAML that does not exist in the
zone produces a warning but does not cause the command to fail, so the
operation is safe to run more than once.

### Preview changes without writing

```bash
cleandns --dry-run --files /etc/bind/example.com.zone
cleandns --dry-run --add-from records.yaml
cleandns --dry-run --remove-from records.yaml
```

Prints a change summary prefixed with `[DRY RUN]` and exits without
modifying any file or creating any backup.

### Reload BIND after saving

```bash
cleandns --reload --files /etc/bind/example.com.zone
cleandns --reload --add-from records.yaml
cleandns --reload --remove-from records.yaml
```

Runs `rndc reload <zone>` after each zone file is successfully written.
BIND is **not** reloaded by default — use this flag only when you are
confident the changes are correct.  Has no effect with `--dry-run`.

## CLI reference

| Flag | Default | Description |
|------|---------|-------------|
| `-f` / `--files FILE …` | — | One or more zone files to process |
| `--add-from YAML` | — | YAML file with records to add (mutually exclusive with `--files` and `--remove-from`) |
| `--remove-from YAML` | — | YAML file with records to remove (mutually exclusive with `--files` and `--add-from`) |
| `--dry-run` | off | Show what would change without writing |
| `--reload` | off | Run `rndc reload` after each successful write |
| `--backup-dir DIR` | `backups/` next to each zone file | Directory where timestamped backups are stored |
| `--no-backup` | off | Disable backup creation entirely |
| `--omit-origin` | off | Do not write the `$ORIGIN` directive |
| `--omit-ttl` | off | Do not write the `$TTL` directive |
| `--omit-record-ttl` | off | Omit the per-record TTL column |
| `--human-readable` | off | Format SOA timing fields as `1h30m` instead of raw seconds |

Mutually exclusive pairs: `--omit-ttl` / `--omit-record-ttl`, `--backup-dir` / `--no-backup`.

## YAML formats

Two formats are accepted; the format is auto-detected.

### Standard format

The top-level key is the zone name.  Each entry requires `type`, `name`,
and `rdata`; `ttl` is optional (defaults to 3600 when omitted).

```yaml
example.com:
  - type: A
    name: webserver
    ttl: 3600
    rdata: 192.168.1.10

  - type: AAAA
    name: webserver
    ttl: 3600
    rdata: 2001:db8::1

  - type: MX
    name: "@"
    ttl: 3600
    rdata: "10 mail.example.com."

  - type: TXT
    name: "@"
    ttl: 3600
    rdata: '"v=spf1 include:example.com ~all"'

other.net:
  - type: CNAME
    name: www
    rdata: webserver   # ttl omitted — falls back to 3600
```

Multiple zones can appear in a single file.

### dnsEntries format (A records only)

A shorthand format that maps IP addresses to FQDNs.  The zone is derived
from the FQDN using longest-suffix matching against the zones known to
`named-checkconf`.

```yaml
dnsEntries:
  - ip: 192.168.1.10
    fqdn: webserver.example.com
  - ip: 192.168.1.20
    fqdn: mail.example.com
  - ip: 10.0.0.5
    fqdn: api.sub.example.com   # zone resolved as sub.example.com if known,
                                 # otherwise example.com with name api.sub
```

## Known limitations

| Limitation | Details |
|------------|---------|
| **Comments are not preserved** | dnspython discards comments when parsing. Every file that is rewritten will lose any inline comments. |
| **Unsupported record types block processing** | A zone file containing types not in the supported list (e.g. SRV, CAA, SSHFP) will be rejected entirely. |
| **Backup files accumulate** | There is no automatic cleanup of timestamped backup files within the backup directory. |
| **Default TTL mismatch on add** | When using `--add-from` and a record in the YAML omits its `ttl`, the fallback is 3600 — regardless of the zone file's own `$TTL` directive.  This does not affect `--remove-from` because TTL is ignored during matching. |
| **No serial overflow guard** | The SOA serial is incremented by 1 with no check for the 32-bit unsigned maximum (4 294 967 295). |

## Running the tests

```bash
source venv/bin/activate
pip install --editable ".[dev]"
pytest
```
