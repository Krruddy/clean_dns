import pytest
from cleandns.argument_parser import ArgumentParser

def test_parse_arguments_files_short_flag():
    """Test parsing files using the short flag -f."""
    parser = ArgumentParser()
    args = parser.parse_arguments(["-f", "file1.dns", "file2.dns"])
    
    assert args.files == ["file1.dns", "file2.dns"]

def test_parse_arguments_files_long_flag():
    """Test parsing files using the long flag --files."""
    parser = ArgumentParser()
    args = parser.parse_arguments(["--files", "file1.dns", "file2.dns", "file3.dns"])
    
    assert args.files == ["file1.dns", "file2.dns", "file3.dns"]

def test_no_arguments_provided():
    """Test that files is None if -f is not provided."""
    parser = ArgumentParser()
    args = parser.parse_arguments([])

    assert args.files is None

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
