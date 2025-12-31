class NoChangesMade(Exception):
    """Raised when no changes were made."""
    pass

class IdenticalEntries(Exception):
    """Raised when entries are identical."""
    pass

class UnknownRecordType(Exception):
    """Raised when a record type is unknown."""
    pass

class MissingSOArecord(Exception):
    """Raised when the SOA record is missing."""
    pass