import pytest
from cleandns.record_types import ARecord, PTRRecord, SOARecord, RecordType, DNSClass


# --- Factories ---

def make_a_record(name="www", rdata="192.168.1.1", ttl=3600, omit_ttl=False) -> ARecord:
    return ARecord(
        name=name, ttl=ttl, class_=DNSClass.IN, type=RecordType.A,
        rdata=rdata, comment=None, omit_ttl=omit_ttl,
    )

def make_ptr_record(name, rdata="host.example.com.", ttl=3600, omit_ttl=False) -> PTRRecord:
    return PTRRecord(
        name=name, ttl=ttl, class_=DNSClass.IN, type=RecordType.PTR,
        rdata=rdata, comment=None, omit_ttl=omit_ttl,
    )

def make_soa_record(human_readable=False, refresh=3600, retry=1800, expire=604800, minimum=86400, ttl=3600, omit_ttl=False) -> SOARecord:
    return SOARecord(
        name="@", ttl=ttl, class_=DNSClass.IN, type=RecordType.SOA,
        rdata="ns1.example.com. admin.example.com. 2023101001 3600 1800 604800 86400",
        comment=None, omit_ttl=omit_ttl,
        mname="ns1.example.com.", rname="admin.example.com.",
        serial=2023101001, refresh=refresh, retry=retry, expire=expire, minimum=minimum,
        human_readable=human_readable,
    )


# --- AbstractRecord.__str__ ---

def test_record_str_includes_ttl():
    """omit_ttl=False: TTL must appear in the serialized record."""
    assert "3600" in str(make_a_record(omit_ttl=False))

def test_record_str_omits_ttl():
    """omit_ttl=True: TTL must not appear in the serialized record."""
    assert "3600" not in str(make_a_record(omit_ttl=True))


# --- AbstractRecord.__lt__ ---

def test_record_lt_by_name():
    """Records with different names sort alphabetically."""
    assert make_a_record(name="alpha") < make_a_record(name="beta")

def test_record_lt_case_insensitive():
    """Name comparison ignores case: AAA < bbb < zzz."""
    records = [make_a_record(name=n) for n in ["zzz", "AAA", "bbb"]]
    assert [r.name for r in sorted(records)] == ["AAA", "bbb", "zzz"]

def test_record_lt_rdata_as_tiebreak():
    """Records with the same name sort by rdata."""
    assert make_a_record(name="host", rdata="1.1.1.1") < make_a_record(name="host", rdata="2.2.2.2")


# --- PTRRecord.__lt__ ---

def test_ptr_record_lt_numeric():
    """PTR records sort numerically, not lexicographically (2 < 10)."""
    records = [make_ptr_record(name=n) for n in ["10.0.0", "2.0.0", "1.0.0"]]
    assert [r.name for r in sorted(records)] == ["1.0.0", "2.0.0", "10.0.0"]

def test_ptr_record_lt_falls_back_for_non_ptr():
    """PTR compared against a non-PTR falls back to AbstractRecord.__lt__."""
    assert make_ptr_record(name="alpha") < make_a_record(name="beta")


# --- SOARecord.increment_serial ---

def test_soa_increment_serial():
    """increment_serial must add exactly 1 to the serial."""
    soa = make_soa_record()
    old = soa.serial
    soa.increment_serial()
    assert soa.serial == old + 1


# --- SOARecord.__str__ ---

def test_soa_str_raw():
    """human_readable=False: SOA timing fields are raw integers."""
    output = str(make_soa_record(human_readable=False))
    assert "3600" in output   # refresh
    assert "1800" in output   # retry

def test_soa_str_human_readable():
    """human_readable=True: SOA timing fields are formatted strings."""
    output = str(make_soa_record(human_readable=True))
    assert "1h" in output    # refresh = 3600
    assert "30m" in output   # retry   = 1800

def test_soa_str_is_idempotent():
    """Calling str() twice on the same SOARecord must give identical results."""
    soa = make_soa_record(human_readable=True)
    assert str(soa) == str(soa)
