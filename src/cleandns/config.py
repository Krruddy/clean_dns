from dataclasses import dataclass

@dataclass(frozen=True)
class DNSConfig:
    """Configuration options for DNS file processing."""
    omit_origin: bool = False
    human_readable: bool = False
    omit_ttl: bool = False
    omit_record_ttl: bool = False
    dry_run: bool = False
