import pytest
from cleandns.config import DNSConfig
from cleandns.dns_file import DNSFile, ZoneChanges
from cleandns.exceptions import InvalidZoneFileError, EmptyZoneFileError, MissingNSRecordError
from cleandns.exceptions import MissingSOARecordError, UnsupportedRecordTypeError
from cleandns.record_types import ARecord, DNSClass, RecordType

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
    assert len(dns.records[RecordType.AAAA]) == 2
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

def test_unsupported_record_type_raises_error(tmp_path, sample_ttl_line, sample_origin_line, sample_soa_block, sample_ns_block, default_config):
    """A zone file containing an unsupported record type must raise UnsupportedRecordTypeError."""
    content = (
        f"{sample_ttl_line}\n"
        f"{sample_origin_line}\n"
        f"{sample_soa_block}\n"
        f"{sample_ns_block}\n"
        '@   IN  CAA 0 issue "ca.example.com"\n'
    )
    p = tmp_path / "unsupported.zone"
    p.write_text(content, encoding=ZONE_FILE_ENCODING)

    with pytest.raises(UnsupportedRecordTypeError):
        DNSFile(p, default_config)

def test_unsupported_record_type_error_message_includes_type_and_count(tmp_path, sample_ttl_line, sample_origin_line, sample_soa_block, sample_ns_block, default_config):
    """UnsupportedRecordTypeError message must include the type name and the occurrence count."""
    content = (
        f"{sample_ttl_line}\n"
        f"{sample_origin_line}\n"
        f"{sample_soa_block}\n"
        f"{sample_ns_block}\n"
        '@   IN  CAA 0 issue "ca.example.com"\n'
        '@   IN  CAA 0 issuewild "ca.example.com"\n'
    )
    p = tmp_path / "unsupported.zone"
    p.write_text(content, encoding=ZONE_FILE_ENCODING)

    with pytest.raises(UnsupportedRecordTypeError, match=r"CAA \(2\)"):
        DNSFile(p, default_config)

def test_multiple_unsupported_record_types_all_reported(tmp_path, sample_ttl_line, sample_origin_line, sample_soa_block, sample_ns_block, default_config):
    """All distinct unsupported record types must appear in one error, not just the first encountered."""
    content = (
        f"{sample_ttl_line}\n"
        f"{sample_origin_line}\n"
        f"{sample_soa_block}\n"
        f"{sample_ns_block}\n"
        '@   IN  CAA  0 issue "ca.example.com"\n'
        '@   IN  SSHFP 1 1 de3487a5c98af0ea64e14b6e43b28b97f5e50d72\n'
    )
    p = tmp_path / "unsupported.zone"
    p.write_text(content, encoding=ZONE_FILE_ENCODING)

    with pytest.raises(UnsupportedRecordTypeError) as exc_info:
        DNSFile(p, default_config)

    message = str(exc_info.value)
    assert "CAA" in message
    assert "SSHFP" in message

# --- MX and TXT record tests ---

def test_load_zone_with_mx_records(tmp_path, mx_zone_content, default_config):
    """Zone file containing MX records must parse without error and expose them via RecordType.MX."""
    p = tmp_path / "mx.zone"
    p.write_text(mx_zone_content, encoding=ZONE_FILE_ENCODING)

    dns_file = DNSFile(p, default_config)

    assert RecordType.MX in dns_file.records
    assert len(dns_file.records[RecordType.MX]) == 2

def test_load_zone_with_txt_records(tmp_path, txt_zone_content, default_config):
    """Zone file containing TXT records must parse without error and expose them via RecordType.TXT."""
    p = tmp_path / "txt.zone"
    p.write_text(txt_zone_content, encoding=ZONE_FILE_ENCODING)

    dns_file = DNSFile(p, default_config)

    assert RecordType.TXT in dns_file.records
    assert len(dns_file.records[RecordType.TXT]) == 1

def test_sort_mx_records(tmp_path, complex_mx_zone_content, expected_sorted_mx_priorities, expected_sorted_mx_exchanges, default_config):
    """sort() must order MX records by preference ascending, with exchange name as the tiebreak."""
    p = tmp_path / "mx_unsorted.zone"
    p.write_text(complex_mx_zone_content, encoding=ZONE_FILE_ENCODING)

    dns_file = DNSFile(p, default_config)
    dns_file.sort()

    records = dns_file.records[RecordType.MX]
    assert [int(r.rdata.split()[0]) for r in records] == expected_sorted_mx_priorities
    assert [r.rdata.split(None, 1)[1] for r in records] == expected_sorted_mx_exchanges

def test_full_pipeline_round_trip_with_mx_and_txt(tmp_path, sample_ttl_line, sample_origin_line, sample_soa_block, sample_ns_block, default_config):
    """Full pipeline with MX and TXT records must produce a valid, reloadable zone."""
    content = (
        f"{sample_ttl_line}\n"
        f"{sample_origin_line}\n"
        f"{sample_soa_block}\n\n"
        f"{sample_ns_block}\n"
        "@   IN  MX  20 mail2.example.com.\n"
        "@   IN  MX  10 mail1.example.com.\n"
        '@   IN  TXT "v=spf1 include:example.com ~all"\n'
    )
    p = tmp_path / "mixed.zone"
    p.write_text(content, encoding=ZONE_FILE_ENCODING)

    dns_file = DNSFile(p, default_config)
    assert dns_file.soa_record is not None
    original_serial = dns_file.soa_record.serial

    dns_file.remove_duplicates()
    dns_file.sort()
    dns_file.save()

    reloaded = DNSFile(p, default_config)
    assert reloaded.soa_record is not None
    assert reloaded.soa_record.serial == original_serial + 1
    assert len(reloaded.records[RecordType.MX]) == 2
    assert len(reloaded.records[RecordType.TXT]) == 1
    # MX must be sorted: preference 10 before 20
    mx = reloaded.records[RecordType.MX]
    assert int(mx[0].rdata.split()[0]) == 10
    assert int(mx[1].rdata.split()[0]) == 20

# --- Logic Tests ---

def test_save_does_not_increment_serial_when_unmodified(zone_file, default_config):
    dns = DNSFile(zone_file, default_config)
    assert dns.soa_record is not None
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

# --- add_record Tests ---

def test_add_record_increases_count_and_sets_modified(zone_file, default_config):
    dns = DNSFile(zone_file, default_config)
    initial_count = len(dns.records[RecordType.A])
    assert dns.modified is False

    new_record = ARecord(name="newhost", ttl=3600, class_=DNSClass.IN, type=RecordType.A, rdata="10.0.0.99", omit_ttl=False)
    dns.add_record(new_record)

    assert len(dns.records[RecordType.A]) == initial_count + 1
    assert dns.modified is True


def test_add_record_aligns_omit_ttl_with_config(zone_file):
    config = DNSConfig(omit_record_ttl=True)
    dns = DNSFile(zone_file, config)

    record = ARecord(name="newhost", ttl=3600, class_=DNSClass.IN, type=RecordType.A, rdata="10.0.0.99", omit_ttl=False)
    dns.add_record(record)

    assert record.omit_ttl is True


def test_add_duplicate_record_is_removed_by_remove_duplicates(zone_file, default_config):
    """add_record followed by remove_duplicates must be idempotent."""
    dns = DNSFile(zone_file, default_config)
    existing = dns.records[RecordType.A][0]
    initial_count = len(dns.records[RecordType.A])

    duplicate = ARecord(
        name=existing.name, ttl=existing.ttl, class_=DNSClass.IN,
        type=RecordType.A, rdata=existing.rdata, omit_ttl=False,
    )
    dns.add_record(duplicate)
    assert len(dns.records[RecordType.A]) == initial_count + 1

    dns.remove_duplicates()
    assert len(dns.records[RecordType.A]) == initial_count


# --- Config Flag Output Tests ---

@pytest.mark.parametrize("flag,directive", [
    ("omit_ttl",    "$TTL"),
    ("omit_origin", "$ORIGIN"),
])
def test_directive_omitted_when_flag_set(zone_file, flag, directive):
    """Setting an omit_* flag must remove the corresponding directive from the output file."""
    config = DNSConfig(**{flag: True})
    dns = DNSFile(zone_file, config)
    # Add a record so that save() has a genuine modification to write
    dns.add_record(ARecord(name="probe", ttl=3600, class_=DNSClass.IN, type=RecordType.A, rdata="10.255.255.1", omit_ttl=False))
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
    assert dns.soa_record is not None
    original_serial = dns.soa_record.serial
    dns.remove_duplicates()
    dns.sort()
    dns.save()

    # Reload from disk — verifies the saved file is a valid, parseable zone
    reloaded = DNSFile(p, default_config)
    assert reloaded.soa_record is not None

    assert reloaded.soa_record.serial == original_serial + 1
    assert [r.name.rstrip(".") for r in reloaded.records[RecordType.A]] == [n.rstrip(".") for n in expected_sorted_a_names]

# --- File I/O Tests ---

def test_save_creates_backup_and_updates_file(zone_file, default_config):
    original_content = zone_file.read_text(encoding=ZONE_FILE_ENCODING)
    dns = DNSFile(zone_file, default_config)
    assert dns.soa_record is not None
    original_serial = dns.soa_record.serial

    # Add a record to trigger a genuine modification so the file is written
    new_record = ARecord(name="probe", ttl=3600, class_=DNSClass.IN, type=RecordType.A, rdata="10.99.99.1", omit_ttl=False)
    dns.add_record(new_record)
    dns.save()

    # 1. Verify content was updated (serial incremented)
    new_content = zone_file.read_text(encoding=ZONE_FILE_ENCODING)
    assert str(original_serial + 1) in new_content

    # 2. Verify backup was created in the default 'backups/' subdirectory
    backup_dir = zone_file.parent / "backups"
    assert backup_dir.is_dir()
    backups = list(backup_dir.iterdir())
    assert len(backups) == 1
    assert backups[0].name.startswith(zone_file.name)
    # Verify backup content matches original state
    assert backups[0].read_text(encoding=ZONE_FILE_ENCODING) == original_content


# ---------------------------------------------------------------------------
# ZoneChanges — return value of save()
# ---------------------------------------------------------------------------

def test_save_returns_zone_changes(zone_file, default_config):
    """save() must always return a ZoneChanges instance."""
    dns = DNSFile(zone_file, default_config)
    result = dns.save()
    assert isinstance(result, ZoneChanges)


def test_zone_changes_has_changes_false_when_unmodified(zone_file, default_config):
    """ZoneChanges.has_changes must be False when no modifications were made."""
    dns = DNSFile(zone_file, default_config)
    changes = dns.save()
    assert changes.has_changes is False


def test_zone_changes_records_added(zone_file, default_config):
    """ZoneChanges.records_added must contain every record passed to add_record()."""
    dns = DNSFile(zone_file, default_config)
    r1 = ARecord(name="host1", ttl=3600, class_=DNSClass.IN, type=RecordType.A, rdata="1.2.3.4", omit_ttl=False)
    r2 = ARecord(name="host2", ttl=3600, class_=DNSClass.IN, type=RecordType.A, rdata="1.2.3.5", omit_ttl=False)
    dns.add_record(r1)
    dns.add_record(r2)
    changes = dns.save()

    assert changes.has_changes is True
    assert len(changes.records_added) == 2
    assert r1 in changes.records_added
    assert r2 in changes.records_added


def test_zone_changes_duplicates_removed(zone_file, default_config):
    """ZoneChanges.duplicates_removed must list the records that were dropped."""
    dns = DNSFile(zone_file, default_config)
    existing = dns.records[RecordType.A][0]
    duplicate = ARecord(
        name=existing.name, ttl=existing.ttl, class_=DNSClass.IN,
        type=RecordType.A, rdata=existing.rdata, omit_ttl=False,
    )
    # Directly append so _records_added doesn't inflate the count
    dns.records[RecordType.A].append(duplicate)
    dns.modified = True  # force save to compute serial_after correctly
    dns.remove_duplicates()
    changes = dns.save()

    assert changes.has_changes is True
    assert len(changes.duplicates_removed) == 1


def test_zone_changes_was_reordered(tmp_path, complex_forward_zone_content, default_config):
    """ZoneChanges.was_reordered must be True when sort() changes record order."""
    p = tmp_path / "unsorted.zone"
    p.write_text(complex_forward_zone_content, encoding=ZONE_FILE_ENCODING)
    dns = DNSFile(p, default_config)
    dns.sort()
    changes = dns.save()

    assert changes.was_reordered is True
    assert changes.has_changes is True


def test_zone_changes_serial_fields(zone_file, default_config):
    """serial_before and serial_after must reflect the SOA serial increment."""
    dns = DNSFile(zone_file, default_config)
    assert dns.soa_record is not None
    original_serial = dns.soa_record.serial

    dns.add_record(ARecord(name="x", ttl=3600, class_=DNSClass.IN, type=RecordType.A, rdata="9.9.9.9", omit_ttl=False))
    changes = dns.save()

    assert changes.serial_before == original_serial
    assert changes.serial_after == original_serial + 1


def test_zone_changes_serial_unchanged_when_unmodified(zone_file, default_config):
    """When nothing was changed serial_before must equal serial_after."""
    dns = DNSFile(zone_file, default_config)
    changes = dns.save()
    assert changes.serial_before == changes.serial_after


# ---------------------------------------------------------------------------
# Dry-run mode
# ---------------------------------------------------------------------------

def test_dry_run_does_not_write_file(zone_file):
    """With dry_run=True save() must not modify the zone file on disk."""
    original_content = zone_file.read_text(encoding=ZONE_FILE_ENCODING)
    config = DNSConfig(dry_run=True)
    dns = DNSFile(zone_file, config)
    dns.add_record(ARecord(name="newhost", ttl=3600, class_=DNSClass.IN, type=RecordType.A, rdata="10.0.0.1", omit_ttl=False))
    dns.sort()
    dns.save()

    assert zone_file.read_text(encoding=ZONE_FILE_ENCODING) == original_content


def test_dry_run_creates_no_backup(zone_file):
    """With dry_run=True no backup file or backup directory must be created."""
    config = DNSConfig(dry_run=True)
    dns = DNSFile(zone_file, config)
    dns.add_record(ARecord(name="newhost", ttl=3600, class_=DNSClass.IN, type=RecordType.A, rdata="10.0.0.1", omit_ttl=False))
    dns.save()

    assert not (zone_file.parent / "backups").exists()


def test_dry_run_still_returns_zone_changes_with_has_changes(zone_file):
    """With dry_run=True ZoneChanges must still report what would have changed."""
    config = DNSConfig(dry_run=True)
    dns = DNSFile(zone_file, config)
    dns.add_record(ARecord(name="newhost", ttl=3600, class_=DNSClass.IN, type=RecordType.A, rdata="10.0.0.1", omit_ttl=False))
    changes = dns.save()

    assert changes.has_changes is True
    assert len(changes.records_added) == 1
    assert changes.serial_after == changes.serial_before + 1


def test_dry_run_does_not_increment_serial_in_memory(zone_file):
    """With dry_run=True the in-memory SOA serial must not be incremented."""
    config = DNSConfig(dry_run=True)
    dns = DNSFile(zone_file, config)
    assert dns.soa_record is not None
    original_serial = dns.soa_record.serial

    dns.add_record(ARecord(name="x", ttl=3600, class_=DNSClass.IN, type=RecordType.A, rdata="1.1.1.1", omit_ttl=False))
    dns.save()

    assert dns.soa_record.serial == original_serial


# ---------------------------------------------------------------------------
# Backup configuration
# ---------------------------------------------------------------------------

def test_backup_goes_to_backups_subdir_by_default(zone_file, default_config):
    """Default backup location must be a 'backups/' subdirectory next to the zone file."""
    dns = DNSFile(zone_file, default_config)
    dns.add_record(ARecord(name="probe", ttl=3600, class_=DNSClass.IN, type=RecordType.A, rdata="10.1.2.3", omit_ttl=False))
    dns.save()

    backup_dir = zone_file.parent / "backups"
    assert backup_dir.is_dir()
    backups = list(backup_dir.iterdir())
    assert len(backups) == 1
    assert backups[0].name.startswith(zone_file.name)


def test_backup_dir_is_created_automatically(zone_file, default_config):
    """save() must create the backup directory if it does not yet exist."""
    backup_dir = zone_file.parent / "backups"
    assert not backup_dir.exists()

    dns = DNSFile(zone_file, default_config)
    dns.add_record(ARecord(name="probe", ttl=3600, class_=DNSClass.IN, type=RecordType.A, rdata="10.1.2.3", omit_ttl=False))
    dns.save()

    assert backup_dir.is_dir()


def test_custom_backup_dir_is_used(tmp_path, zone_file, default_config):
    """With backup_dir set, backups must go to the specified directory."""
    custom_dir = tmp_path / "my_backups"
    assert not custom_dir.exists()

    config = DNSConfig(backup_dir=custom_dir)
    dns = DNSFile(zone_file, config)
    dns.add_record(ARecord(name="probe", ttl=3600, class_=DNSClass.IN, type=RecordType.A, rdata="10.1.2.3", omit_ttl=False))
    dns.save()

    assert custom_dir.is_dir()
    backups = list(custom_dir.iterdir())
    assert len(backups) == 1
    assert backups[0].name.startswith(zone_file.name)
    # Default 'backups/' subdirectory must NOT have been created
    assert not (zone_file.parent / "backups").exists()


def test_no_backup_skips_backup_entirely(zone_file):
    """With no_backup=True the zone file is updated but no backup is created."""
    config = DNSConfig(no_backup=True)
    dns = DNSFile(zone_file, config)
    assert dns.soa_record is not None
    original_serial = dns.soa_record.serial

    dns.add_record(ARecord(name="probe", ttl=3600, class_=DNSClass.IN, type=RecordType.A, rdata="10.1.2.3", omit_ttl=False))
    dns.save()

    # Zone file was updated
    assert str(original_serial + 1) in zone_file.read_text(encoding=ZONE_FILE_ENCODING)
    # No backup directory was created
    assert not (zone_file.parent / "backups").exists()


def test_no_backup_does_not_create_any_extra_files(zone_file):
    """With no_backup=True, no files other than the zone file itself must appear."""
    config = DNSConfig(no_backup=True)
    files_before = set(zone_file.parent.iterdir())

    dns = DNSFile(zone_file, config)
    dns.add_record(ARecord(name="probe", ttl=3600, class_=DNSClass.IN, type=RecordType.A, rdata="10.1.2.3", omit_ttl=False))
    dns.save()

    files_after = set(zone_file.parent.iterdir())
    # Only the zone file itself should be present — no new files or directories
    assert files_after == files_before


def test_backup_dir_creation_failure_raises_before_write(zone_file):
    """If the backup directory cannot be created, save() must raise OSError
    before the zone file is modified."""
    original_content = zone_file.read_text(encoding=ZONE_FILE_ENCODING)

    # Place a regular file where the backup directory should be created —
    # mkdir will raise NotADirectoryError (a subclass of OSError).
    blocker = zone_file.parent / "backups"
    blocker.write_text("I am a file, not a directory", encoding=ZONE_FILE_ENCODING)

    dns = DNSFile(zone_file, default_config := DNSConfig())
    dns.add_record(ARecord(name="probe", ttl=3600, class_=DNSClass.IN, type=RecordType.A, rdata="10.1.2.3", omit_ttl=False))

    with pytest.raises(OSError):
        dns.save()

    # The zone file must be completely unchanged
    assert zone_file.read_text(encoding=ZONE_FILE_ENCODING) == original_content


# ---------------------------------------------------------------------------
# Explicit origin (zone files without $ORIGIN)
# ---------------------------------------------------------------------------

def test_explicit_origin_is_set_on_dns_file(tmp_path, no_origin_zone_content):
    """DNSFile.origin is populated from the explicit origin when the file has no $ORIGIN."""
    zone_file = tmp_path / "example.com.zone"
    zone_file.write_text(no_origin_zone_content, encoding=ZONE_FILE_ENCODING)
    dns = DNSFile(zone_file, DNSConfig(), origin="example.com")
    assert dns.origin is not None
    assert "example.com" in dns.origin


def test_explicit_origin_written_to_output(tmp_path, no_origin_zone_content):
    """$ORIGIN appears in the rewritten file when origin was supplied externally."""
    zone_file = tmp_path / "example.com.zone"
    zone_file.write_text(no_origin_zone_content, encoding=ZONE_FILE_ENCODING)
    dns = DNSFile(zone_file, DNSConfig(), origin="example.com")
    dns.add_record(ARecord(name="new", ttl=3600, class_=DNSClass.IN, type=RecordType.A, rdata="192.168.1.99", omit_ttl=False))
    dns.save()
    output = zone_file.read_text(encoding=ZONE_FILE_ENCODING)
    assert "$ORIGIN" in output
    assert "example.com." in output


def test_explicit_origin_consistent_with_file_origin(tmp_path, forward_sample_zone_content):
    """Passing an explicit origin that matches the file's $ORIGIN is accepted."""
    zone_file = tmp_path / "example.com.zone"
    zone_file.write_text(forward_sample_zone_content, encoding=ZONE_FILE_ENCODING)
    dns = DNSFile(zone_file, DNSConfig(), origin="example.com")
    assert dns.origin is not None
    assert "example.com" in dns.origin


def test_no_origin_file_without_explicit_origin_raises(tmp_path, no_origin_zone_content):
    """Parsing a file with no $ORIGIN and no explicit origin raises InvalidZoneFileError."""
    zone_file = tmp_path / "example.com.zone"
    zone_file.write_text(no_origin_zone_content, encoding=ZONE_FILE_ENCODING)
    with pytest.raises(InvalidZoneFileError):
        DNSFile(zone_file, DNSConfig())
