import pytest
from pathlib import Path
from cleandns.yaml_record_loader import YAMLRecordLoader
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
    with pytest.raises(InvalidYAMLError, match="top-level structure"):
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
