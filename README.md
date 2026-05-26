# clean-dns

A command-line tool for managing BIND9 DNS zone files.  It removes
duplicate records, sorts records into a predictable order, and can add
new records from a YAML file.  Every modification atomically replaces the
zone file (with a timestamped backup) and increments the SOA serial.

## Features

- **Deduplication** — removes duplicate records within a zone
- **Sorting** — alphabetical for A/AAAA/CNAME/NS/TXT, numeric for PTR, priority-then-exchange for MX
- **Add records** — append new records from a YAML file; zone files are discovered automatically via `named-checkconf`
- **Dry-run** — preview what would change without writing anything
- **Change summary** — always printed, whether or not changes are applied
- **BIND reload** — optionally trigger `rndc reload` after a successful write

Supported record types: **A, AAAA, CNAME, MX, NS, PTR, TXT**.

## Requirements

- Python ≥ 3.12
- [dnspython](https://www.dnspython.org/) ≥ 2.0
- [PyYAML](https://pyyaml.org/) ≥ 6.0
- BIND9 (`named-checkconf`) must be on PATH when using `--add-from`
- BIND9 (`rndc`) must be on PATH when using `--reload`

## Installation

```bash
python -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install --editable .
```

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

### Preview changes without writing

```bash
cleandns --dry-run --files /etc/bind/example.com.zone
cleandns --dry-run --add-from records.yaml
```

Prints a change summary prefixed with `[DRY RUN]` and exits without
modifying any file or creating any backup.

### Reload BIND after saving

```bash
cleandns --reload --files /etc/bind/example.com.zone
cleandns --reload --add-from records.yaml
```

Runs `rndc reload <zone>` after each zone file is successfully written.
BIND is **not** reloaded by default — use this flag only when you are
confident the changes are correct.  Has no effect with `--dry-run`.

## CLI reference

| Flag | Default | Description |
|------|---------|-------------|
| `-f` / `--files FILE …` | — | One or more zone files to process |
| `--add-from YAML` | — | YAML file with records to add (mutually exclusive with `--files`) |
| `--dry-run` | off | Show what would change without writing |
| `--reload` | off | Run `rndc reload` after each successful write |
| `--omit-origin` | off | Do not write the `$ORIGIN` directive |
| `--omit-ttl` | off | Do not write the `$TTL` directive |
| `--omit-record-ttl` | off | Omit the per-record TTL column |
| `--human-readable` | off | Format SOA timing fields as `1h30m` instead of raw seconds |

`--omit-ttl` and `--omit-record-ttl` are mutually exclusive.

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
| **Backup files accumulate** | There is no automatic cleanup of timestamped backup files. |
| **Default TTL mismatch on add** | When using `--add-from` and a record in the YAML omits its `ttl`, the fallback is 3600 — regardless of the zone file's own `$TTL` directive. |
| **No serial overflow guard** | The SOA serial is incremented by 1 with no check for the 32-bit unsigned maximum (4 294 967 295). |

## Running the tests

```bash
source venv/bin/activate
pytest
```
