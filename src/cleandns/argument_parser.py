import argparse


class ArgumentParser:
    def __init__(self):
        self.parser = argparse.ArgumentParser(description="A tool to process and manage DNS files cleanly.")
        self.parser.add_argument(
            "-f", "--files",
            nargs='+',
            type=str,
            help="the DNS files that will be treated by the program"
        )

    def parse_arguments(self, args=None):
        return self.parser.parse_args(args)
