# Test files

These files let you exercise the tool against realistic zone data
without touching a live BIND9 installation.

---

## Zone files

### `example.com.zone` — forward zone

A realistic `192.168.1.0/24` network with the following intentional
issues for the tool to fix:

| Record type | Issue | Expected result |
|-------------|-------|-----------------|
| A (11 records) | Unsorted | api → app → db → ftp → mail1 → mail2 → mail3 → ns1 → ns2 → web → www |
| AAAA (3 records) | Unsorted | mail1 → ns1 → www |
| CNAME (4 records) | Unsorted | imap → pop → smtp → webmail |
| MX (3 records) | Priorities in order 30/10/20 | 10 → 20 → 30 |

> **Note on duplicate detection:** BIND and dnspython both treat zone
> files as sets — identical records in the raw file are merged
> automatically on load.  The `remove_duplicates()` step is therefore
> most useful in the `--add-from` workflow, where you might add a
> record that already exists in the zone.

### `1.168.192.in-addr.arpa.zone` — reverse zone

Reverse-lookup zone for `192.168.1.0/24`.  PTR records are in a
shuffled order; the tool sorts them numerically by last octet
(1, 2, 10, 20, 21, 22, 30, 40, 50, 60).

---

## YAML file

### `add_records.yaml` — standard format

Records to inject into `example.com` using `--add-from`.
Requires a running BIND9 installation (`named-checkconf` must be on PATH).
Run with `--dry-run` first to preview before applying.

---

## Suggested commands

```bash
# Activate the virtual environment
source venv/bin/activate

# ── Forward zone ──────────────────────────────────────────────────────

# Preview (no files written)
cleandns --dry-run --files test_files/example.com.zone

# Apply — creates test_files/backups/ automatically
cleandns --files test_files/example.com.zone

# Inspect the backup
ls test_files/backups/

# ── Reverse zone ──────────────────────────────────────────────────────

cleandns --dry-run --files test_files/1.168.192.in-addr.arpa.zone
cleandns --files test_files/1.168.192.in-addr.arpa.zone

# ── Both zones at once ────────────────────────────────────────────────

cleandns --dry-run --files test_files/example.com.zone \
                          test_files/1.168.192.in-addr.arpa.zone

cleandns --files test_files/example.com.zone \
                 test_files/1.168.192.in-addr.arpa.zone

# ── Human-readable SOA timing ─────────────────────────────────────────

cleandns --dry-run --human-readable --files test_files/example.com.zone

# ── Custom backup directory ───────────────────────────────────────────

cleandns --backup-dir /tmp/dns-backups --files test_files/example.com.zone

# ── Disable backups ───────────────────────────────────────────────────

cleandns --no-backup --files test_files/example.com.zone

# ── Add records (requires BIND9 + named-checkconf) ────────────────────

cleandns --dry-run --add-from test_files/add_records.yaml
cleandns --add-from test_files/add_records.yaml
```
