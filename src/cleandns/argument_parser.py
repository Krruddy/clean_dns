import argparse


class ArgumentParser:
    def __init__(self):
        self.parser = argparse.ArgumentParser(description="A tool to process and manage DNS files cleanly.")
        input = self.parser.add_mutually_exclusive_group(required=True)
        input.add_argument(
            "-f", "--files",
            nargs='+',
            type=str,
            help="the DNS files that will be treated by the program"
        )
        input.add_argument(
            "-l", "--list",
            type=str,
            help="path to a text file that contains the names of the DNS files that will be treated by the program (One dns name per line)."
        )
        self.parser.add_argument(
            "--keep-comments",
            action='store_true',
            help="If set, comments in the DNS files will be preserved."
        )

    def parse_arguments(self):
        return self.parser.parse_args()
