class CleanDNSError(Exception):
    """Base for all errors this library raises intentionally."""

class InvalidZoneFileError(CleanDNSError):
    """The zone file could not be parsed or is structurally invalid."""

class MissingSOARecordError(InvalidZoneFileError):
    """Raised when the SOA record is absent."""

class MissingNSRecordError(InvalidZoneFileError):
    """Raised when no NS record exists at the zone origin."""

class EmptyZoneFileError(InvalidZoneFileError):
    """The file contains no parseable zone content (blank, whitespace, or comments only)."""

class NamedConfError(CleanDNSError):
    """Base for errors raised while interacting with named-checkconf."""

class NamedConfNotFoundError(NamedConfError):
    """named-checkconf is not installed or not on PATH."""

class NamedConfParseError(NamedConfError):
    """named-checkconf output could not be parsed."""

class InvalidYAMLError(CleanDNSError):
    """The YAML record file is missing, malformed, or structurally invalid."""

class UnknownRecordTypeError(InvalidYAMLError):
    """A record type in the YAML file is not supported."""

class ZoneNotFoundError(CleanDNSError):
    """A zone referenced in the YAML file has no matching entry in named-checkconf output."""
