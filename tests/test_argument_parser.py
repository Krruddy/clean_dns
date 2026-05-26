import pytest
from pathlib import Path
from cleandns.argument_parser import ArgumentParser


def test_parse_arguments_files_short_flag():
    """Test parsing files using the short flag -f."""
    result = ArgumentParser().parse_arguments(["-f", "file1.dns", "file2.dns"])

    assert result.files == ["file1.dns", "file2.dns"]


def test_parse_arguments_files_long_flag():
    """Test parsing files using the long flag --files."""
    result = ArgumentParser().parse_arguments(["--files", "file1.dns", "file2.dns", "file3.dns"])

    assert result.files == ["file1.dns", "file2.dns", "file3.dns"]


def test_no_arguments_provided():
    """Test that files is an empty list if -f is not provided."""
    result = ArgumentParser().parse_arguments([])

    assert result.files == []


def test_flag_provided_without_values():
    """Test that parser exits if -f is provided but no files follow (nargs='+')."""
    with pytest.raises(SystemExit):
        ArgumentParser().parse_arguments(["-f"])


def test_unknown_arguments():
    """Test that parser exits if unknown arguments are provided."""
    with pytest.raises(SystemExit):
        ArgumentParser().parse_arguments(["--unknown-flag"])


# --- Config flag tests ---

@pytest.mark.parametrize("flag,attr", [
    (["--omit-origin"],     "omit_origin"),
    (["--human-readable"],  "human_readable"),
    (["--omit-ttl"],        "omit_ttl"),
    (["--omit-record-ttl"], "omit_record_ttl"),
    (["--dry-run"],         "dry_run"),
    (["--reload"],          "reload"),
])
def test_config_flag_sets_attribute(flag, attr):
    """Each config flag must set its corresponding DNSConfig attribute to True."""
    result = ArgumentParser().parse_arguments(flag)
    assert getattr(result.config, attr) is True


def test_config_flags_default_to_false():
    """All config flags must be False when not provided."""
    result = ArgumentParser().parse_arguments([])
    assert result.config.omit_origin is False
    assert result.config.human_readable is False
    assert result.config.omit_ttl is False
    assert result.config.omit_record_ttl is False
    assert result.config.dry_run is False
    assert result.config.reload is False


def test_omit_ttl_and_omit_record_ttl_are_mutually_exclusive():
    """--omit-ttl and --omit-record-ttl cannot be used together."""
    with pytest.raises(SystemExit):
        ArgumentParser().parse_arguments(["--omit-ttl", "--omit-record-ttl"])


# --- --add-from tests ---

def test_add_from_returns_path(tmp_path):
    yaml = tmp_path / "records.yaml"
    yaml.touch()
    result = ArgumentParser().parse_arguments(["--add-from", str(yaml)])
    assert result.add_from == yaml


def test_add_from_defaults_to_none():
    result = ArgumentParser().parse_arguments([])
    assert result.add_from is None


def test_add_from_and_files_are_mutually_exclusive():
    """--add-from and -f cannot be used together."""
    with pytest.raises(SystemExit):
        ArgumentParser().parse_arguments(["-f", "zone.dns", "--add-from", "records.yaml"])
