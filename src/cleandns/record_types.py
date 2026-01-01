from abc import abstractmethod, ABC
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Union, Any


class RecordType(Enum):
    SOA = 'SOA'
    NS = 'NS'
    A = 'A'
    AAAA = 'AAAA'
    CNAME = 'CNAME'
    PTR = 'PTR'

class DNSClass(Enum):
    IN = 'IN'
    CH = 'CH'

@dataclass
class AbstractRecord(ABC):
    """Abstract class for DNS records."""
    name: str
    ttl: int
    type: RecordType
    rdata: Union[str, Any]
    comment: Optional[str] = field(compare=False)
    class_: DNSClass

    def __str__(self) -> str:
        """
        Returns the record in the standard DNS zone file format (BIND format).
        """
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
    mname: str 
    rname: str 
    serial: int
    refresh: int
    retry: int 
    expire: int
    minimum: int 

    def __str__(self) -> str:
        return (
            f"{self.name}\t{self.ttl}\t{self.class_.value}\t{self.type.value}\t{self.mname} {self.rname} (\n"
            f"\t\t\t\t{self.serial}\t; serial\n"
            f"\t\t\t\t{self.refresh}\t; refresh\n"
            f"\t\t\t\t{self.retry}\t; retry\n"
            f"\t\t\t\t{self.expire}\t; expire\n"
            f"\t\t\t\t{self.minimum})\t; minimum"
        )
    
    def increment_serial(self):
        """
        Increments the serial number by 1.
        """
        self.serial += 1

    def _format_soa_time(self, seconds):
        """
        
        """
        # Define time units and their corresponding values in seconds
        time_units = [
            ('W', 7 * 24 * 3600),  # 7 days
            ('d', 24 * 3600),       # 1 day
            ('h', 3600),           # 1 hour
            ('m', 60),           # 1 minute
            ('s', 1)             # 1 second
        ]

        # Create a dictionary to store the breakdown
        result = {}

        # Calculate the time in each unit
        for unit_name, unit_value in time_units:
            if seconds >= unit_value:
                result[unit_name], seconds = divmod(seconds, unit_value)

        # Create a formatted string
        formatted_time = ", ".join(f"{value}{unit}" for unit, value in result.items())

        return formatted_time

@dataclass
class NSRecord(AbstractRecord):
    pass

@dataclass
class ARecord(AbstractRecord):
    pass

@dataclass
class AAAARecord(AbstractRecord):
    pass

@dataclass
class CNAMERecord(AbstractRecord):
    pass

@dataclass
class PTRRecord(AbstractRecord):
    def __lt__(self, other: object) -> bool:
        if not isinstance(other, PTRRecord):
            return super().__lt__(other)
        
        def sort_key(name: str):
            # Split into labels and convert to (type_priority, value)
            # 0 for int (priority), 1 for string. This ensures 2 < 10 and 10 < "foo"
            return [
                (0, int(part)) if part.isdigit() else (1, part.lower())
                for part in name.split('.')
            ]
        
        self_key = sort_key(self.name)
        other_key = sort_key(other.name)
        
        if self_key != other_key:
            return self_key < other_key
        
        return str(self.rdata).lower() < str(other.rdata).lower()
