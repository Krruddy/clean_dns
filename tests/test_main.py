import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from cleandns.config import DNSConfig
from cleandns.main import process_file
from cleandns.exceptions import InvalidZoneFileError, EmptyZoneFileError, MissingNSRecordError
from cleandns.logger import Logger

ZONE_FILE_ENCODING = "utf-8"


@pytest.fixture
def logger():
    return Logger()


@pytest.fixture
def config():
    return DNSConfig()


# --- process_file return codes ---

def test_process_file_returns_0_on_success(tmp_path, forward_sample_zone_content, config, logger):
    p = tmp_path / "example.com.zone"
    p.write_text(forward_sample_zone_content, encoding=ZONE_FILE_ENCODING)

    assert process_file(p, logger, config) == 0


def test_process_file_returns_1_for_nonexistent_path(tmp_path, config, logger):
    assert process_file(tmp_path / "missing.zone", logger, config) == 1


def test_process_file_returns_1_for_directory(tmp_path, config, logger):
    assert process_file(tmp_path, logger, config) == 1


def test_process_file_returns_1_for_empty_file(tmp_path, config, logger):
    p = tmp_path / "empty.zone"
    p.write_text("", encoding=ZONE_FILE_ENCODING)

    assert process_file(p, logger, config) == 1


def test_process_file_returns_1_for_invalid_zone(tmp_path, config, logger):
    p = tmp_path / "bad.zone"
    p.write_text("$TTL INVALID\n", encoding=ZONE_FILE_ENCODING)

    assert process_file(p, logger, config) == 1


def test_process_file_returns_1_for_missing_ns(tmp_path, sample_ttl_line, sample_origin_line, sample_soa_block, config, logger):
    content = f"{sample_ttl_line}\n{sample_origin_line}\n{sample_soa_block}\n"
    p = tmp_path / "no_ns.zone"
    p.write_text(content, encoding=ZONE_FILE_ENCODING)

    assert process_file(p, logger, config) == 1


def test_process_file_returns_1_on_permission_error(tmp_path, forward_sample_zone_content, config, logger):
    p = tmp_path / "example.com.zone"
    p.write_text(forward_sample_zone_content, encoding=ZONE_FILE_ENCODING)

    with patch("cleandns.main.DNSFile", side_effect=PermissionError("denied")):
        assert process_file(p, logger, config) == 1


def test_process_file_returns_1_on_os_error(tmp_path, forward_sample_zone_content, config, logger):
    p = tmp_path / "example.com.zone"
    p.write_text(forward_sample_zone_content, encoding=ZONE_FILE_ENCODING)

    with patch("cleandns.main.DNSFile", side_effect=OSError("disk full")):
        assert process_file(p, logger, config) == 1


# --- main() aggregation ---

def test_main_returns_1_when_any_file_fails(tmp_path, forward_sample_zone_content):
    good = tmp_path / "good.zone"
    good.write_text(forward_sample_zone_content, encoding=ZONE_FILE_ENCODING)
    bad = tmp_path / "missing.zone"

    with patch("cleandns.main.ArgumentParser") as mock_parser_cls:
        mock_parser = MagicMock()
        mock_parser.parse_arguments.return_value = (DNSConfig(), [str(good), str(bad)])
        mock_parser_cls.return_value = mock_parser

        from cleandns.main import main
        assert main() == 1


def test_main_returns_0_when_all_files_succeed(tmp_path, forward_sample_zone_content):
    p = tmp_path / "good.zone"
    p.write_text(forward_sample_zone_content, encoding=ZONE_FILE_ENCODING)

    with patch("cleandns.main.ArgumentParser") as mock_parser_cls:
        mock_parser = MagicMock()
        mock_parser.parse_arguments.return_value = (DNSConfig(), [str(p)])
        mock_parser_cls.return_value = mock_parser

        from cleandns.main import main
        assert main() == 0


def test_main_returns_0_for_no_files():
    with patch("cleandns.main.ArgumentParser") as mock_parser_cls:
        mock_parser = MagicMock()
        mock_parser.parse_arguments.return_value = (DNSConfig(), [])
        mock_parser_cls.return_value = mock_parser

        from cleandns.main import main
        assert main() == 0
