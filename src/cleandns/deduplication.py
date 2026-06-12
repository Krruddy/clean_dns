import sys
from collections import defaultdict
from typing import Dict, List

from cleandns.logger import Logger
from cleandns.record_types import AbstractRecord, RecordType

# A and AAAA are the only standard record types whose rdata is a bare IP address,
# making same-IP grouping meaningful.  PTR rdata is a hostname; CNAME/MX/NS/TXT
# rdata is not an IP address either.
DEDUP_RECORD_TYPES = frozenset({RecordType.A, RecordType.AAAA})


def find_ip_duplicates(
    records: Dict[RecordType, List[AbstractRecord]]
) -> List[List[AbstractRecord]]:
    """
    Return groups of records that share both record type and IP address (rdata).
    Only A and AAAA records are considered.  Groups containing a single record
    are excluded.  Within each group the original list order is preserved.
    """
    groups: List[List[AbstractRecord]] = []
    for rtype in DEDUP_RECORD_TYPES:
        if rtype not in records:
            continue
        by_ip: Dict[str, List[AbstractRecord]] = defaultdict(list)
        for record in records[rtype]:
            by_ip[record.rdata].append(record)
        for group in by_ip.values():
            if len(group) > 1:
                groups.append(list(group))
    return groups


def prompt_deduplication(
    groups: List[List[AbstractRecord]], logger: Logger
) -> List[AbstractRecord]:
    """
    Interactively prompt the user to resolve each group of IP-duplicate records.
    Returns a list of records to remove (those the user chose not to keep).

    If stdout is not a TTY (e.g. a systemd timer or automated pipeline), logs a
    warning and returns an empty list so the process never hangs.
    """
    if not groups:
        return []

    if not sys.stdout.isatty():
        logger.warning(
            "Non-interactive terminal detected; skipping --dedup-ip prompts. "
            "All duplicate records will be kept."
        )
        return []

    records_to_remove: List[AbstractRecord] = []

    for group in groups:
        ip = group[0].rdata
        rtype = group[0].type.value
        print(f"\nDuplicate {rtype} records pointing to {ip}:")
        for idx, record in enumerate(group):
            print(f"  {idx}: {record}")

        while True:
            raw = input(
                "Insert the numbers corresponding to the records you wish to KEEP "
                "(e.g., 0,2), or press Enter to keep all: "
            ).strip()

            if not raw:
                break

            try:
                indices = [int(token.strip()) for token in raw.split(",")]
            except ValueError:
                print("Invalid input: please enter comma-separated integers (e.g., 0,2).")
                continue

            if any(i < 0 or i >= len(group) for i in indices):
                print(
                    f"Out-of-bounds: valid indices are 0–{len(group) - 1}. "
                    "Please try again."
                )
                continue

            keep_set = set(indices)
            for idx, record in enumerate(group):
                if idx not in keep_set:
                    records_to_remove.append(record)
            break

    return records_to_remove
