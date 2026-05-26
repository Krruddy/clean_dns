import argparse
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from cleandns.config import DNSConfig


@dataclass(frozen=True)
class ParsedArgs:
    config: DNSConfig
    files: list[str]
    add_from: Path | None


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

    def parse_arguments(self, args: Sequence[str] | None = None) -> ParsedArgs:
        parsed_args = self.parser.parse_args(args)

        config = DNSConfig(
            omit_origin=parsed_args.omit_origin,
            human_readable=parsed_args.human_readable,
            omit_ttl=parsed_args.omit_ttl,
            omit_record_ttl=parsed_args.omit_record_ttl,
            dry_run=parsed_args.dry_run,
        )

        add_from = Path(parsed_args.add_from) if parsed_args.add_from else None

        return ParsedArgs(
            config=config,
            files=parsed_args.files or [],
            add_from=add_from,
        )
