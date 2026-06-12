import subprocess
import pytest
from pathlib import Path
from unittest.mock import patch, call
from cleandns.argument_parser import ParsedArgs
from cleandns.config import DNSConfig
from cleandns.main import process_file, add_from_yaml, remove_from_yaml
from cleandns.exceptions import InvalidZoneFileError, EmptyZoneFileError, MissingNSRecordError
from cleandns.logger import Logger

ZONE_FILE_ENCODING = "utf-8"


@pytest.fixture
def logger():
    return Logger()


@pytest.fixture
def config():
    return DNSConfig()


def _parsed_args(config=None, files=None, add_from=None, remove_from=None):
    """Build a ParsedArgs for use in main() tests."""
    return ParsedArgs(
        config=config or DNSConfig(),
        files=files or [],
        add_from=add_from,
        remove_from=remove_from,
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


# ---------------------------------------------------------------------------
# remove_from_yaml — return codes and behaviour
# ---------------------------------------------------------------------------

def test_remove_from_yaml_returns_0_when_record_removed(tmp_path, forward_sample_zone_content, config, logger):
    zone_file = tmp_path / "example.com.zone"
    zone_file.write_text(forward_sample_zone_content, encoding=ZONE_FILE_ENCODING)

    yaml_file = tmp_path / "remove.yaml"
    yaml_file.write_text(
        "example.com:\n"
        "  - type: A\n"
        "    name: www\n"
        "    ttl: 3600\n"
        "    rdata: 192.168.1.10\n",
        encoding=ZONE_FILE_ENCODING,
    )

    with patch("cleandns.main.NamedConfParser.from_system", return_value={"example.com": zone_file}):
        assert remove_from_yaml(yaml_file, logger, config) == 0

    updated = zone_file.read_text(encoding=ZONE_FILE_ENCODING)
    assert "192.168.1.10" not in updated


def test_remove_from_yaml_returns_0_when_record_not_found(tmp_path, forward_sample_zone_content, config, logger):
    """Removing a non-existent record warns but does not fail."""
    zone_file = tmp_path / "example.com.zone"
    zone_file.write_text(forward_sample_zone_content, encoding=ZONE_FILE_ENCODING)

    yaml_file = tmp_path / "remove.yaml"
    yaml_file.write_text(
        "example.com:\n"
        "  - type: A\n"
        "    name: ghost\n"
        "    ttl: 3600\n"
        "    rdata: 10.0.0.1\n",
        encoding=ZONE_FILE_ENCODING,
    )

    with patch("cleandns.main.NamedConfParser.from_system", return_value={"example.com": zone_file}):
        assert remove_from_yaml(yaml_file, logger, config) == 0


def test_remove_from_yaml_returns_1_when_named_checkconf_fails(tmp_path, config, logger):
    from cleandns.exceptions import NamedConfNotFoundError
    yaml_file = tmp_path / "remove.yaml"
    yaml_file.write_text("example.com: []\n", encoding=ZONE_FILE_ENCODING)

    with patch("cleandns.main.NamedConfParser.from_system", side_effect=NamedConfNotFoundError("not found")):
        assert remove_from_yaml(yaml_file, logger, config) == 1


def test_remove_from_yaml_returns_1_for_unknown_zone(tmp_path, config, logger):
    yaml_file = tmp_path / "remove.yaml"
    yaml_file.write_text(
        "unknown.zone:\n"
        "  - type: A\n"
        "    name: host\n"
        "    ttl: 3600\n"
        "    rdata: 1.2.3.4\n",
        encoding=ZONE_FILE_ENCODING,
    )

    with patch("cleandns.main.NamedConfParser.from_system", return_value={}):
        assert remove_from_yaml(yaml_file, logger, config) == 1


def test_remove_from_yaml_dry_run_does_not_modify_zone_file(tmp_path, forward_sample_zone_content, logger):
    zone_file = tmp_path / "example.com.zone"
    zone_file.write_text(forward_sample_zone_content, encoding=ZONE_FILE_ENCODING)
    original = zone_file.read_text(encoding=ZONE_FILE_ENCODING)

    yaml_file = tmp_path / "remove.yaml"
    yaml_file.write_text(
        "example.com:\n"
        "  - type: A\n"
        "    name: www\n"
        "    ttl: 3600\n"
        "    rdata: 192.168.1.10\n",
        encoding=ZONE_FILE_ENCODING,
    )
    dry_config = DNSConfig(dry_run=True)

    with patch("cleandns.main.NamedConfParser.from_system", return_value={"example.com": zone_file}):
        assert remove_from_yaml(yaml_file, logger, dry_config) == 0

    assert zone_file.read_text(encoding=ZONE_FILE_ENCODING) == original


def test_remove_from_yaml_reload_calls_rndc_after_write(tmp_path, forward_sample_zone_content, logger):
    zone_file = tmp_path / "example.com.zone"
    zone_file.write_text(forward_sample_zone_content, encoding=ZONE_FILE_ENCODING)

    yaml_file = tmp_path / "remove.yaml"
    yaml_file.write_text(
        "example.com:\n"
        "  - type: A\n"
        "    name: www\n"
        "    ttl: 3600\n"
        "    rdata: 192.168.1.10\n",
        encoding=ZONE_FILE_ENCODING,
    )
    reload_config = DNSConfig(reload=True)

    with patch("cleandns.main.NamedConfParser.from_system", return_value={"example.com": zone_file}), \
         patch("cleandns.main.subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        result = remove_from_yaml(yaml_file, logger, reload_config)

    assert result == 0
    mock_run.assert_called_once()
    cmd = mock_run.call_args[0][0]
    assert cmd == ["rndc", "reload", "example.com"]


def test_main_routes_to_remove_from_yaml(tmp_path):
    yaml_file = tmp_path / "remove.yaml"
    yaml_file.touch()

    with patch("cleandns.main.ArgumentParser") as mock_cls, \
         patch("cleandns.main.remove_from_yaml", return_value=0) as mock_remove:
        mock_cls.return_value.parse_arguments.return_value = _parsed_args(remove_from=yaml_file)
        from cleandns.main import main
        assert main() == 0
        mock_remove.assert_called_once()


# ---------------------------------------------------------------------------
# --dedup-ip — integration via process_file
# ---------------------------------------------------------------------------

DEDUP_ZONE_CONTENT = (
    "$TTL 3600\n"
    "$ORIGIN example.com.\n"
    "@   IN  SOA ns1.example.com. admin.example.com. (\n"
    "        2023101001 ; serial\n"
    "        3600       ; refresh\n"
    "        1800       ; retry\n"
    "        604800     ; expire\n"
    "        86400 )    ; minimum\n"
    "@   IN  NS  ns1.example.com.\n"
    "@   IN  NS  ns2.example.com.\n"
    "host1   IN  A   192.168.1.10\n"
    "host2   IN  A   192.168.1.10\n"
    "host3   IN  A   192.168.1.20\n"
)


def test_process_file_dedup_ip_removes_user_selected_record(tmp_path, logger):
    """With dedup_ip=True in a TTY, the record the user discards is removed from the zone."""
    p = tmp_path / "example.com.zone"
    p.write_text(DEDUP_ZONE_CONTENT, encoding="utf-8")
    config = DNSConfig(dedup_ip=True, no_backup=True)

    # TTY: user keeps index 0 (host1), so host2 (index 1) should be removed.
    with patch("sys.stdout") as mock_stdout, \
         patch("builtins.input", return_value="0"), \
         patch("builtins.print"):
        mock_stdout.isatty.return_value = True
        result = process_file(p, logger, config)

    assert result == 0
    content = p.read_text(encoding="utf-8")
    assert "host1" in content
    assert "host2" not in content
    assert "host3" in content  # different IP, untouched


def test_process_file_dedup_ip_non_tty_keeps_all_records(tmp_path, logger):
    """With dedup_ip=True in a non-interactive environment, all records are preserved."""
    p = tmp_path / "example.com.zone"
    p.write_text(DEDUP_ZONE_CONTENT, encoding="utf-8")
    config = DNSConfig(dedup_ip=True, no_backup=True)

    with patch("sys.stdout") as mock_stdout:
        mock_stdout.isatty.return_value = False
        result = process_file(p, logger, config)

    assert result == 0
    content = p.read_text(encoding="utf-8")
    assert "host1" in content
    assert "host2" in content


def test_process_file_dedup_ip_false_skips_dedup(tmp_path, logger):
    """Without --dedup-ip, IP duplicates are left untouched (handled by remove_duplicates only)."""
    p = tmp_path / "example.com.zone"
    p.write_text(DEDUP_ZONE_CONTENT, encoding="utf-8")
    config = DNSConfig(dedup_ip=False, no_backup=True)

    with patch("builtins.input") as mock_input:
        result = process_file(p, logger, config)

    assert result == 0
    mock_input.assert_not_called()


def test_process_file_dedup_ip_enter_keeps_all(tmp_path, logger):
    """With dedup_ip=True in a TTY, pressing Enter for a group keeps all records."""
    p = tmp_path / "example.com.zone"
    p.write_text(DEDUP_ZONE_CONTENT, encoding="utf-8")
    config = DNSConfig(dedup_ip=True, no_backup=True)

    with patch("sys.stdout") as mock_stdout, \
         patch("builtins.input", return_value=""), \
         patch("builtins.print"):
        mock_stdout.isatty.return_value = True
        result = process_file(p, logger, config)

    assert result == 0
    content = p.read_text(encoding="utf-8")
    assert "host1" in content
    assert "host2" in content


def test_process_file_dedup_ip_zone_changes_reflect_removed_records(tmp_path, logger):
    """Records removed via --dedup-ip must appear in ZoneChanges.records_removed."""
    from cleandns.dns_file import DNSFile
    from cleandns.deduplication import find_ip_duplicates, prompt_deduplication

    p = tmp_path / "example.com.zone"
    p.write_text(DEDUP_ZONE_CONTENT, encoding="utf-8")
    config = DNSConfig(dedup_ip=True, no_backup=True)

    dns_file = DNSFile(p, config)
    dns_file.remove_duplicates()

    with patch("sys.stdout") as mock_stdout, \
         patch("builtins.input", return_value="0"), \
         patch("builtins.print"):
        mock_stdout.isatty.return_value = True
        groups = find_ip_duplicates(dns_file.records)
        to_remove = prompt_deduplication(groups, logger)
        for record in to_remove:
            dns_file.remove_record(record)

    changes = dns_file.save()
    assert changes.has_changes is True
    assert len(changes.records_removed) == 1
    assert changes.records_removed[0].name in ("host1", "host2")
