import subprocess
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from cleandns.named_conf_parser import NamedConfParser
from cleandns.exceptions import NamedConfNotFoundError, NamedConfParseError

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_named_conf(*zones: tuple[str, str, str]) -> str:
    """
    Build a named-checkconf -p snippet containing the given zones.
    Each entry is (zone_name, zone_type, file_path).
    """
    blocks = []
    for name, ztype, fpath in zones:
        blocks.append(
            f'zone "{name}" {{\n'
            f'    type {ztype};\n'
            f'    file "{fpath}";\n'
            f'}};\n'
        )
    return "\n".join(blocks)


# ---------------------------------------------------------------------------
# NamedConfParser.parse — zone type filtering
# ---------------------------------------------------------------------------

def test_parse_returns_master_zones():
    text = make_named_conf(("example.com", "master", "/etc/bind/example.com.zone"))
    result = NamedConfParser.parse(text)
    assert result == {"example.com": Path("/etc/bind/example.com.zone")}


def test_parse_returns_primary_zones():
    """BIND 9.16+ uses 'primary' as the modern alias for 'master'."""
    text = make_named_conf(("example.com", "primary", "/etc/bind/example.com.zone"))
    result = NamedConfParser.parse(text)
    assert result == {"example.com": Path("/etc/bind/example.com.zone")}


def test_parse_ignores_hint_zones():
    text = make_named_conf((".", "hint", "/etc/bind/db.root"))
    assert NamedConfParser.parse(text) == {}


def test_parse_ignores_slave_zones():
    text = make_named_conf(("example.com", "slave", "/var/cache/bind/example.com.zone"))
    assert NamedConfParser.parse(text) == {}


def test_parse_mixed_zone_types():
    """Only master/primary zones appear in the result."""
    text = make_named_conf(
        (".", "hint", "/etc/bind/db.root"),
        ("example.com", "master", "/etc/bind/example.com.zone"),
        ("replica.com", "slave", "/var/cache/bind/replica.com.zone"),
        ("internal.net", "primary", "/etc/bind/internal.net.zone"),
    )
    result = NamedConfParser.parse(text)
    assert result == {
        "example.com": Path("/etc/bind/example.com.zone"),
        "internal.net": Path("/etc/bind/internal.net.zone"),
    }


def test_parse_multiple_master_zones():
    text = make_named_conf(
        ("example.com", "master", "/etc/bind/example.com.zone"),
        ("0.168.192.in-addr.arpa", "master", "/etc/bind/192.168.0.rev"),
    )
    result = NamedConfParser.parse(text)
    assert len(result) == 2
    assert result["0.168.192.in-addr.arpa"] == Path("/etc/bind/192.168.0.rev")


def test_parse_empty_input():
    assert NamedConfParser.parse("") == {}


def test_parse_ignores_non_zone_blocks():
    text = (
        'options {\n'
        '    directory "/var/cache/bind";\n'
        '};\n'
        + make_named_conf(("example.com", "master", "/etc/bind/example.com.zone"))
    )
    result = NamedConfParser.parse(text)
    assert result == {"example.com": Path("/etc/bind/example.com.zone")}


def test_parse_zone_with_extra_options():
    """Extra directives inside a zone block must not break parsing."""
    text = (
        'zone "example.com" {\n'
        '    type master;\n'
        '    file "/etc/bind/example.com.zone";\n'
        '    allow-update { none; };\n'
        '    notify yes;\n'
        '};\n'
    )
    result = NamedConfParser.parse(text)
    assert result == {"example.com": Path("/etc/bind/example.com.zone")}


# ---------------------------------------------------------------------------
# NamedConfParser.from_system — subprocess behaviour
# ---------------------------------------------------------------------------

def test_from_system_parses_stdout():
    text = make_named_conf(("example.com", "master", "/etc/bind/example.com.zone"))
    mock_result = MagicMock()
    mock_result.stdout = text

    with patch("cleandns.named_conf_parser.subprocess.run", return_value=mock_result):
        result = NamedConfParser.from_system()

    assert result == {"example.com": Path("/etc/bind/example.com.zone")}


def test_from_system_raises_when_not_found():
    with patch("cleandns.named_conf_parser.subprocess.run", side_effect=FileNotFoundError):
        with pytest.raises(NamedConfNotFoundError):
            NamedConfParser.from_system()


def test_from_system_raises_on_nonzero_exit():
    with patch(
        "cleandns.named_conf_parser.subprocess.run",
        side_effect=subprocess.CalledProcessError(1, "named-checkconf", stderr="syntax error"),
    ):
        with pytest.raises(NamedConfParseError):
            NamedConfParser.from_system()
