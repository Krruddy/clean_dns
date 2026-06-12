import pytest
from unittest.mock import patch
from cleandns.deduplication import find_ip_duplicates, prompt_deduplication, DEDUP_RECORD_TYPES
from cleandns.logger import Logger
from cleandns.record_types import (
    ARecord, AAAARecord, CNAMERecord, MXRecord, NSRecord, RecordType, DNSClass,
)


def make_a(name: str, ip: str) -> ARecord:
    return ARecord(name=name, ttl=3600, class_=DNSClass.IN, type=RecordType.A, rdata=ip, omit_ttl=False)


def make_aaaa(name: str, ip: str) -> AAAARecord:
    return AAAARecord(name=name, ttl=3600, class_=DNSClass.IN, type=RecordType.AAAA, rdata=ip, omit_ttl=False)


def make_cname(name: str, target: str) -> CNAMERecord:
    return CNAMERecord(name=name, ttl=3600, class_=DNSClass.IN, type=RecordType.CNAME, rdata=target, omit_ttl=False)


def make_mx(name: str, rdata: str) -> MXRecord:
    return MXRecord(name=name, ttl=3600, class_=DNSClass.IN, type=RecordType.MX, rdata=rdata, omit_ttl=False)


@pytest.fixture
def logger():
    return Logger()


# ---------------------------------------------------------------------------
# DEDUP_RECORD_TYPES constant
# ---------------------------------------------------------------------------

def test_dedup_record_types_contains_a_and_aaaa():
    assert RecordType.A in DEDUP_RECORD_TYPES
    assert RecordType.AAAA in DEDUP_RECORD_TYPES


def test_dedup_record_types_excludes_other_types():
    for rtype in (RecordType.CNAME, RecordType.MX, RecordType.NS, RecordType.TXT, RecordType.PTR, RecordType.SOA):
        assert rtype not in DEDUP_RECORD_TYPES


# ---------------------------------------------------------------------------
# find_ip_duplicates
# ---------------------------------------------------------------------------

def test_find_ip_duplicates_empty_records():
    assert find_ip_duplicates({}) == []


def test_find_ip_duplicates_no_duplicates_among_a_records():
    records = {RecordType.A: [make_a("host1", "1.2.3.4"), make_a("host2", "5.6.7.8")]}
    assert find_ip_duplicates(records) == []


def test_find_ip_duplicates_single_a_record_is_not_a_group():
    records = {RecordType.A: [make_a("host1", "1.2.3.4")]}
    assert find_ip_duplicates(records) == []


def test_find_ip_duplicates_returns_group_of_two_a_records():
    r1 = make_a("host1", "1.2.3.4")
    r2 = make_a("host2", "1.2.3.4")
    records = {RecordType.A: [r1, r2]}
    groups = find_ip_duplicates(records)
    assert len(groups) == 1
    assert set(id(r) for r in groups[0]) == {id(r1), id(r2)}


def test_find_ip_duplicates_returns_group_of_three_a_records():
    r1 = make_a("h1", "10.0.0.1")
    r2 = make_a("h2", "10.0.0.1")
    r3 = make_a("h3", "10.0.0.1")
    records = {RecordType.A: [r1, r2, r3]}
    groups = find_ip_duplicates(records)
    assert len(groups) == 1
    assert len(groups[0]) == 3


def test_find_ip_duplicates_aaaa_records():
    r1 = make_aaaa("host1", "2001:db8::1")
    r2 = make_aaaa("host2", "2001:db8::1")
    records = {RecordType.AAAA: [r1, r2]}
    groups = find_ip_duplicates(records)
    assert len(groups) == 1
    assert len(groups[0]) == 2


def test_find_ip_duplicates_ignores_cname_records():
    records = {
        RecordType.CNAME: [make_cname("a", "target."), make_cname("b", "target.")],
    }
    assert find_ip_duplicates(records) == []


def test_find_ip_duplicates_ignores_mx_records():
    records = {
        RecordType.MX: [make_mx("@", "10 mail.example.com."), make_mx("@", "10 mail.example.com.")],
    }
    assert find_ip_duplicates(records) == []


def test_find_ip_duplicates_two_separate_ip_groups():
    r1 = make_a("host1", "1.1.1.1")
    r2 = make_a("host2", "1.1.1.1")
    r3 = make_a("host3", "2.2.2.2")
    r4 = make_a("host4", "2.2.2.2")
    records = {RecordType.A: [r1, r2, r3, r4]}
    groups = find_ip_duplicates(records)
    assert len(groups) == 2


def test_find_ip_duplicates_mixed_a_and_aaaa_produce_separate_groups():
    ra1 = make_a("h1", "1.2.3.4")
    ra2 = make_a("h2", "1.2.3.4")
    rb1 = make_aaaa("h3", "::1")
    rb2 = make_aaaa("h4", "::1")
    records = {RecordType.A: [ra1, ra2], RecordType.AAAA: [rb1, rb2]}
    groups = find_ip_duplicates(records)
    assert len(groups) == 2


def test_find_ip_duplicates_a_and_aaaa_with_same_string_do_not_mix():
    # Even if rdata strings happen to be identical, types are kept separate.
    ra = make_a("h1", "::1")  # pathological but possible in test
    rb = make_a("h2", "::1")
    rc = make_aaaa("h3", "::1")
    rd = make_aaaa("h4", "::1")
    records = {RecordType.A: [ra, rb], RecordType.AAAA: [rc, rd]}
    groups = find_ip_duplicates(records)
    # Two groups, one per type
    assert len(groups) == 2
    group_types = {g[0].type for g in groups}
    assert group_types == {RecordType.A, RecordType.AAAA}


def test_find_ip_duplicates_preserves_original_order():
    r1 = make_a("alpha", "10.0.0.1")
    r2 = make_a("beta", "10.0.0.1")
    r3 = make_a("gamma", "10.0.0.1")
    records = {RecordType.A: [r1, r2, r3]}
    groups = find_ip_duplicates(records)
    assert groups[0] == [r1, r2, r3]


# ---------------------------------------------------------------------------
# prompt_deduplication — non-interactive path
# ---------------------------------------------------------------------------

def test_prompt_deduplication_empty_groups_returns_empty(logger):
    assert prompt_deduplication([], logger) == []


def test_prompt_deduplication_non_tty_returns_empty(logger):
    groups = [[make_a("host1", "1.2.3.4"), make_a("host2", "1.2.3.4")]]
    with patch("sys.stdout") as mock_stdout:
        mock_stdout.isatty.return_value = False
        result = prompt_deduplication(groups, logger)
    assert result == []


def test_prompt_deduplication_non_tty_does_not_call_input(logger):
    groups = [[make_a("host1", "1.2.3.4"), make_a("host2", "1.2.3.4")]]
    with patch("sys.stdout") as mock_stdout, patch("builtins.input") as mock_input:
        mock_stdout.isatty.return_value = False
        prompt_deduplication(groups, logger)
    mock_input.assert_not_called()


def test_prompt_deduplication_non_tty_empty_groups_skips_tty_check(logger):
    # Empty groups must return early before the isatty check is even reached.
    with patch("sys.stdout") as mock_stdout:
        mock_stdout.isatty.return_value = False
        result = prompt_deduplication([], logger)
    assert result == []


# ---------------------------------------------------------------------------
# prompt_deduplication — interactive path (tty)
# ---------------------------------------------------------------------------

def test_prompt_deduplication_enter_keeps_all(logger):
    r1 = make_a("host1", "1.2.3.4")
    r2 = make_a("host2", "1.2.3.4")
    groups = [[r1, r2]]
    with patch("sys.stdout") as mock_stdout, \
         patch("builtins.input", return_value=""), \
         patch("builtins.print"):
        mock_stdout.isatty.return_value = True
        result = prompt_deduplication(groups, logger)
    assert result == []


def test_prompt_deduplication_whitespace_only_input_keeps_all(logger):
    r1 = make_a("host1", "1.2.3.4")
    r2 = make_a("host2", "1.2.3.4")
    groups = [[r1, r2]]
    with patch("sys.stdout") as mock_stdout, \
         patch("builtins.input", return_value="   "), \
         patch("builtins.print"):
        mock_stdout.isatty.return_value = True
        result = prompt_deduplication(groups, logger)
    assert result == []


def test_prompt_deduplication_keep_first_removes_second(logger):
    r1 = make_a("host1", "1.2.3.4")
    r2 = make_a("host2", "1.2.3.4")
    groups = [[r1, r2]]
    with patch("sys.stdout") as mock_stdout, \
         patch("builtins.input", return_value="0"), \
         patch("builtins.print"):
        mock_stdout.isatty.return_value = True
        result = prompt_deduplication(groups, logger)
    assert result == [r2]


def test_prompt_deduplication_keep_second_removes_first(logger):
    r1 = make_a("host1", "1.2.3.4")
    r2 = make_a("host2", "1.2.3.4")
    groups = [[r1, r2]]
    with patch("sys.stdout") as mock_stdout, \
         patch("builtins.input", return_value="1"), \
         patch("builtins.print"):
        mock_stdout.isatty.return_value = True
        result = prompt_deduplication(groups, logger)
    assert result == [r1]


def test_prompt_deduplication_keep_subset_of_three(logger):
    r1 = make_a("h1", "1.1.1.1")
    r2 = make_a("h2", "1.1.1.1")
    r3 = make_a("h3", "1.1.1.1")
    groups = [[r1, r2, r3]]
    with patch("sys.stdout") as mock_stdout, \
         patch("builtins.input", return_value="0,2"), \
         patch("builtins.print"):
        mock_stdout.isatty.return_value = True
        result = prompt_deduplication(groups, logger)
    assert result == [r2]


def test_prompt_deduplication_keep_all_by_entering_all_indices(logger):
    r1 = make_a("h1", "1.1.1.1")
    r2 = make_a("h2", "1.1.1.1")
    groups = [[r1, r2]]
    with patch("sys.stdout") as mock_stdout, \
         patch("builtins.input", return_value="0,1"), \
         patch("builtins.print"):
        mock_stdout.isatty.return_value = True
        result = prompt_deduplication(groups, logger)
    assert result == []


def test_prompt_deduplication_input_with_spaces_around_numbers(logger):
    r1 = make_a("h1", "1.1.1.1")
    r2 = make_a("h2", "1.1.1.1")
    r3 = make_a("h3", "1.1.1.1")
    groups = [[r1, r2, r3]]
    with patch("sys.stdout") as mock_stdout, \
         patch("builtins.input", return_value=" 0 , 2 "), \
         patch("builtins.print"):
        mock_stdout.isatty.return_value = True
        result = prompt_deduplication(groups, logger)
    assert result == [r2]


# ---------------------------------------------------------------------------
# Input validation — invalid input is re-prompted
# ---------------------------------------------------------------------------

def test_prompt_deduplication_letters_then_valid_input(logger):
    r1 = make_a("host1", "1.2.3.4")
    r2 = make_a("host2", "1.2.3.4")
    groups = [[r1, r2]]
    with patch("sys.stdout") as mock_stdout, \
         patch("builtins.input", side_effect=["abc", "1"]), \
         patch("builtins.print"):
        mock_stdout.isatty.return_value = True
        result = prompt_deduplication(groups, logger)
    assert result == [r1]


def test_prompt_deduplication_mixed_valid_invalid_then_valid(logger):
    r1 = make_a("host1", "1.2.3.4")
    r2 = make_a("host2", "1.2.3.4")
    groups = [[r1, r2]]
    with patch("sys.stdout") as mock_stdout, \
         patch("builtins.input", side_effect=["0,x", "0"]), \
         patch("builtins.print"):
        mock_stdout.isatty.return_value = True
        result = prompt_deduplication(groups, logger)
    assert result == [r2]


def test_prompt_deduplication_out_of_bounds_positive_then_valid(logger):
    r1 = make_a("host1", "1.2.3.4")
    r2 = make_a("host2", "1.2.3.4")
    groups = [[r1, r2]]
    with patch("sys.stdout") as mock_stdout, \
         patch("builtins.input", side_effect=["5", "0"]), \
         patch("builtins.print"):
        mock_stdout.isatty.return_value = True
        result = prompt_deduplication(groups, logger)
    assert result == [r2]


def test_prompt_deduplication_negative_index_then_valid(logger):
    r1 = make_a("host1", "1.2.3.4")
    r2 = make_a("host2", "1.2.3.4")
    groups = [[r1, r2]]
    with patch("sys.stdout") as mock_stdout, \
         patch("builtins.input", side_effect=["-1", "0"]), \
         patch("builtins.print"):
        mock_stdout.isatty.return_value = True
        result = prompt_deduplication(groups, logger)
    assert result == [r2]


def test_prompt_deduplication_prints_error_on_invalid_input(logger):
    r1 = make_a("h1", "1.2.3.4")
    r2 = make_a("h2", "1.2.3.4")
    groups = [[r1, r2]]
    with patch("sys.stdout") as mock_stdout, \
         patch("builtins.input", side_effect=["bad", ""]), \
         patch("builtins.print") as mock_print:
        mock_stdout.isatty.return_value = True
        prompt_deduplication(groups, logger)
    # At least one error message must have been printed
    error_calls = [str(c) for c in mock_print.call_args_list if "Invalid" in str(c)]
    assert len(error_calls) >= 1


def test_prompt_deduplication_prints_error_on_out_of_bounds(logger):
    r1 = make_a("h1", "1.2.3.4")
    r2 = make_a("h2", "1.2.3.4")
    groups = [[r1, r2]]
    with patch("sys.stdout") as mock_stdout, \
         patch("builtins.input", side_effect=["9", ""]), \
         patch("builtins.print") as mock_print:
        mock_stdout.isatty.return_value = True
        prompt_deduplication(groups, logger)
    error_calls = [str(c) for c in mock_print.call_args_list if "Out-of-bounds" in str(c)]
    assert len(error_calls) >= 1


# ---------------------------------------------------------------------------
# Multiple groups
# ---------------------------------------------------------------------------

def test_prompt_deduplication_multiple_groups_each_prompted_independently(logger):
    r1 = make_a("h1", "1.1.1.1")
    r2 = make_a("h2", "1.1.1.1")
    r3 = make_a("h3", "2.2.2.2")
    r4 = make_a("h4", "2.2.2.2")
    groups = [[r1, r2], [r3, r4]]
    # Keep index 0 from group 1, Enter (keep all) for group 2
    with patch("sys.stdout") as mock_stdout, \
         patch("builtins.input", side_effect=["0", ""]), \
         patch("builtins.print"):
        mock_stdout.isatty.return_value = True
        result = prompt_deduplication(groups, logger)
    assert r2 in result
    assert r3 not in result
    assert r4 not in result


def test_prompt_deduplication_multiple_groups_all_resolved(logger):
    r1 = make_a("h1", "1.1.1.1")
    r2 = make_a("h2", "1.1.1.1")
    r3 = make_aaaa("h3", "::1")
    r4 = make_aaaa("h4", "::1")
    groups = [[r1, r2], [r3, r4]]
    # Keep 1 from first group, keep 0 from second
    with patch("sys.stdout") as mock_stdout, \
         patch("builtins.input", side_effect=["1", "0"]), \
         patch("builtins.print"):
        mock_stdout.isatty.return_value = True
        result = prompt_deduplication(groups, logger)
    assert r1 in result
    assert r4 in result
    assert r2 not in result
    assert r3 not in result
