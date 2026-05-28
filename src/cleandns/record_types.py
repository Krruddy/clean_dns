from abc import ABC
from dataclasses import dataclass, field
from enum import Enum


class RecordType(Enum):
    SOA = 'SOA'
    NS = 'NS'
    A = 'A'
    AAAA = 'AAAA'
    CNAME = 'CNAME'
    MX = 'MX'
    PTR = 'PTR'
    TXT = 'TXT'

class DNSClass(Enum):
    IN = 'IN'
    CH = 'CH'

@dataclass
class AbstractRecord(ABC):
    """Abstract class for DNS records."""
    name: str
    ttl: int
    type: RecordType
    rdata: str
    class_: DNSClass
    omit_ttl: bool = field(compare=False)

    def __str__(self) -> str:
        """
        Returns the record in the standard DNS zone file format (BIND format).
        """
        if self.omit_ttl:
            return f"{self.name}\t{self.class_.value}\t{self.type.value}\t{self.rdata}"
        return f"{self.name}\t{self.ttl}\t{self.class_.value}\t{self.type.value}\t{self.rdata}"


    def __lt__(self, other: object) -> bool:
        if not isinstance(other, AbstractRecord):
            return NotImplemented

        self_name_lower = self.name.lower()
        other_name_lower = other.name.lower()

        if self_name_lower != other_name_lower:
            return self_name_lower < other_name_lower
        return str(self.rdata).lower() < str(other.rdata).lower()

@dataclass
class SOARecord(AbstractRecord):
    """
    Represents a Start of Authority (SOA) DNS record, which contains administrative information about the zone.
    """
    mname: str
    rname: str
    serial: int
    refresh: int
    retry: int
    expire: int
    minimum: int
    human_readable: bool = field(default=False, compare=False)

    def __str__(self) -> str:
        if self.human_readable:
            refresh = self._format_time(self.refresh)
            retry = self._format_time(self.retry)
            expire = self._format_time(self.expire)
            minimum = self._format_time(self.minimum)
        else:
            refresh, retry, expire, minimum = self.refresh, self.retry, self.expire, self.minimum

        if self.omit_ttl:
            header = f"{self.name}\t{self.class_.value}\t{self.type.value}\t{self.mname}\t{self.rname} ("
        else:
            header = f"{self.name}\t{self.ttl}\t{self.class_.value}\t{self.type.value}\t{self.mname}\t{self.rname} ("

        return (
            f"{header}\n"
            f"\t{self.serial}\t; serial\n"
            f"\t{refresh}\t; refresh\n"
            f"\t{retry}\t; retry\n"
            f"\t{expire}\t; expire\n"
            f"\t{minimum}\t; minimum\n"
            f")"
        )
    
    def increment_serial(self):
        """
        Increments the serial number by 1.
        """
        self.serial += 1

    def _format_time(self, seconds: int) -> str:
        """
        Converts a time value in seconds to a human-readable format using weeks, days, hours, minutes, and seconds.
        """
        # Define time units and their corresponding values in seconds
        time_units = [
            ('W', 7 * 24 * 3600),  # 7 days
            ('d', 24 * 3600),       # 1 day
            ('h', 3600),           # 1 hour
            ('m', 60),           # 1 minute
            ('s', 1)             # 1 second
        ]

        result = ""

        # Calculate the time in each unit
        for unit_name, unit_value in time_units:
            if seconds >= unit_value:
                # Calculate how many whole units fit into the remaining seconds
                unit_amount = seconds // unit_value
                # Subtract the calculated amount of time from the total seconds
                seconds -= unit_amount * unit_value
                # Append the amount and unit to the result string
                result += f"{unit_amount}{unit_name}"

        return result

@dataclass
class NSRecord(AbstractRecord):
    pass

@dataclass
class ARecord(AbstractRecord):
    def __lt__(self, other: object) -> bool:
        if not isinstance(other, ARecord):
            return super().__lt__(other)
        self_octets = [int(b) for b in self.rdata.split('.')]
        other_octets = [int(b) for b in other.rdata.split('.')]
        if self_octets != other_octets:
            return self_octets < other_octets
        return self.name.lower() < other.name.lower()

@dataclass
class AAAARecord(AbstractRecord):
    pass

@dataclass
class CNAMERecord(AbstractRecord):
    pass

@dataclass
class MXRecord(AbstractRecord):
    """
    Represents a Mail Exchange (MX) DNS record.
    Sorted by preference (ascending), then by exchange name.
    """

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, MXRecord):
            return super().__lt__(other)
        self_pref, self_exchange = self.rdata.split(None, 1)
        other_pref, other_exchange = other.rdata.split(None, 1)
        if self_pref != other_pref:
            return int(self_pref) < int(other_pref)
        return self_exchange.lower() < other_exchange.lower()


@dataclass
class TXTRecord(AbstractRecord):
    """
    Represents a Text (TXT) DNS record.
    """


@dataclass
class PTRRecord(AbstractRecord):
    """
    Represents a Pointer (PTR) DNS record, which maps an IP address to a hostname.
    """

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, PTRRecord):
            return super().__lt__(other)
        
        def sort_key(name: str):
            parts = name.split('.')
            parts.reverse()
            return [
                (0, int(part)) if part.isdigit() else (1, part.lower())
                for part in parts
            ]
        
        self_key = sort_key(self.name)
        other_key = sort_key(other.name)
        
        if self_key != other_key:
            return self_key < other_key
        
        return str(self.rdata).lower() < str(other.rdata).lower()
