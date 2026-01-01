import pytest
from pathlib import Path
from cleandns.dns_file import DNSFile
from cleandns.exceptions import MissingSOArecord
from cleandns.record_types import RecordType
from tests.conftest import ZONE_FILE_ENCODING

# --- Fixtures for Sample Data ---

@pytest.fixture
def zone_file(tmp_path, forward_sample_zone_content):
    """Creates a temporary valid zone file."""
    p = tmp_path / "example.com.zone"
    # We extend the shared fixture with the CNAME record specific to these tests
    p.write_text(forward_sample_zone_content, encoding=ZONE_FILE_ENCODING)
    return p

# --- Parsing Tests ---

def test_load_valid_zone(zone_file):
    """Test that a valid zone file is parsed correctly."""
    assert zone_file.exists()
    dns = DNSFile(zone_file)
    
    assert dns.ttl == 3600
    assert dns.soa_record is not None
    assert dns.soa_record.serial == 2023101001
    assert dns.soa_record.mname == "ns1.example.com."
    
    # Check record counts
    assert len(dns.records[RecordType.A]) == 2
    assert len(dns.records[RecordType.NS]) == 2
    assert len(dns.records[RecordType.CNAME]) == 1

def test_missing_soa_raises_exception(tmp_path, sample_ttl_line, sample_ns_block, simple_sample_a_records_block):
    """Test that a file missing an SOA record raises MissingSOArecord."""
    content = (
        f"{sample_ttl_line}\n"
        f"{sample_ns_block}\n"
        f"{simple_sample_a_records_block}\n"
    )
    p = tmp_path / "no_soa.zone"
    p.write_text(content, encoding=ZONE_FILE_ENCODING)
    
    with pytest.raises(MissingSOArecord):
        DNSFile(p)

def test_empty_file_raises_exception(tmp_path):
    """Test that a completely empty file raises MissingSOArecord."""
    p = tmp_path / "empty.zone"
    p.write_text("", encoding=ZONE_FILE_ENCODING)
    
    with pytest.raises(MissingSOArecord):
        DNSFile(p)

def test_invalid_ttl_raises_value_error(tmp_path, sample_soa_block):
    """Test that a file with an invalid TTL raises ValueError."""
    content = (
        "$TTL INVALID\n"
        f"{sample_soa_block}\n"
    )
    p = tmp_path / "bad_ttl.zone"
    p.write_text(content, encoding=ZONE_FILE_ENCODING)
    
    with pytest.raises(ValueError, match="Invalid TTL"):
        DNSFile(p)

# --- Logic Tests ---

def test_increment_serial(zone_file):
    """Test that the serial number is incremented correctly."""
    dns = DNSFile(zone_file)
    old_serial = dns.soa_record.serial
    dns.increment_serial()
    assert dns.soa_record.serial == old_serial + 1

def test_remove_duplicates(tmp_path, sample_ttl_line, sample_soa_block, sample_ns_block, simple_sample_a_records_block):
    """Test that duplicate records are removed and modified flag is set."""
    content = (
        f"{sample_ttl_line}\n"
        f"{sample_soa_block}\n"
        f"{sample_ns_block}\n"
        f"{simple_sample_a_records_block}\n"
    )
    p = tmp_path / "dup.zone"
    p.write_text(content, encoding=ZONE_FILE_ENCODING)
    
    dns = DNSFile(p)

    # Manually add a duplicate record
    records = dns.records[RecordType.A]
    initial_count = len(records)
    records.append(records[0])

    dns.remove_duplicates()

    assert len(dns.records[RecordType.A]) == initial_count
    assert dns.modified is True

def test_sort_a_records(tmp_path, complex_forward_zone_content, expected_sorted_a_names):
    """Test that A records are sorted alphabetically."""
    content = complex_forward_zone_content
    p = tmp_path / "unsorted.zone"
    p.write_text(content, encoding=ZONE_FILE_ENCODING)
    
    dns = DNSFile(p)
    dns.sort()
    
    records = dns.records[RecordType.A]
    # Normalize names by stripping trailing dots for a robust comparison
    assert [record.name.rstrip('.') for record in records] == [n.rstrip('.') for n in expected_sorted_a_names]
    assert dns.modified is True

def test_sort_ptr_records(tmp_path, complex_reverse_zone_content, expected_sorted_ptr_names):
    """Test that PTR records are sorted numerically."""
    content = complex_reverse_zone_content
    p = tmp_path / "unsorted.zone"
    p.write_text(content, encoding=ZONE_FILE_ENCODING)

    dns = DNSFile(p)
    dns.sort()

    records = dns.records[RecordType.PTR]
    assert [record.name.rstrip('.') for record in records] == [n.rstrip('.') for n in expected_sorted_ptr_names]
    assert dns.modified is True

def test_sort_is_case_insensitive(tmp_path, sample_ttl_line, sample_ns_block, sample_soa_block):
    """Test that sorting ignores case (e.g., 'www' and 'WWW' are treated the same)."""
    content = (
        f"{sample_ttl_line}\n"
        f"{sample_soa_block}\n"
        f"{sample_ns_block}\n"
        "zzz IN A 1.1.1.1\n"
        "AAA IN A 2.2.2.2\n"
        "bbb IN A 3.3.3.3\n"
    )
    p = tmp_path / "case.zone"
    p.write_text(content, encoding=ZONE_FILE_ENCODING)
    
    dns = DNSFile(p)
    dns.sort()
    
    names = [r.name.lower() for r in dns.records[RecordType.A]]
    assert names == ["aaa", "bbb", "zzz"]

# --- File I/O Tests ---

def test_save_creates_backup_and_updates_file(zone_file):
    """Test that saving updates the file content and creates a backup."""
    original_content = zone_file.read_text(encoding=ZONE_FILE_ENCODING)
    dns = DNSFile(zone_file)
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
