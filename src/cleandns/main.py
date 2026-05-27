import subprocess
import sys
from pathlib import Path
from typing import List, Optional

from cleandns.argument_parser import ArgumentParser
from cleandns.config import DNSConfig
from cleandns.dns_file import DNSFile, ZoneChanges
from cleandns.logger import Logger
from cleandns.named_conf_parser import NamedConfParser
from cleandns.yaml_record_loader import YAMLRecordLoader
from cleandns.exceptions import (
    InvalidZoneFileError, EmptyZoneFileError, MissingNSRecordError,
    NamedConfError, InvalidYAMLError, ZoneNotFoundError,
)


def _rndc_reload(zone_name: Optional[str], logger: Logger) -> bool:
    """
    Run `rndc reload [zone_name]`. Returns True on success, False on failure.
    When zone_name is None, reloads all zones.
    """
    cmd = ["rndc", "reload"]
    if zone_name:
        cmd.append(zone_name)
    label = zone_name or "all zones"

    try:
        subprocess.run(cmd, capture_output=True, text=True, check=True)
        logger.info(f"rndc reload succeeded for {label}")
        return True
    except FileNotFoundError:
        logger.error("rndc not found — is BIND9 installed and on PATH?")
        return False
    except subprocess.CalledProcessError as e:
        logger.error(f"rndc reload failed for {label}: {e.stderr.strip()}")
        return False
    except OSError as e:
        logger.error(f"Could not run rndc: {e}")
        return False


def _log_changes(changes: ZoneChanges, logger: Logger, label: str, dry_run: bool) -> None:
    """Log a human-readable summary of what did (or would) change in a zone."""
    tag = "[DRY RUN] " if dry_run else ""

    if not changes.has_changes:
        logger.info(f"{tag}{label}: no changes")
        return

    parts: List[str] = []
    if changes.records_added:
        record_strs = ", ".join(f"{r.name} ({r.type.value})" for r in changes.records_added)
        parts.append(f"added {len(changes.records_added)} record(s): {record_strs}")
    if changes.duplicates_removed:
        parts.append(f"removed {len(changes.duplicates_removed)} duplicate(s)")
    if changes.was_reordered:
        parts.append("reordered records")
    if changes.serial_before != changes.serial_after:
        parts.append(f"serial {changes.serial_before} → {changes.serial_after}")

    logger.info(f"{tag}{label}: {'; '.join(parts)}")


def process_file(file_path: Path, logger: Logger, config: DNSConfig) -> int:
    """
    Process a single DNS file. Returns 0 on success, 1 on failure.
    """
    if not file_path.is_file():
        logger.warning(f"Skipping {file_path}: Not a valid file.")
        return 1

    try:
        dns_file = DNSFile(file_path, config)
        dns_file.remove_duplicates()
        dns_file.sort()
        changes = dns_file.save()
        _log_changes(changes, logger, file_path.name, config.dry_run)
        if changes.has_changes and not config.dry_run:
            logger.info(f"Successfully processed {file_path.name}")
            if config.reload:
                zone_name = dns_file.origin.rstrip('.') if dns_file.origin else None
                if not _rndc_reload(zone_name, logger):
                    return 1
        return 0
    except FileNotFoundError as e:
        logger.error(f"File not found: '{file_path}'\n{e}")
        return 1
    except PermissionError as e:
        logger.error(f"Permission denied: '{file_path}'\n{e}")
        return 1
    except OSError as e:
        logger.error(f"OS error while processing '{file_path}'\n{e}")
        return 1
    except EmptyZoneFileError as e:
        logger.error(f"Invalid zone file: '{file_path}'\n{e}")
        return 1
    except MissingNSRecordError as e:
        logger.error(f"Invalid zone file: '{file_path}'\n{e}")
        return 1
    except InvalidZoneFileError as e:
        logger.error(f"Invalid zone file: '{file_path}'\n{e}")
        return 1


def add_from_yaml(yaml_path: Path, logger: Logger, config: DNSConfig) -> int:
    """
    Add records from a YAML file to the appropriate zone files discovered
    via named-checkconf -p. Returns 0 on success, 1 on failure.
    """
    try:
        zone_map = NamedConfParser.from_system()
    except NamedConfError as e:
        logger.error(f"Could not read BIND9 configuration: {e}")
        return 1

    try:
        records_by_zone = YAMLRecordLoader.load(yaml_path, zone_map=zone_map)
    except InvalidYAMLError as e:
        logger.error(f"Could not load YAML file: {e}")
        return 1

    # Validate all zones are known before touching any file.
    unknown = [z for z in records_by_zone if z not in zone_map]
    if unknown:
        logger.error(
            f"The following zones were not found in named-checkconf output: "
            f"{', '.join(unknown)}"
        )
        return 1

    failed_zones: List[str] = []

    for zone_name, records in records_by_zone.items():
        file_path = zone_map[zone_name]
        try:
            dns_file = DNSFile(file_path, config)
            for record in records:
                dns_file.add_record(record)
            dns_file.remove_duplicates()
            dns_file.sort()
            changes = dns_file.save()
            _log_changes(changes, logger, f"{file_path.name} ({zone_name})", config.dry_run)
            if changes.has_changes and not config.dry_run:
                logger.info(f"Successfully updated {file_path.name} ({zone_name})")
                if config.reload:
                    if not _rndc_reload(zone_name, logger):
                        failed_zones.append(zone_name)
        except FileNotFoundError as e:
            logger.error(f"File not found: '{file_path}'\n{e}")
            failed_zones.append(zone_name)
        except PermissionError as e:
            logger.error(f"Permission denied: '{file_path}'\n{e}")
            failed_zones.append(zone_name)
        except OSError as e:
            logger.error(f"OS error while processing '{file_path}'\n{e}")
            failed_zones.append(zone_name)
        except InvalidZoneFileError as e:
            logger.error(f"Invalid zone file '{file_path}': {e}")
            failed_zones.append(zone_name)

    if failed_zones:
        logger.error(f"Failed to update: {', '.join(failed_zones)}")
        return 1

    return 0


def main():
    # Initialize the singleton logger (configuration is handled inside the class)
    logger = Logger()

    arg_parser = ArgumentParser()
    parsed = arg_parser.parse_arguments()

    if parsed.add_from is not None:
        return add_from_yaml(parsed.add_from, logger, parsed.config)

    if not parsed.files:
        logger.warning("No files provided to process. Use --help for more information.")
        return 0

    files_to_process = [Path(f) for f in parsed.files]
    failed_files: List[str] = []

    # Process files sequentially
    for file_path in files_to_process:
        if process_file(file_path, logger, parsed.config) != 0:
            failed_files.append(file_path.name)

    if failed_files:
        logger.error(f"Failed to process: {', '.join(failed_files)}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
