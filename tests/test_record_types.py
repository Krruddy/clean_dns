import pytest
from cleandns.record_types import ARecord, RecordType, DNSClass


@pytest.fixture
def base_a_record():
    """A minimal ARecord with a known TTL, used to test serialization variants."""
    def _make(omit_ttl: bool) -> ARecord:
        return ARecord(
            name="www",
            ttl=3600,
            class_=DNSClass.IN,
            type=RecordType.A,
            rdata="192.168.1.1",
            comment=None,
            omit_ttl=omit_ttl,
        )
    return _make


def test_record_str_includes_ttl(base_a_record):
    """omit_ttl=False: TTL must appear in the serialized record."""
    assert "3600" in str(base_a_record(omit_ttl=False))


def test_record_str_omits_ttl(base_a_record):
    """omit_ttl=True: TTL must not appear in the serialized record."""
    assert "3600" not in str(base_a_record(omit_ttl=True))
