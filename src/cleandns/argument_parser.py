import argparse
from collections.abc import Sequence
from cleandns.config import DNSConfig


class ArgumentParser:
    parser: argparse.ArgumentParser

    def __init__(self) -> None:
        self.parser = argparse.ArgumentParser(description="A tool to process and manage DNS files cleanly.")
        _ = self.parser.add_argument(
            "-f", "--files",
            nargs='+',
            type=str,
            help="the DNS files that will be treated by the program."
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

    def parse_arguments(self, args: Sequence[str] | None = None) -> tuple[DNSConfig, list[str]]:      
        parsed_args = self.parser.parse_args(args)                                                    
                                                                                                      
        config = DNSConfig(                                                                           
            omit_origin=parsed_args.omit_origin,                                                      
            human_readable=parsed_args.human_readable,                                                
            omit_ttl=parsed_args.omit_ttl,                                                            
            omit_record_ttl=parsed_args.omit_record_ttl                                               
        )                                                                                             
                                                                                                      
        return config, parsed_args.files if parsed_args.files else None
