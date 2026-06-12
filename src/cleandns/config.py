from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class DNSConfig:
    """Configuration options for DNS file processing."""
    omit_origin: bool = False
    human_readable: bool = False
    omit_ttl: bool = False
    omit_record_ttl: bool = False
    dry_run: bool = False
    reload: bool = False
    # backup_dir: explicit directory for backups; None means use the default
    #             ('backups/' subdirectory next to each zone file).
    # no_backup:  skip backup creation entirely (for external backup workflows).
    backup_dir: Optional[Path] = None
    no_backup: bool = False
    dedup_ip: bool = False
