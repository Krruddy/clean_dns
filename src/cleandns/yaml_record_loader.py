from pathlib import Path

import yaml

from cleandns.exceptions import InvalidYAMLError, UnknownRecordTypeError
from cleandns.record_types import (
    ARecord, AAAARecord, NSRecord, CNAMERecord, PTRRecord,
    RecordType, DNSClass, AbstractRecord,
)

_DEFAULT_TTL = 3600

# Maps the type string from YAML to (record class, RecordType enum value).
_RECORD_TYPES: dict[str, tuple[type[AbstractRecord], RecordType]] = {
    "A":     (ARecord,     RecordType.A),
    "AAAA":  (AAAARecord,  RecordType.AAAA),
    "NS":    (NSRecord,    RecordType.NS),
    "CNAME": (CNAMERecord, RecordType.CNAME),
    "PTR":   (PTRRecord,   RecordType.PTR),
}


class YAMLRecordLoader:
    """
    Loads DNS records from a YAML file.

    Expected format:
        zone-name:
          - type: A
            name: host
            rdata: 192.168.1.1
            ttl: 3600          # optional; defaults to the zone file's $TTL
    """

    @staticmethod
    def load(path: Path, default_ttl: int = _DEFAULT_TTL) -> dict[str, list[AbstractRecord]]:
        """
        Parse the YAML file at *path* and return a mapping of zone name to
        the list of records to add to that zone.

        *default_ttl* is used for any record that does not declare its own TTL.
        Pass the zone file's TTL here so that omitted TTLs are consistent with
        the rest of the zone.
        """
        try:
            with open(path) as f:
                data = yaml.safe_load(f)
        except OSError as e:
            raise InvalidYAMLError(f"Could not open YAML file '{path.name}': {e}") from e
        except yaml.YAMLError as e:
            raise InvalidYAMLError(f"Could not parse YAML file '{path.name}': {e}") from e

        if not isinstance(data, dict):
            raise InvalidYAMLError(
                f"'{path.name}': top-level structure must be a mapping of zone names to record lists."
            )

        result: dict[str, list[AbstractRecord]] = {}

        for zone_name, record_list in data.items():
            if not isinstance(record_list, list):
                raise InvalidYAMLError(
                    f"'{path.name}': records for zone '{zone_name}' must be a list."
                )
            result[str(zone_name)] = [
                _build_record(entry, path.name, str(zone_name), default_ttl)
                for entry in record_list
            ]

        return result


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
