import pytest
from cleandns.record_types import ARecord, MXRecord, PTRRecord, SOARecord, TXTRecord, RecordType, DNSClass


# --- Factories ---

def make_a_record(name="www", rdata="192.168.1.1", ttl=3600, omit_ttl=False) -> ARecord:
    return ARecord(
        name=name, ttl=ttl, class_=DNSClass.IN, type=RecordType.A,
        rdata=rdata, omit_ttl=omit_ttl,
    )

def make_ptr_record(name, rdata="host.example.com.", ttl=3600, omit_ttl=False) -> PTRRecord:
    return PTRRecord(
        name=name, ttl=ttl, class_=DNSClass.IN, type=RecordType.PTR,
        rdata=rdata, omit_ttl=omit_ttl,
    )

def make_soa_record(human_readable=False, refresh=3600, retry=1800, expire=604800, minimum=86400, ttl=3600, omit_ttl=False) -> SOARecord:
    return SOARecord(
        name="@", ttl=ttl, class_=DNSClass.IN, type=RecordType.SOA,
        rdata="ns1.example.com. admin.example.com. 2023101001 3600 1800 604800 86400",
        omit_ttl=omit_ttl,
        mname="ns1.example.com.", rname="admin.example.com.",
        serial=2023101001, refresh=refresh, retry=retry, expire=expire, minimum=minimum,
        human_readable=human_readable,
    )


# --- AbstractRecord.__str__ ---

@pytest.mark.parametrize("omit_ttl,present", [(False, True), (True, False)])
def test_record_str_ttl_visibility(omit_ttl, present):
    """TTL appears in the serialized record iff omit_ttl=False."""
    assert ("3600" in str(make_a_record(omit_ttl=omit_ttl))) == present


# --- AbstractRecord.__lt__ ---

def test_record_lt_by_name():
    """Records with different names sort alphabetically."""
    assert make_txt_record(name="alpha") < make_txt_record(name="beta")

def test_record_lt_case_insensitive():
    """Name comparison ignores case: AAA < bbb < zzz."""
    records = [make_txt_record(name=n) for n in ["zzz", "AAA", "bbb"]]
    assert [r.name for r in sorted(records)] == ["AAA", "bbb", "zzz"]

def test_record_lt_rdata_as_tiebreak():
    """Records with the same name sort by rdata."""
    assert make_txt_record(name="host", rdata="aaa") < make_txt_record(name="host", rdata="zzz")


# --- ARecord.__lt__ ---

def test_a_record_lt_by_first_octet():
    """A records sort by first octet numerically."""
    assert make_a_record(rdata="1.0.0.1") < make_a_record(rdata="2.0.0.1")

def test_a_record_lt_by_last_octet():
    """Last octet is the final tiebreaker."""
    assert make_a_record(rdata="10.0.0.1") < make_a_record(rdata="10.0.0.2")

def test_a_record_lt_numeric_not_lexicographic():
    """Octet comparison is numeric: 9 < 10, not lexicographic '10' < '9'."""
    records = [make_a_record(rdata=f"10.0.0.{n}") for n in [10, 9, 2]]
    assert [r.rdata for r in sorted(records)] == ["10.0.0.2", "10.0.0.9", "10.0.0.10"]

def test_a_record_lt_name_as_tiebreak():
    """A records with identical IPs fall back to name comparison."""
    assert make_a_record(name="alpha", rdata="1.1.1.1") < make_a_record(name="beta", rdata="1.1.1.1")

def test_a_record_lt_falls_back_for_non_a():
    """ARecord compared against a non-ARecord falls back to AbstractRecord.__lt__."""
    assert make_a_record(name="alpha") < make_mx_record(name="beta")


# --- PTRRecord.__lt__ ---

def test_ptr_record_lt_numeric():
    """PTR records sort numerically, not lexicographically (2 < 10)."""
    records = [make_ptr_record(name=n) for n in ["10.0.0", "2.0.0", "1.0.0"]]
    assert [r.name for r in sorted(records)] == ["1.0.0", "2.0.0", "10.0.0"]

def make_mx_record(name="@", rdata="10 mail.example.com.", ttl=3600, omit_ttl=False) -> MXRecord:
    return MXRecord(name=name, ttl=ttl, class_=DNSClass.IN, type=RecordType.MX, rdata=rdata, omit_ttl=omit_ttl)

def make_txt_record(name="@", rdata='"v=spf1 ~all"', ttl=3600, omit_ttl=False) -> TXTRecord:
    return TXTRecord(name=name, ttl=ttl, class_=DNSClass.IN, type=RecordType.TXT, rdata=rdata, omit_ttl=omit_ttl)


def test_ptr_record_lt_falls_back_for_non_ptr():
    """PTR compared against a non-PTR falls back to AbstractRecord.__lt__."""
    assert make_ptr_record(name="alpha") < make_a_record(name="beta")


# --- MXRecord.__lt__ ---

def test_mx_record_lt_by_preference():
    """MX records sort by preference ascending."""
    assert make_mx_record(rdata="10 mail.example.com.") < make_mx_record(rdata="20 mail.example.com.")

def test_mx_record_lt_preference_is_numeric():
    """Preference comparison must be numeric, not lexicographic (2 < 10 < 100)."""
    records = [make_mx_record(rdata=f"{p} mail.example.com.") for p in [100, 2, 10]]
    assert [int(r.rdata.split()[0]) for r in sorted(records)] == [2, 10, 100]

def test_mx_record_lt_exchange_as_tiebreak():
    """Records with equal preference sort alphabetically by exchange name."""
    assert make_mx_record(rdata="10 a.example.com.") < make_mx_record(rdata="10 b.example.com.")

def test_mx_record_lt_exchange_tiebreak_is_case_insensitive():
    """Exchange tiebreak ignores case."""
    assert make_mx_record(rdata="10 AAA.example.com.") < make_mx_record(rdata="10 bbb.example.com.")

def test_mx_record_lt_falls_back_for_non_mx():
    """MX compared against a non-MX record falls back to AbstractRecord.__lt__."""
    assert make_mx_record(name="alpha") < make_a_record(name="beta")


# --- MXRecord.__str__ ---

@pytest.mark.parametrize("omit_ttl,present", [(False, True), (True, False)])
def test_mx_record_str_ttl_visibility(omit_ttl, present):
    """MXRecord must honour omit_ttl the same way AbstractRecord does."""
    assert ("3600" in str(make_mx_record(omit_ttl=omit_ttl))) == present

def test_mx_record_str_contains_preference_and_exchange():
    """MXRecord str must include both the preference value and the exchange name."""
    r = make_mx_record(rdata="10 mail.example.com.")
    assert "MX" in str(r)
    assert "10 mail.example.com." in str(r)


# --- TXTRecord.__str__ ---

def test_txt_record_str_contains_type_and_rdata():
    """TXTRecord str must include the type and the quoted rdata."""
    r = make_txt_record()
    assert "TXT" in str(r)
    assert '"v=spf1 ~all"' in str(r)

@pytest.mark.parametrize("omit_ttl,present", [(False, True), (True, False)])
def test_txt_record_str_ttl_visibility(omit_ttl, present):
    """TXTRecord must honour omit_ttl the same way AbstractRecord does."""
    assert ("3600" in str(make_txt_record(omit_ttl=omit_ttl))) == present


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

@pytest.mark.parametrize("omit_ttl,present", [(False, True), (True, False)])
def test_soa_str_ttl_visibility(omit_ttl, present):
    """SOARecord must honour omit_ttl in the same way as AbstractRecord."""
    # Use a TTL value distinct from all timing fields (refresh=3600, retry=1800, etc.)
    # to avoid a false positive when checking for its presence in the output.
    assert ("7200" in str(make_soa_record(ttl=7200, omit_ttl=omit_ttl))) == present


# --- SOARecord._format_time ---

@pytest.mark.parametrize("seconds,expected", [
    (0,      ""),       # no units match → empty string
    (1,      "1s"),
    (60,     "1m"),
    (3600,   "1h"),
    (86400,  "1d"),
    (604800, "1W"),
    (90061,  "1d1h1m1s"),  # multi-unit: 1 day + 1 hour + 1 min + 1 sec
])
def test_format_time(seconds, expected):
    """_format_time must convert seconds to the correct human-readable string."""
    assert make_soa_record()._format_time(seconds) == expected
