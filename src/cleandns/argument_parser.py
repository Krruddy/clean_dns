import argparse
from collections.abc import Sequence


class ArgumentParser:
    parser: argparse.ArgumentParser

    def __init__(self) -> None:
        self.parser = argparse.ArgumentParser(description="A tool to process and manage DNS files cleanly.")
        _ = self.parser.add_argument(
            "-f", "--files",
            nargs='+',
            type=str,
            help="the DNS files that will be treated by the program"
        )

    def parse_arguments(self, args: Sequence[str] | None = None) -> argparse.Namespace:
        return self.parser.parse_args(args)
