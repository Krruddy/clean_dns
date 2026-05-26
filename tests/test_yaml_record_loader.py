import pytest
from pathlib import Path
from cleandns.yaml_record_loader import YAMLRecordLoader, StandardFormat, DNSEntriesFormat
from cleandns.record_types import RecordType, ARecord, AAAARecord, CNAMERecord, MXRecord, PTRRecord, TXTRecord
from cleandns.exceptions import InvalidYAMLError, UnknownRecordTypeError

ENCODING = "utf-8"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def write_yaml(tmp_path: Path, content: str) -> Path:
    p = tmp_path / "records.yaml"
    p.write_text(content, encoding=ENCODING)
    return p


# ---------------------------------------------------------------------------
# Valid input
# ---------------------------------------------------------------------------

def test_load_single_a_record(tmp_path):
    p = write_yaml(tmp_path, """\
example.com:
  - type: A
    name: newhost
    ttl: 3600
    rdata: 192.168.1.100
""")
    result = YAMLRecordLoader.load(p)
    assert list(result.keys()) == ["example.com"]
    assert len(result["example.com"]) == 1
    record = result["example.com"][0]
    assert isinstance(record, ARecord)
    assert record.name == "newhost"
    assert record.ttl == 3600
    assert record.rdata == "192.168.1.100"


def test_load_multiple_record_types(tmp_path):
    p = write_yaml(tmp_path, """\
example.com:
  - type: A
    name: host1
    ttl: 3600
    rdata: 10.0.0.1
  - type: AAAA
    name: host1
    ttl: 3600
    rdata: 2001:db8::1
  - type: CNAME
    name: www
    ttl: 300
    rdata: host1
  - type: PTR
    name: 1.0.0
    ttl: 3600
    rdata: host1.example.com.
""")
    result = YAMLRecordLoader.load(p)
    records = result["example.com"]
    assert len(records) == 4
    assert isinstance(records[0], ARecord)
    assert isinstance(records[1], AAAARecord)
    assert isinstance(records[2], CNAMERecord)
    assert isinstance(records[3], PTRRecord)


def test_load_multiple_zones(tmp_path):
    p = write_yaml(tmp_path, """\
example.com:
  - type: A
    name: host1
    ttl: 3600
    rdata: 10.0.0.1
other.net:
  - type: A
    name: host2
    ttl: 300
    rdata: 10.0.0.2
""")
    result = YAMLRecordLoader.load(p)
    assert set(result.keys()) == {"example.com", "other.net"}
    assert len(result["example.com"]) == 1
    assert len(result["other.net"]) == 1


def test_load_omitted_ttl_uses_default(tmp_path):
    """A record without a ttl field must use the provided default_ttl."""
    p = write_yaml(tmp_path, """\
example.com:
  - type: A
    name: host1
    rdata: 10.0.0.1
""")
    result = YAMLRecordLoader.load(p, default_ttl=7200)
    assert result["example.com"][0].ttl == 7200


def test_load_type_is_case_insensitive(tmp_path):
    p = write_yaml(tmp_path, """\
example.com:
  - type: a
    name: host1
    ttl: 3600
    rdata: 10.0.0.1
""")
    result = YAMLRecordLoader.load(p)
    assert isinstance(result["example.com"][0], ARecord)


# ---------------------------------------------------------------------------
# Invalid input
# ---------------------------------------------------------------------------

def test_load_raises_on_nonexistent_file(tmp_path):
    with pytest.raises(InvalidYAMLError, match="Could not open"):
        YAMLRecordLoader.load(tmp_path / "missing.yaml")


def test_load_raises_on_malformed_yaml(tmp_path):
    p = write_yaml(tmp_path, "key: [unclosed")
    with pytest.raises(InvalidYAMLError, match="Could not parse"):
        YAMLRecordLoader.load(p)


def test_load_raises_when_top_level_is_not_dict(tmp_path):
    p = write_yaml(tmp_path, "- a\n- b\n")
    with pytest.raises(InvalidYAMLError, match="unrecognised YAML structure"):
        YAMLRecordLoader.load(p)


def test_load_raises_when_records_is_not_list(tmp_path):
    p = write_yaml(tmp_path, "example.com: not-a-list\n")
    with pytest.raises(InvalidYAMLError, match="must be a list"):
        YAMLRecordLoader.load(p)


def test_load_raises_when_record_is_not_dict(tmp_path):
    p = write_yaml(tmp_path, "example.com:\n  - just-a-string\n")
    with pytest.raises(InvalidYAMLError, match="must be a mapping"):
        YAMLRecordLoader.load(p)


def test_load_raises_on_missing_name(tmp_path):
    p = write_yaml(tmp_path, """\
example.com:
  - type: A
    ttl: 3600
    rdata: 10.0.0.1
""")
    with pytest.raises(InvalidYAMLError, match="'name'"):
        YAMLRecordLoader.load(p)


def test_load_raises_on_missing_rdata(tmp_path):
    p = write_yaml(tmp_path, """\
example.com:
  - type: A
    name: host1
    ttl: 3600
""")
    with pytest.raises(InvalidYAMLError, match="'rdata'"):
        YAMLRecordLoader.load(p)


def test_load_mx_record(tmp_path):
    p = write_yaml(tmp_path, """\
example.com:
  - type: MX
    name: "@"
    ttl: 3600
    rdata: "10 mail.example.com."
""")
    result = YAMLRecordLoader.load(p)
    record = result["example.com"][0]
    assert isinstance(record, MXRecord)
    assert record.rdata == "10 mail.example.com."


def test_load_txt_record(tmp_path):
    p = write_yaml(tmp_path, """\
example.com:
  - type: TXT
    name: "@"
    ttl: 3600
    rdata: '"v=spf1 include:example.com ~all"'
""")
    result = YAMLRecordLoader.load(p)
    record = result["example.com"][0]
    assert isinstance(record, TXTRecord)
    assert "spf1" in record.rdata


def test_load_raises_on_unknown_type(tmp_path):
    p = write_yaml(tmp_path, """\
example.com:
  - type: CAA
    name: "@"
    ttl: 3600
    rdata: '0 issue "ca.example.com"'
""")
    with pytest.raises(UnknownRecordTypeError, match="CAA"):
        YAMLRecordLoader.load(p)


def test_load_raises_on_invalid_ttl(tmp_path):
    p = write_yaml(tmp_path, """\
example.com:
  - type: A
    name: host1
    ttl: -1
    rdata: 10.0.0.1
""")
    with pytest.raises(InvalidYAMLError, match="ttl"):
        YAMLRecordLoader.load(p)


# ---------------------------------------------------------------------------
# Format auto-detection — can_parse() unit tests
# ---------------------------------------------------------------------------

def test_dns_entries_format_can_parse_dns_entries_document():
    assert DNSEntriesFormat.can_parse({"dnsEntries": []}) is True

def test_dns_entries_format_rejects_standard_document():
    assert DNSEntriesFormat.can_parse({"example.com": []}) is False

def test_dns_entries_format_rejects_non_dict():
    assert DNSEntriesFormat.can_parse([{"dnsEntries": []}]) is False

def test_standard_format_can_parse_any_dict():
    assert StandardFormat.can_parse({"example.com": []}) is True

def test_standard_format_rejects_non_dict():
    assert StandardFormat.can_parse(["a", "b"]) is False


# ---------------------------------------------------------------------------
# DNSEntriesFormat — valid input
# ---------------------------------------------------------------------------

def test_dns_entries_load_single_entry(tmp_path):
    """A single dnsEntries entry must produce one ARecord in the correct zone."""
    p = write_yaml(tmp_path, """\
dnsEntries:
  - ip: 10.10.100.123
    fqdn: host3.example.com
""")
    result = YAMLRecordLoader.load(p)
    assert list(result.keys()) == ["example.com"]
    record = result["example.com"][0]
    assert isinstance(record, ARecord)
    assert record.name == "host3"
    assert record.rdata == "10.10.100.123"


def test_dns_entries_load_multiple_entries_same_zone(tmp_path):
    """Multiple entries with the same domain suffix land in the same zone."""
    p = write_yaml(tmp_path, """\
dnsEntries:
  - ip: 10.10.100.123
    fqdn: host3.example.com
  - ip: 10.10.100.124
    fqdn: host4.example.com
""")
    result = YAMLRecordLoader.load(p)
    assert len(result) == 1
    assert len(result["example.com"]) == 2
    assert {r.name for r in result["example.com"]} == {"host3", "host4"}


def test_dns_entries_load_entries_across_zones(tmp_path):
    """Entries with different domain suffixes are grouped into separate zones."""
    p = write_yaml(tmp_path, """\
dnsEntries:
  - ip: 10.0.0.1
    fqdn: host1.example.com
  - ip: 10.0.0.2
    fqdn: host2.other.net
""")
    result = YAMLRecordLoader.load(p)
    assert set(result.keys()) == {"example.com", "other.net"}
    assert result["example.com"][0].name == "host1"
    assert result["other.net"][0].name == "host2"


def test_dns_entries_multi_label_hostname(tmp_path):
    """Only the first label is the hostname; the rest is the zone."""
    p = write_yaml(tmp_path, """\
dnsEntries:
  - ip: 10.0.0.1
    fqdn: web.sub.example.com
""")
    result = YAMLRecordLoader.load(p)
    assert "sub.example.com" in result
    assert result["sub.example.com"][0].name == "web"


def test_dns_entries_uses_default_ttl(tmp_path):
    """Records created from dnsEntries must use the supplied default_ttl."""
    p = write_yaml(tmp_path, """\
dnsEntries:
  - ip: 10.0.0.1
    fqdn: host1.example.com
""")
    result = YAMLRecordLoader.load(p, default_ttl=7200)
    assert result["example.com"][0].ttl == 7200


# ---------------------------------------------------------------------------
# DNSEntriesFormat — invalid input
# ---------------------------------------------------------------------------

def test_dns_entries_raises_on_missing_ip(tmp_path):
    p = write_yaml(tmp_path, """\
dnsEntries:
  - fqdn: host1.example.com
""")
    with pytest.raises(InvalidYAMLError, match="'ip'"):
        YAMLRecordLoader.load(p)


def test_dns_entries_raises_on_missing_fqdn(tmp_path):
    p = write_yaml(tmp_path, """\
dnsEntries:
  - ip: 10.0.0.1
""")
    with pytest.raises(InvalidYAMLError, match="'fqdn'"):
        YAMLRecordLoader.load(p)


def test_dns_entries_raises_on_single_label_fqdn(tmp_path):
    """An FQDN with only one label cannot yield a zone name."""
    p = write_yaml(tmp_path, """\
dnsEntries:
  - ip: 10.0.0.1
    fqdn: justahostname
""")
    with pytest.raises(InvalidYAMLError, match="zone"):
        YAMLRecordLoader.load(p)


def test_dns_entries_raises_when_list_is_not_a_list(tmp_path):
    p = write_yaml(tmp_path, "dnsEntries: not-a-list\n")
    with pytest.raises(InvalidYAMLError, match="must be a list"):
        YAMLRecordLoader.load(p)


def test_dns_entries_raises_when_entry_is_not_a_mapping(tmp_path):
    p = write_yaml(tmp_path, "dnsEntries:\n  - just-a-string\n")
    with pytest.raises(InvalidYAMLError, match="must be a mapping"):
        YAMLRecordLoader.load(p)


# ---------------------------------------------------------------------------
# DNSEntriesFormat — zone_map-based resolution
# ---------------------------------------------------------------------------

def test_dns_entries_zone_map_resolves_correct_zone(tmp_path):
    """When zone_map is provided the FQDN is matched against the known zones."""
    p = write_yaml(tmp_path, """\
dnsEntries:
  - ip: 10.0.0.1
    fqdn: web.example.com
""")
    zone_map = {"example.com": Path("/etc/bind/example.com.zone")}
    result = YAMLRecordLoader.load(p, zone_map=zone_map)
    assert "example.com" in result
    assert result["example.com"][0].name == "web"


def test_dns_entries_zone_map_prefers_longest_match(tmp_path):
    """Longest-suffix matching picks the most specific zone over a parent zone."""
    p = write_yaml(tmp_path, """\
dnsEntries:
  - ip: 10.0.0.1
    fqdn: host.sub.example.com
""")
    zone_map = {
        "example.com":     Path("/etc/bind/example.com.zone"),
        "sub.example.com": Path("/etc/bind/sub.example.com.zone"),
    }
    result = YAMLRecordLoader.load(p, zone_map=zone_map)
    assert "sub.example.com" in result
    assert result["sub.example.com"][0].name == "host"
    assert "example.com" not in result


def test_dns_entries_zone_map_falls_back_to_parent_when_no_subzone(tmp_path):
    """When only the parent zone is known, the sub-domain labels become part of the name."""
    p = write_yaml(tmp_path, """\
dnsEntries:
  - ip: 10.0.0.1
    fqdn: host.sub.example.com
""")
    zone_map = {"example.com": Path("/etc/bind/example.com.zone")}
    result = YAMLRecordLoader.load(p, zone_map=zone_map)
    assert "example.com" in result
    assert result["example.com"][0].name == "host.sub"


def test_dns_entries_zone_map_raises_on_unmatched_fqdn(tmp_path):
    """An FQDN that matches no known zone must raise InvalidYAMLError."""
    p = write_yaml(tmp_path, """\
dnsEntries:
  - ip: 10.0.0.1
    fqdn: host.unknown.com
""")
    zone_map = {"example.com": Path("/etc/bind/example.com.zone")}
    with pytest.raises(InvalidYAMLError, match="does not match any known zone"):
        YAMLRecordLoader.load(p, zone_map=zone_map)
