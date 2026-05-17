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
