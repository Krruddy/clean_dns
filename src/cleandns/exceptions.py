class CleanDNSError(Exception):
    """Base for all errors this library raises intentionally."""

class InvalidZoneFile(CleanDNSError):
    """The zone file could not be parsed or is structurally invalid."""

class MissingSOArecord(InvalidZoneFile):
    """Raised when the SOA record is missing."""

class EmptyZoneFile(InvalidZoneFile):
    """The file contains no parseable zone content (blank, whitespace, or comments only)."""
