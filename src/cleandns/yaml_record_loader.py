from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Type

import yaml

from cleandns.exceptions import InvalidYAMLError, UnknownRecordTypeError
from cleandns.record_types import (
    ARecord, AAAARecord, NSRecord, CNAMERecord, MXRecord, PTRRecord, TXTRecord,
    RecordType, DNSClass, AbstractRecord,
)

_DEFAULT_TTL = 3600

# Maps the type string from YAML to (record class, RecordType enum value).
_RECORD_TYPES: Dict[str, Tuple[Type[AbstractRecord], RecordType]] = {
    "A":     (ARecord,     RecordType.A),
    "AAAA":  (AAAARecord,  RecordType.AAAA),
    "NS":    (NSRecord,    RecordType.NS),
    "CNAME": (CNAMERecord, RecordType.CNAME),
    "MX":    (MXRecord,    RecordType.MX),
    "PTR":   (PTRRecord,   RecordType.PTR),
    "TXT":   (TXTRecord,   RecordType.TXT),
}


class YAMLFormat(ABC):
    """
    Abstract base class for YAML input-format handlers.

    Each concrete subclass is responsible for:
      - declaring whether it can handle a given parsed YAML document (can_parse)
      - converting that document into a zone-name → record-list mapping (parse)

    To support a new YAML structure, subclass YAMLFormat, implement both
    methods, and insert the class into _FORMATS before the StandardFormat
    fallback.
    """

    @classmethod
    @abstractmethod
    def can_parse(cls, data: object) -> bool:
        """Return True if *data* matches this format's expected top-level structure."""
        ...

    @classmethod
    @abstractmethod
    def parse(
        cls,
        data: object,
        filename: str,
        default_ttl: int,
        zone_map: Optional[Dict[str, Path]] = None,
    ) -> Dict[str, List[AbstractRecord]]:
        """
        Parse *data* and return a mapping of zone name to the list of records
        to add to that zone.  Raise InvalidYAMLError on any validation failure.

        *zone_map* is the BIND zone-name → file-path mapping from
        named-checkconf.  Formats that derive zone names from FQDNs should use
        it for accurate matching; formats with explicit zone names may ignore it.
        """
        ...


class StandardFormat(YAMLFormat):
    """
    Zone-keyed format — the default/canonical format for this tool:

        zone-name:
          - type: A
            name: host
            rdata: 192.168.1.1
            ttl: 3600   # optional; defaults to the zone file's $TTL
    """

    @classmethod
    def can_parse(cls, data: object) -> bool:
        # Acts as the fallback: any top-level mapping that is not claimed by a
        # more specific format is treated as StandardFormat.
        return isinstance(data, dict)

    @classmethod
    def parse(
        cls,
        data: object,
        filename: str,
        default_ttl: int,
        zone_map: Optional[Dict[str, Path]] = None,
    ) -> Dict[str, List[AbstractRecord]]:
        if not isinstance(data, dict):
            raise InvalidYAMLError(
                f"'{filename}': top-level structure must be a mapping of zone names to record lists."
            )

        result: Dict[str, List[AbstractRecord]] = {}
        for zone_name, record_list in data.items():
            if not isinstance(record_list, list):
                raise InvalidYAMLError(
                    f"'{filename}': records for zone '{zone_name}' must be a list."
                )
            result[str(zone_name)] = [
                _build_record(entry, filename, str(zone_name), default_ttl)
                for entry in record_list
            ]
        return result


class DNSEntriesFormat(YAMLFormat):
    """
    IP/FQDN shorthand format.  Creates an A record in the forward zone and,
    when a matching reverse zone is present in zone_map, a PTR record too:

        dnsEntries:
          - ip: 10.10.100.123
            fqdn: host3.example.com
          - ip: 10.10.100.124
            fqdn: host4.example.com

    The forward zone is derived by stripping the first label from the FQDN:
      host3.example.com   → zone 'example.com',     name 'host3'
      web.sub.example.com → zone 'sub.example.com', name 'web'

    The reverse zone is found via longest-prefix matching against zone_map
    (e.g. 192.168.1.10 → '1.168.192.in-addr.arpa' if that zone is known).
    PTR records are only added when zone_map is provided and contains a
    matching reverse zone; they are silently skipped otherwise.
    """

    @classmethod
    def can_parse(cls, data: object) -> bool:
        return isinstance(data, dict) and "dnsEntries" in data

    @classmethod
    def parse(
        cls,
        data: object,
        filename: str,
        default_ttl: int,
        zone_map: Optional[Dict[str, Path]] = None,
    ) -> Dict[str, List[AbstractRecord]]:
        if not isinstance(data, dict) or not isinstance(data.get("dnsEntries"), list):
            raise InvalidYAMLError(
                f"'{filename}': 'dnsEntries' must be a list."
            )

        result: Dict[str, List[AbstractRecord]] = {}

        for entry in data["dnsEntries"]:
            if not isinstance(entry, dict):
                raise InvalidYAMLError(
                    f"'{filename}': each entry in 'dnsEntries' must be a mapping."
                )

            ip = entry.get("ip")
            fqdn_raw = entry.get("fqdn")

            if ip is None:
                raise InvalidYAMLError(
                    f"'{filename}': missing required field 'ip' in dnsEntries entry."
                )
            if fqdn_raw is None:
                raise InvalidYAMLError(
                    f"'{filename}': missing required field 'fqdn' in dnsEntries entry."
                )

            name, zone = _resolve_fqdn(str(fqdn_raw), filename, zone_map)

            record = ARecord(
                name=name,
                ttl=default_ttl,
                class_=DNSClass.IN,
                type=RecordType.A,
                rdata=str(ip),
                omit_ttl=False,
            )
            result.setdefault(zone, []).append(record)

            if zone_map is not None:
                ptr = _build_ptr_entry(str(ip), str(fqdn_raw), zone_map, default_ttl)
                if ptr is not None:
                    reverse_zone, ptr_record = ptr
                    result.setdefault(reverse_zone, []).append(ptr_record)

        return result


# Formats are tried in declaration order; more specific formats must come
# before the StandardFormat fallback.
_FORMATS: List[Type[YAMLFormat]] = [DNSEntriesFormat, StandardFormat]


class YAMLRecordLoader:
    """
    Loads DNS records from a YAML file, auto-detecting the format.

    Supported formats (tried in declaration order, most specific first):
      - DNSEntriesFormat — dnsEntries: [{ip, fqdn}, ...]
      - StandardFormat   — zone-name: [{type, name, rdata, ttl?}, ...]
    """

    @staticmethod
    def load(
        path: Path,
        default_ttl: int = _DEFAULT_TTL,
        zone_map: Optional[Dict[str, Path]] = None,
    ) -> Dict[str, List[AbstractRecord]]:
        """
        Parse the YAML file at *path* and return a mapping of zone name to
        the list of records to add to that zone.  The format is auto-detected.

        *default_ttl* is used for any record that does not declare its own TTL.
        Pass the zone file's $TTL here so that omitted TTLs are consistent with
        the rest of the zone.

        *zone_map* is the BIND zone-name → file-path mapping from
        named-checkconf (as returned by NamedConfParser.from_system()).  When
        provided, formats that derive zone names from FQDNs — such as
        DNSEntriesFormat — use longest-suffix matching to resolve each FQDN to
        the correct zone.  When omitted, those formats fall back to stripping
        only the first label.
        """
        try:
            with open(path) as f:
                data = yaml.safe_load(f)
        except OSError as e:
            raise InvalidYAMLError(f"Could not open YAML file '{path.name}': {e}") from e
        except yaml.YAMLError as e:
            raise InvalidYAMLError(f"Could not parse YAML file '{path.name}': {e}") from e

        for fmt in _FORMATS:
            if fmt.can_parse(data):
                return fmt.parse(data, path.name, default_ttl, zone_map)

        raise InvalidYAMLError(
            f"'{path.name}': unrecognised YAML structure. "
            f"Supported formats: {', '.join(f.__name__ for f in _FORMATS)}."
        )


def _build_record(
    entry: object,
    filename: str,
    zone_name: str,
    default_ttl: int,
) -> AbstractRecord:
    if not isinstance(entry, dict):
        raise InvalidYAMLError(
            f"'{filename}': each record in zone '{zone_name}' must be a mapping."
        )

    record_type_str = str(entry.get("type", "")).upper()
    if record_type_str not in _RECORD_TYPES:
        raise UnknownRecordTypeError(
            f"'{filename}': unsupported record type '{record_type_str}' in zone '{zone_name}'. "
            f"Supported types: {', '.join(sorted(_RECORD_TYPES))}."
        )

    name = entry.get("name")
    rdata = entry.get("rdata")
    ttl = entry.get("ttl", default_ttl)

    if name is None:
        raise InvalidYAMLError(
            f"'{filename}': missing required field 'name' in zone '{zone_name}'."
        )
    if rdata is None:
        raise InvalidYAMLError(
            f"'{filename}': missing required field 'rdata' in zone '{zone_name}'."
        )
    if not isinstance(ttl, int) or ttl < 0:
        raise InvalidYAMLError(
            f"'{filename}': 'ttl' must be a non-negative integer in zone '{zone_name}'."
        )

    record_cls, enum_type = _RECORD_TYPES[record_type_str]
    return record_cls(
        name=str(name),
        ttl=ttl,
        class_=DNSClass.IN,
        type=enum_type,
        rdata=str(rdata),
        omit_ttl=False,  # updated by DNSFile.add_record() to match config
    )


def _build_ptr_entry(
    ip: str,
    fqdn: str,
    zone_map: Dict[str, Path],
    default_ttl: int,
) -> Optional[Tuple[str, PTRRecord]]:
    """
    Return (reverse_zone_name, PTRRecord) for an IPv4 address, or None if the
    IP is not a valid IPv4 address or no reverse zone in zone_map matches.

    Uses longest-prefix matching: a /24 reverse zone is preferred over a /16,
    which is preferred over a /8.
    """
    parts = ip.split('.')
    if len(parts) != 4:
        return None
    try:
        int_parts = [int(p) for p in parts]
    except ValueError:
        return None
    if not all(0 <= v <= 255 for v in int_parts):
        return None

    reversed_parts = parts[::-1]   # ['10', '1', '168', '192'] for 192.168.1.10
    ptr_rdata = fqdn if fqdn.endswith('.') else fqdn + '.'

    # i = number of octets that become the record name inside the zone.
    # i=1 → zone has 3 octets (/24, most specific); i=3 → zone has 1 octet (/8).
    for i in range(1, len(reversed_parts)):
        zone_candidate = '.'.join(reversed_parts[i:]) + '.in-addr.arpa'
        if zone_candidate in zone_map:
            return (zone_candidate, PTRRecord(
                name='.'.join(reversed_parts[:i]),
                ttl=default_ttl,
                class_=DNSClass.IN,
                type=RecordType.PTR,
                rdata=ptr_rdata,
                omit_ttl=False,
            ))

    return None


def _resolve_fqdn(
    fqdn: str,
    filename: str,
    zone_map: Optional[Dict[str, Path]],
) -> Tuple[str, str]:
    """
    Resolve an FQDN to (name, zone).

    When *zone_map* is provided, uses longest-suffix matching so that the most
    specific known zone is preferred over a less specific parent:

        FQDN 'host.sub.example.com' against zones
        {'sub.example.com', 'example.com'}
        → name='host', zone='sub.example.com'   ✓  (not example.com)

        FQDN 'host.sub.example.com' against zones {'example.com'}
        → name='host.sub', zone='example.com'   ✓

    When *zone_map* is None, falls back to stripping the first label only
    (appropriate for tests or invocations without BIND context):
        'host3.example.com' → ('host3', 'example.com')

    Raises InvalidYAMLError if the FQDN has fewer than two labels, or if
    *zone_map* is provided but no zone matches.
    """
    labels = fqdn.rstrip('.').split('.')

    if len(labels) < 2 or not labels[0]:
        raise InvalidYAMLError(
            f"'{filename}': cannot derive a zone from FQDN '{fqdn}': "
            f"expected at least two dot-separated labels."
        )

    if zone_map is not None:
        # Try all suffixes from most specific (longest) to least specific.
        for i in range(1, len(labels)):
            candidate_zone = '.'.join(labels[i:])
            if candidate_zone in zone_map:
                return '.'.join(labels[:i]), candidate_zone
        raise InvalidYAMLError(
            f"'{filename}': FQDN '{fqdn}' does not match any known zone."
        )

    # Fallback: strip the first label only.
    return labels[0], '.'.join(labels[1:])
