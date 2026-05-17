import pytest
from cleandns.argument_parser import ArgumentParser

def test_parse_arguments_files_short_flag():
    """Test parsing files using the short flag -f."""
    parser = ArgumentParser()
    _, file_list = parser.parse_arguments(["-f", "file1.dns", "file2.dns"])
    
    assert file_list == ["file1.dns", "file2.dns"]

def test_parse_arguments_files_long_flag():
    """Test parsing files using the long flag --files."""
    parser = ArgumentParser()
    _, file_list = parser.parse_arguments(["--files", "file1.dns", "file2.dns", "file3.dns"])
    
    assert file_list == ["file1.dns", "file2.dns", "file3.dns"]

def test_no_arguments_provided():
    """Test that files is an empty list if -f is not provided."""
    parser = ArgumentParser()
    _, file_list = parser.parse_arguments([])

    assert file_list == []

def test_flag_provided_without_values():
    """Test that parser exits if -f is provided but no files follow (nargs='+')."""
    parser = ArgumentParser()
    
    with pytest.raises(SystemExit):
        parser.parse_arguments(["-f"])

def test_unknown_arguments():
    """Test that parser exits if unknown arguments are provided."""
    parser = ArgumentParser()

    with pytest.raises(SystemExit):
        parser.parse_arguments(["--unknown-flag"])


# --- Config flag tests ---

@pytest.mark.parametrize("flag,attr", [
    (["--omit-origin"],     "omit_origin"),
    (["--human-readable"],  "human_readable"),
    (["--omit-ttl"],        "omit_ttl"),
    (["--omit-record-ttl"], "omit_record_ttl"),
])
def test_config_flag_sets_attribute(flag, attr):
    """Each config flag must set its corresponding DNSConfig attribute to True."""
    config, _ = ArgumentParser().parse_arguments(flag)
    assert getattr(config, attr) is True


def test_config_flags_default_to_false():
    """All config flags must be False when not provided."""
    config, _ = ArgumentParser().parse_arguments([])
    assert config.omit_origin is False
    assert config.human_readable is False
    assert config.omit_ttl is False
    assert config.omit_record_ttl is False


def test_omit_ttl_and_omit_record_ttl_are_mutually_exclusive():
    """--omit-ttl and --omit-record-ttl cannot be used together."""
    with pytest.raises(SystemExit):
        ArgumentParser().parse_arguments(["--omit-ttl", "--omit-record-ttl"])
