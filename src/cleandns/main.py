import sys
from pathlib import Path
from cleandns.argument_parser import ArgumentParser
from cleandns.dns_file import DNSFile
from cleandns.logger import Logger
from cleandns.exceptions import InvalidZoneFile, EmptyZoneFile

def process_file(file_path: Path, logger: Logger, config: dict[str, bool]) -> int:
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
        dns_file.save()
        logger.info(f"Successfully processed {file_path.name}")
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
    except EmptyZoneFile as e:
        logger.error(f"Invalid zone file: '{file_path}'\n{e}")
        return 1
    except InvalidZoneFile as e:
        logger.error(f"Invalid zone file: '{file_path}'\n{e}")
        return 1


def main():
    # Initialize the singleton logger (configuration is handled inside the class)
    logger = Logger()

    arg_parser = ArgumentParser()
    config, file_list = arg_parser.parse_arguments()

    files_to_process = []

    if not file_list:
        logger.warning("No files provided to process. Use --help for more information.")
        return 0

    files_to_process = [Path(f) for f in file_list]

    failed_files = []

    # Process files sequentially
    for file_path in files_to_process:
        if process_file(file_path, logger, config) != 0:
            failed_files.append(file_path.name) 
            logger.error(f"Failed to process {file_path.name}")

    if failed_files:
        logger.error(f"Failed to process the following files: {', '.join(failed_files)}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
