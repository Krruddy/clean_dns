import subprocess
import pytest
from pathlib import Path
from unittest.mock import patch, call
from cleandns.argument_parser import ParsedArgs
from cleandns.config import DNSConfig
from cleandns.main import process_file, add_from_yaml
from cleandns.exceptions import InvalidZoneFileError, EmptyZoneFileError, MissingNSRecordError
from cleandns.logger import Logger

ZONE_FILE_ENCODING = "utf-8"


@pytest.fixture
def logger():
    return Logger()


@pytest.fixture
def config():
    return DNSConfig()


def _parsed_args(config=None, files=None, add_from=None):
    """Build a ParsedArgs for use in main() tests."""
    return ParsedArgs(
        config=config or DNSConfig(),
        files=files or [],
        add_from=add_from,
    )


# ---------------------------------------------------------------------------
# process_file — return codes
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# add_from_yaml — return codes
# ---------------------------------------------------------------------------

def test_add_from_yaml_returns_0_on_success(tmp_path, forward_sample_zone_content, config, logger):
    zone_file = tmp_path / "example.com.zone"
    zone_file.write_text(forward_sample_zone_content, encoding=ZONE_FILE_ENCODING)

    yaml_file = tmp_path / "records.yaml"
    yaml_file.write_text(
        "example.com:\n"
        "  - type: A\n"
        "    name: newhost\n"
        "    ttl: 3600\n"
        "    rdata: 10.99.99.99\n",
        encoding=ZONE_FILE_ENCODING,
    )

    with patch("cleandns.main.NamedConfParser.from_system", return_value={"example.com": zone_file}):
        assert add_from_yaml(yaml_file, logger, config) == 0


def test_add_from_yaml_returns_1_when_named_checkconf_fails(tmp_path, config, logger):
    from cleandns.exceptions import NamedConfNotFoundError
    yaml_file = tmp_path / "records.yaml"
    yaml_file.write_text("example.com: []\n", encoding=ZONE_FILE_ENCODING)

    with patch("cleandns.main.NamedConfParser.from_system", side_effect=NamedConfNotFoundError("not found")):
        assert add_from_yaml(yaml_file, logger, config) == 1


def test_add_from_yaml_returns_1_for_invalid_yaml(tmp_path, config, logger):
    yaml_file = tmp_path / "bad.yaml"
    yaml_file.write_text("key: [unclosed", encoding=ZONE_FILE_ENCODING)

    with patch("cleandns.main.NamedConfParser.from_system", return_value={}):
        assert add_from_yaml(yaml_file, logger, config) == 1


def test_add_from_yaml_returns_1_for_unknown_zone(tmp_path, config, logger):
    yaml_file = tmp_path / "records.yaml"
    yaml_file.write_text(
        "unknown.zone:\n"
        "  - type: A\n"
        "    name: host\n"
        "    ttl: 3600\n"
        "    rdata: 1.2.3.4\n",
        encoding=ZONE_FILE_ENCODING,
    )

    with patch("cleandns.main.NamedConfParser.from_system", return_value={}):
        assert add_from_yaml(yaml_file, logger, config) == 1


# ---------------------------------------------------------------------------
# main() — mode routing and exit code aggregation
# ---------------------------------------------------------------------------

def test_main_returns_1_when_any_file_fails(tmp_path, forward_sample_zone_content):
    good = tmp_path / "good.zone"
    good.write_text(forward_sample_zone_content, encoding=ZONE_FILE_ENCODING)
    bad = tmp_path / "missing.zone"

    with patch("cleandns.main.ArgumentParser") as mock_cls:
        mock_cls.return_value.parse_arguments.return_value = _parsed_args(
            files=[str(good), str(bad)]
        )
        from cleandns.main import main
        assert main() == 1


def test_main_returns_0_when_all_files_succeed(tmp_path, forward_sample_zone_content):
    p = tmp_path / "good.zone"
    p.write_text(forward_sample_zone_content, encoding=ZONE_FILE_ENCODING)

    with patch("cleandns.main.ArgumentParser") as mock_cls:
        mock_cls.return_value.parse_arguments.return_value = _parsed_args(files=[str(p)])
        from cleandns.main import main
        assert main() == 0


def test_main_returns_0_for_no_files():
    with patch("cleandns.main.ArgumentParser") as mock_cls:
        mock_cls.return_value.parse_arguments.return_value = _parsed_args()
        from cleandns.main import main
        assert main() == 0


def test_main_routes_to_add_from_yaml(tmp_path):
    yaml_file = tmp_path / "records.yaml"
    yaml_file.touch()

    with patch("cleandns.main.ArgumentParser") as mock_cls, \
         patch("cleandns.main.add_from_yaml", return_value=0) as mock_add:
        mock_cls.return_value.parse_arguments.return_value = _parsed_args(add_from=yaml_file)
        from cleandns.main import main
        assert main() == 0
        mock_add.assert_called_once()


# ---------------------------------------------------------------------------
# Dry-run mode — end-to-end via process_file / add_from_yaml
# ---------------------------------------------------------------------------

def test_process_file_dry_run_does_not_modify_file(tmp_path, forward_sample_zone_content, logger):
    """With dry_run=True process_file must return 0 but leave the file unchanged."""
    p = tmp_path / "example.com.zone"
    p.write_text(forward_sample_zone_content, encoding=ZONE_FILE_ENCODING)
    original = p.read_text(encoding=ZONE_FILE_ENCODING)
    dry_config = DNSConfig(dry_run=True)

    assert process_file(p, logger, dry_config) == 0
    assert p.read_text(encoding=ZONE_FILE_ENCODING) == original


def test_process_file_dry_run_creates_no_backup(tmp_path, forward_sample_zone_content, logger):
    """With dry_run=True no backup file or backup directory must be created."""
    p = tmp_path / "example.com.zone"
    p.write_text(forward_sample_zone_content, encoding=ZONE_FILE_ENCODING)
    dry_config = DNSConfig(dry_run=True)

    process_file(p, logger, dry_config)

    assert not (p.parent / "backups").exists()


def test_add_from_yaml_dry_run_does_not_modify_zone_file(tmp_path, forward_sample_zone_content, logger):
    """With dry_run=True add_from_yaml must return 0 but leave zone files unchanged."""
    zone_file = tmp_path / "example.com.zone"
    zone_file.write_text(forward_sample_zone_content, encoding=ZONE_FILE_ENCODING)
    original = zone_file.read_text(encoding=ZONE_FILE_ENCODING)

    yaml_file = tmp_path / "records.yaml"
    yaml_file.write_text(
        "example.com:\n"
        "  - type: A\n"
        "    name: drynewhost\n"
        "    ttl: 3600\n"
        "    rdata: 10.99.99.99\n",
        encoding=ZONE_FILE_ENCODING,
    )
    dry_config = DNSConfig(dry_run=True)

    with patch("cleandns.main.NamedConfParser.from_system", return_value={"example.com": zone_file}):
        assert add_from_yaml(yaml_file, logger, dry_config) == 0

    assert zone_file.read_text(encoding=ZONE_FILE_ENCODING) == original


# ---------------------------------------------------------------------------
# --reload flag — rndc reload integration
# ---------------------------------------------------------------------------

def test_process_file_reload_calls_rndc_when_changes_applied(
    tmp_path, complex_forward_zone_content, logger
):
    """With reload=True, rndc reload must be called after changes are written."""
    # complex_forward_zone_content is unsorted, so sort() will produce changes.
    p = tmp_path / "example.com.zone"
    p.write_text(complex_forward_zone_content, encoding=ZONE_FILE_ENCODING)
    reload_config = DNSConfig(reload=True)

    with patch("cleandns.main.subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        result = process_file(p, logger, reload_config)

    assert result == 0
    # rndc reload should have been called with the zone origin (example.com)
    mock_run.assert_called_once()
    cmd = mock_run.call_args[0][0]
    assert cmd[0] == "rndc"
    assert cmd[1] == "reload"
    assert "example.com" in cmd[2]


def test_process_file_reload_not_called_when_no_changes(
    tmp_path, complex_forward_zone_content, logger
):
    """With reload=True, rndc must NOT be called when the zone needed no changes."""
    p = tmp_path / "example.com.zone"
    p.write_text(complex_forward_zone_content, encoding=ZONE_FILE_ENCODING)

    # First pass — bring the file into its final sorted, deduped form so the
    # second pass genuinely has nothing to change.
    process_file(p, logger, DNSConfig())

    reload_config = DNSConfig(reload=True)
    with patch("cleandns.main.subprocess.run") as mock_run:
        result = process_file(p, logger, reload_config)

    assert result == 0
    mock_run.assert_not_called()


def test_process_file_reload_not_called_when_dry_run(
    tmp_path, complex_forward_zone_content, logger
):
    """--reload has no effect when combined with --dry-run."""
    p = tmp_path / "example.com.zone"
    p.write_text(complex_forward_zone_content, encoding=ZONE_FILE_ENCODING)
    config = DNSConfig(dry_run=True, reload=True)

    with patch("cleandns.main.subprocess.run") as mock_run:
        result = process_file(p, logger, config)

    assert result == 0
    mock_run.assert_not_called()


def test_process_file_reload_failure_returns_1(
    tmp_path, complex_forward_zone_content, logger
):
    """If rndc reload exits with a non-zero status, process_file must return 1."""
    p = tmp_path / "example.com.zone"
    p.write_text(complex_forward_zone_content, encoding=ZONE_FILE_ENCODING)
    reload_config = DNSConfig(reload=True)

    with patch("cleandns.main.subprocess.run",
               side_effect=subprocess.CalledProcessError(1, "rndc", stderr="zone not found")):
        result = process_file(p, logger, reload_config)

    assert result == 1


def test_process_file_reload_rndc_not_found_returns_1(
    tmp_path, complex_forward_zone_content, logger
):
    """If rndc is not on PATH, process_file must return 1."""
    p = tmp_path / "example.com.zone"
    p.write_text(complex_forward_zone_content, encoding=ZONE_FILE_ENCODING)
    reload_config = DNSConfig(reload=True)

    with patch("cleandns.main.subprocess.run", side_effect=FileNotFoundError):
        result = process_file(p, logger, reload_config)

    assert result == 1


def test_add_from_yaml_reload_calls_rndc_after_write(
    tmp_path, forward_sample_zone_content, logger
):
    """With reload=True, rndc reload must be called for each zone that was written."""
    zone_file = tmp_path / "example.com.zone"
    zone_file.write_text(forward_sample_zone_content, encoding=ZONE_FILE_ENCODING)

    yaml_file = tmp_path / "records.yaml"
    yaml_file.write_text(
        "example.com:\n"
        "  - type: A\n"
        "    name: newhost\n"
        "    ttl: 3600\n"
        "    rdata: 10.99.99.99\n",
        encoding=ZONE_FILE_ENCODING,
    )
    reload_config = DNSConfig(reload=True)

    with patch("cleandns.main.NamedConfParser.from_system", return_value={"example.com": zone_file}), \
         patch("cleandns.main.subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        result = add_from_yaml(yaml_file, logger, reload_config)

    assert result == 0
    mock_run.assert_called_once()
    cmd = mock_run.call_args[0][0]
    assert cmd == ["rndc", "reload", "example.com"]


def test_add_from_yaml_reload_failure_returns_1(
    tmp_path, forward_sample_zone_content, logger
):
    """If rndc reload fails during add_from_yaml, the function must return 1."""
    zone_file = tmp_path / "example.com.zone"
    zone_file.write_text(forward_sample_zone_content, encoding=ZONE_FILE_ENCODING)

    yaml_file = tmp_path / "records.yaml"
    yaml_file.write_text(
        "example.com:\n"
        "  - type: A\n"
        "    name: newhost\n"
        "    ttl: 3600\n"
        "    rdata: 10.99.99.99\n",
        encoding=ZONE_FILE_ENCODING,
    )
    reload_config = DNSConfig(reload=True)

    with patch("cleandns.main.NamedConfParser.from_system", return_value={"example.com": zone_file}), \
         patch("cleandns.main.subprocess.run",
               side_effect=subprocess.CalledProcessError(1, "rndc", stderr="permission denied")):
        result = add_from_yaml(yaml_file, logger, reload_config)

    assert result == 1
