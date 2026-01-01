import sys
from pathlib import Path
from src.cleandns.argument_parser import ArgumentParser
from src.cleandns.dns_file import DNSFile
from src.cleandns.logger import Logger

def process_file(file_path: Path, logger: Logger) -> bool:
    """
    Process a single DNS file. Returns True if successful, False otherwise.
    """
    if not file_path.is_file():
        logger.warning(f"Skipping {file_path}: Not a valid file.")
        return False

    try:
        dns_file = DNSFile(file_path)
        dns_file.remove_duplicates()
        dns_file.sort()
        dns_file.save()
        logger.info(f"Successfully processed {file_path.name}")
        return True
    except Exception as e:
        logger.error(f"Failed to process {file_path.name}: {e}")
        return False

def main():
    # Initialize the singleton logger (configuration is handled inside the class)
    logger = Logger()

    arg_parser = ArgumentParser()
    args = arg_parser.parse_arguments()

    files_to_process = []

    if not args.files:
        logger.warning("No files provided to process. Use --help for more information.")
        sys.exit(0)

    files_to_process = [Path(f) for f in args.files]

    has_error = False

    # Process files sequentially
    for file_path in files_to_process:
        success = process_file(file_path, logger)
        if not success:
            has_error = True

    # Exit with non-zero code if any file failed
    sys.exit(1 if has_error else 0)

if __name__ == "__main__":
    main()
