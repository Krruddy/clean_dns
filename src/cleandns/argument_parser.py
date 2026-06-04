import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Sequence

from cleandns.config import DNSConfig


@dataclass(frozen=True)
class ParsedArgs:
    config: DNSConfig
    files: List[str]
    add_from: Optional[Path]
    remove_from: Optional[Path]


class ArgumentParser:
    parser: argparse.ArgumentParser

    def __init__(self) -> None:
        self.parser = argparse.ArgumentParser(description="A tool to process and manage DNS files cleanly.")

        mode_group = self.parser.add_mutually_exclusive_group()
        _ = mode_group.add_argument(
            "-f", "--files",
            nargs='+',
            type=str,
            help="the DNS files that will be treated by the program."
        )
        _ = mode_group.add_argument(
            "--add-from",
            metavar="YAML",
            type=str,
            help="YAML file listing records to add. Zone files are discovered via named-checkconf -p."
        )
        _ = mode_group.add_argument(
            "--remove-from",
            metavar="YAML",
            type=str,
            help="YAML file listing records to remove. Zone files are discovered via named-checkconf -p."
        )

        _ = self.parser.add_argument(
            "--omit-origin",
            action="store_true",
            default=False,
            help="Do not output the $ORIGIN line in the reconstructed file."
        )
        _ = self.parser.add_argument(
            "--human-readable",
            action="store_true",
            default=False,
            help="Output the TLL values, and the SOA time values in a human-readable format (e.g., 1w2d3h4m5s instead of 123456)."
        )
        ttl_group = self.parser.add_mutually_exclusive_group()
        _ = ttl_group.add_argument(
            "--omit-ttl",
            action="store_true",
            default=False,
            help="Do not output the $TTL line in the reconstructed file."
        )
        _ = ttl_group.add_argument(
            "--omit-record-ttl",
            action="store_true",
            default=False,
            help="Do not output the TTL value for individual records in the reconstructed file."
        )
        _ = self.parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help=(
                "Show what would be changed without writing any files. "
                "A change summary is always printed; this flag prevents the actual write."
            ),
        )
        _ = self.parser.add_argument(
            "--reload",
            action="store_true",
            default=False,
            help=(
                "Run 'rndc reload <zone>' after each zone file is successfully written. "
                "BIND is NOT reloaded by default; use this flag only when you are "
                "confident the changes are correct. Has no effect with --dry-run."
            ),
        )

        backup_group = self.parser.add_mutually_exclusive_group()
        _ = backup_group.add_argument(
            "--backup-dir",
            metavar="DIR",
            type=str,
            default=None,
            help=(
                "Directory where zone file backups are stored. "
                "Defaults to a 'backups/' subdirectory next to each zone file."
            ),
        )
        _ = backup_group.add_argument(
            "--no-backup",
            action="store_true",
            default=False,
            help="Disable backup creation. Use when backups are managed externally.",
        )

    def parse_arguments(self, args: Optional[Sequence[str]] = None) -> ParsedArgs:
        parsed_args = self.parser.parse_args(args)

        backup_dir = Path(parsed_args.backup_dir) if parsed_args.backup_dir else None

        config = DNSConfig(
            omit_origin=parsed_args.omit_origin,
            human_readable=parsed_args.human_readable,
            omit_ttl=parsed_args.omit_ttl,
            omit_record_ttl=parsed_args.omit_record_ttl,
            dry_run=parsed_args.dry_run,
            reload=parsed_args.reload,
            backup_dir=backup_dir,
            no_backup=parsed_args.no_backup,
        )

        add_from = Path(parsed_args.add_from) if parsed_args.add_from else None
        remove_from = Path(parsed_args.remove_from) if parsed_args.remove_from else None

        return ParsedArgs(
            config=config,
            files=parsed_args.files or [],
            add_from=add_from,
            remove_from=remove_from,
        )
