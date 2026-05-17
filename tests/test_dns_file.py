import pytest
from cleandns.config import DNSConfig
from cleandns.dns_file import DNSFile
from cleandns.exceptions import InvalidZoneFileError, EmptyZoneFileError, MissingNSRecordError
from cleandns.exceptions import MissingSOARecordError
from cleandns.record_types import RecordType

ZONE_FILE_ENCODING = "utf-8"

# --- Fixtures for Sample Data ---

@pytest.fixture
def zone_file(tmp_path, forward_sample_zone_content):
    """
    Creates a temporary valid zone file.
    """
    p = tmp_path / "example.com.zone"
    # We extend the shared fixture with the CNAME record specific to these tests
    p.write_text(forward_sample_zone_content, encoding=ZONE_FILE_ENCODING)
    return p

# --- Parsing Tests ---

def test_load_valid_zone(zone_file, default_config):
    assert zone_file.exists()
    dns = DNSFile(zone_file, default_config)

    assert dns.ttl == 3600
    assert dns.origin == "example.com."
    assert dns.soa_record is not None
    assert dns.soa_record.serial == 2023101001
    assert dns.soa_record.mname == "ns1"

    # Check record counts
    assert len(dns.records[RecordType.A]) == 2
    assert len(dns.records[RecordType.NS]) == 2
    assert len(dns.records[RecordType.CNAME]) == 1

def test_missing_soa_raises_exception(tmp_path, sample_ttl_line, sample_origin_line, sample_ns_block, simple_sample_a_records_block, default_config):
    content = (
        f"{sample_ttl_line}\n"
        f"{sample_origin_line}\n"
        f"{sample_ns_block}\n"
        f"{simple_sample_a_records_block}\n"
    )
    p = tmp_path / "no_soa.zone"
    p.write_text(content, encoding=ZONE_FILE_ENCODING)

    with pytest.raises(MissingSOARecordError):
        DNSFile(p, default_config)

def test_empty_file_raises_exception(tmp_path, default_config):
    """Blank file must raise EmptyZoneFileError, not the generic MissingSOARecordError."""
    p = tmp_path / "empty.zone"
    p.write_text("", encoding=ZONE_FILE_ENCODING)

    with pytest.raises(EmptyZoneFileError):
        DNSFile(p, default_config)

def test_invalid_ttl_raises_value_error(tmp_path, sample_soa_block, sample_origin_line, default_config):
    """Non-numeric $TTL must raise InvalidZoneFileError."""
    content = (
        "$TTL INVALID\n"
        f"{sample_origin_line}\n"
        f"{sample_soa_block}\n"
    )
    p = tmp_path / "bad_ttl.zone"
    p.write_text(content, encoding=ZONE_FILE_ENCODING)

    with pytest.raises(InvalidZoneFileError, match="Invalid TTL"):
        DNSFile(p, default_config)

def test_ttl_string_format_is_parsed(tmp_path, sample_soa_block, sample_origin_line, sample_ns_block, default_config):
    """$TTL in DNS string notation (e.g. 1h) must be converted to seconds."""
    content = (
        "$TTL 1h\n"
        f"{sample_origin_line}\n"
        f"{sample_soa_block}\n"
        f"{sample_ns_block}\n"
    )
    p = tmp_path / "string_ttl.zone"
    p.write_text(content, encoding=ZONE_FILE_ENCODING)

    dns = DNSFile(p, default_config)
    assert dns.ttl == 3600

def test_missing_ttl_directive_is_allowed(tmp_path, sample_soa_block, sample_origin_line, sample_ns_block, default_config):
    """A zone file without a $TTL directive must parse successfully with ttl=None."""
    content = (
        f"{sample_origin_line}\n"
        f"{sample_soa_block}\n"
        f"{sample_ns_block}\n"
    )
    p = tmp_path / "no_ttl.zone"
    p.write_text(content, encoding=ZONE_FILE_ENCODING)

    dns = DNSFile(p, default_config)
    assert dns.ttl is None

def test_zone_without_ns_raises_missing_ns_record(tmp_path, sample_ttl_line, sample_origin_line, sample_soa_block, default_config):
    """Zone without NS records must raise MissingNSRecordError, not the generic MissingSOARecordError."""
    content = (
        f"{sample_ttl_line}\n"
        f"{sample_origin_line}\n"
        f"{sample_soa_block}\n"
    )
    p = tmp_path / "soa_only.zone"
    p.write_text(content, encoding=ZONE_FILE_ENCODING)

    with pytest.raises(MissingNSRecordError):
        DNSFile(p, default_config)

def test_comments_only_file_raises_missing_soa(tmp_path, default_config):
    """A file containing only comments must raise MissingSOARecordError, not EmptyZoneFileError."""
    p = tmp_path / "comments.zone"
    p.write_text("; this is just a comment\n", encoding=ZONE_FILE_ENCODING)

    with pytest.raises(MissingSOARecordError):
        DNSFile(p, default_config)

# --- Logic Tests ---

def test_save_does_not_increment_serial_when_unmodified(zone_file, default_config):
    dns = DNSFile(zone_file, default_config)
    original_serial = dns.soa_record.serial
    assert dns.modified is False

    dns.save()

    assert dns.soa_record.serial == original_serial

def test_remove_duplicates(zone_file, default_config):
    """remove_duplicates() must shrink the record list and set modified=True."""
    dns = DNSFile(zone_file, default_config)
    records = dns.records[RecordType.A]
    initial_count = len(records)
    records.append(records[0])

    dns.remove_duplicates()

    assert len(dns.records[RecordType.A]) == initial_count
    assert dns.modified is True

def test_remove_duplicates_no_change_leaves_modified_false(zone_file, default_config):
    """remove_duplicates() on a duplicate-free zone must not set modified=True."""
    dns = DNSFile(zone_file, default_config)
    dns.remove_duplicates()
    assert dns.modified is False

def test_sort_no_change_leaves_modified_false(zone_file, default_config):
    """sort() on an already-sorted zone must not set modified=True."""
    dns = DNSFile(zone_file, default_config)
    dns.sort()           # bring into sorted order
    dns.modified = False  # reset
    dns.sort()           # second pass must be a no-op
    assert dns.modified is False

def test_sort_a_records(tmp_path, complex_forward_zone_content, expected_sorted_a_names, default_config):
    p = tmp_path / "unsorted.zone"
    p.write_text(complex_forward_zone_content, encoding=ZONE_FILE_ENCODING)

    dns = DNSFile(p, default_config)
    dns.sort()

    records = dns.records[RecordType.A]
    # Normalize names by stripping trailing dots for a robust comparison
    assert [record.name.rstrip('.') for record in records] == [n.rstrip('.') for n in expected_sorted_a_names]
    assert dns.modified is True

def test_sort_ptr_records(tmp_path, complex_reverse_zone_content, expected_sorted_ptr_names, default_config):
    content = complex_reverse_zone_content
    p = tmp_path / "unsorted.zone"
    p.write_text(content, encoding=ZONE_FILE_ENCODING)

    dns = DNSFile(p, default_config)
    dns.sort()

    records = dns.records[RecordType.PTR]
    assert [record.name.rstrip('.') for record in records] == [n.rstrip('.') for n in expected_sorted_ptr_names]
    assert dns.modified is True

# --- Config Flag Output Tests ---

@pytest.mark.parametrize("flag,directive", [
    ("omit_ttl",    "$TTL"),
    ("omit_origin", "$ORIGIN"),
])
def test_directive_omitted_when_flag_set(zone_file, flag, directive):
    """Setting an omit_* flag must remove the corresponding directive from the output file."""
    config = DNSConfig(**{flag: True})
    dns = DNSFile(zone_file, config)
    dns.modified = True
    dns.save()
    assert directive not in zone_file.read_text(encoding=ZONE_FILE_ENCODING)

def test_omit_record_ttl_excluded_from_output(zone_file):
    """omit_record_ttl=True must omit the TTL column from all record string representations."""
    config = DNSConfig(omit_origin=False, human_readable=False, omit_ttl=False, omit_record_ttl=True)
    dns = DNSFile(zone_file, config)
    for records in dns.records.values():
        for record in records:
            assert str(record.ttl) not in str(record)

# --- Integration Tests ---

def test_full_pipeline_round_trip(tmp_path, complex_forward_zone_content, expected_sorted_a_names, default_config):
    """Full pipeline: load → remove_duplicates → sort → save → reload must produce a valid, sorted, serial-bumped zone."""
    p = tmp_path / "example.com.zone"
    p.write_text(complex_forward_zone_content, encoding=ZONE_FILE_ENCODING)

    # Run the pipeline
    dns = DNSFile(p, default_config)
    original_serial = dns.soa_record.serial
    dns.remove_duplicates()
    dns.sort()
    dns.save()

    # Reload from disk — verifies the saved file is a valid, parseable zone
    reloaded = DNSFile(p, default_config)

    assert reloaded.soa_record.serial == original_serial + 1
    assert [r.name.rstrip(".") for r in reloaded.records[RecordType.A]] == [n.rstrip(".") for n in expected_sorted_a_names]

# --- File I/O Tests ---

def test_save_creates_backup_and_updates_file(zone_file, default_config):
    original_content = zone_file.read_text(encoding=ZONE_FILE_ENCODING)
    dns = DNSFile(zone_file, default_config)
    original_serial = dns.soa_record.serial

    # Mark as modified to trigger serial update and file write
    dns.modified = True
    dns.save()

    # 1. Verify content was updated (serial incremented)
    new_content = zone_file.read_text(encoding=ZONE_FILE_ENCODING)
    assert str(original_serial + 1) in new_content

    # 2. Verify backup file was created
    # Backup format is filename.YYYY-MM-DD_HH-MM-SS
    # We look for any file starting with the original name but longer
    backups = [f for f in zone_file.parent.iterdir() if f.name.startswith(zone_file.name) and f != zone_file]
    assert len(backups) > 0
    # Verify backup content matches original state
    assert backups[0].read_text(encoding=ZONE_FILE_ENCODING) == original_content
