from datetime import datetime
from collections import defaultdict

from cleandns.exceptions import MissingSOArecord, MissingNSRecord, InvalidZoneFile, EmptyZoneFile
from cleandns.logger import Logger
from cleandns.config import DNSConfig

import os
import shutil
import dns.zone
import dns.rdataclass
import dns.ttl
import dns.rdatatype

from cleandns.record_types import ARecord, NSRecord, CNAMERecord, SOARecord, PTRRecord, RecordType, DNSClass, \
    AbstractRecord

from pathlib import Path

class DNSFile:
    """
    A class to represent a DNS zone file.
    """
    path: Path
    logger: Logger
    ttl: int | None
    origin: str | None
    soa_record: SOARecord | None
    records: dict[RecordType, list[AbstractRecord]]
    modified: bool
    config: DNSConfig

    def __init__(self, path: Path, config: DNSConfig) -> None:
        self.logger = Logger()
        self.config = config
        self.path = path
        self.__set_TTL()
        self.origin = None
        self.__set_DNS_records()
        self.modified = False

    def __set_TTL(self):
        self.ttl = None
        with open(self.path, "r") as file:
            for line in file:
                line_clean = line.split(';')[0].strip()
                if line_clean.upper().startswith("$TTL"):
                    parts = line_clean.split()
                    if len(parts) == 2:
                        try:
                            self.ttl = dns.ttl.from_text(parts[1])
                        except (ValueError, dns.ttl.BadTTL) as e:
                            raise InvalidZoneFile(f"Invalid TTL format in {self.path.name}: {parts[1]}") from e
                    break

    def __set_DNS_records(self):
        self.soa_record = None
        self.records = defaultdict(list)

        with open(self.path, "r") as file:
            file_content = file.read()
        if not file_content.strip():
            raise EmptyZoneFile(f"Zone file {self.path.name} is empty or contains only whitespace.")

        try:
            zone = dns.zone.from_text(file_content)
        except dns.zone.NoSOA as e:
            raise MissingSOArecord(f"Missing SOA record in {self.path.name}") from e
        except dns.zone.NoNS as e:
            raise MissingNSRecord(f"Missing NS record in {self.path.name}") from e
        except dns.exception.DNSException as e:
            raise InvalidZoneFile(f"Could not parse zone file {self.path.name}: {e}") from e

        self.origin = zone.origin.to_text()

        # Mapping for standard records that share the same constructor signature
        record_types = {
            dns.rdatatype.A: (ARecord, RecordType.A),
            dns.rdatatype.NS: (NSRecord, RecordType.NS),
            dns.rdatatype.CNAME: (CNAMERecord, RecordType.CNAME),
            dns.rdatatype.PTR: (PTRRecord, RecordType.PTR),
        }

        for name, node in zone.nodes.items():
            for rdataset in node.rdatasets:
                for rdata in rdataset:
                    rdtype = rdataset.rdtype

                    if rdtype in record_types:
                        record_cls, enum_type = record_types[rdtype]
                        current_record = record_cls(
                            name=name.to_text(),
                            ttl=rdataset.ttl,
                            class_=DNSClass(dns.rdataclass.to_text(rdataset.rdclass)),
                            type=enum_type,
                            rdata=rdata.to_text(),
                            omit_ttl=self.config.omit_record_ttl,
                            comment=None
                        )
                        self.records[enum_type].append(current_record)

                    elif rdtype == dns.rdatatype.SOA:
                        current_record = SOARecord(name=name.to_text(omit_final_dot=True),
                                                   ttl=rdataset.ttl,
                                                   class_=DNSClass(dns.rdataclass.to_text(rdataset.rdclass)),
                                                   type=RecordType.SOA,
                                                   rdata=rdata.to_text(),
                                                   comment=None,
                                                   mname=rdata.mname.to_text(),
                                                   rname=rdata.rname.to_text(),
                                                   serial=rdata.serial,
                                                   refresh=rdata.refresh,
                                                   retry=rdata.retry,
                                                   expire=rdata.expire,
                                                   minimum=rdata.minimum,
                                                   omit_ttl=self.config.omit_record_ttl,
                                                   human_readable=self.config.human_readable
                                                   )

                        self.soa_record = current_record

        if self.soa_record is None:
            raise MissingSOArecord(f"Missing SOA record in {self.path.name}")

    def increment_serial(self):
        """
        Increments the serial number in the SOA record by 1.
        """
        if self.soa_record is not None:
            self.soa_record.increment_serial()

    def remove_duplicates(self):
        """
        Removes duplicate records from the DNS file. 
        A record is considered a duplicate if its string representation is identical to another record of the same type.
        """
        for r_type in self.records:
            unique_records: list[AbstractRecord] = []
            seen = set[str]()
            for record in self.records[r_type]:
                # Use the string representation as a key since records are not hashable
                record_key = str(record)
                if record_key not in seen:
                    seen.add(record_key)
                    unique_records.append(record)
            
            if len(unique_records) < len(self.records[r_type]):
                self.records[r_type] = unique_records
                self.modified = True

    def sort(self):
        """
        Sorts the records in the DNS file.
        The sorting is done first by the name of the record (case-insensitive).
        """
        for records in self.records.values():
            new_order = sorted(records)
            if new_order != records:
                # Update the list in-place and mark as modified
                records[:] = new_order
                self.modified = True

    @property
    def __tmp_path(self) -> Path:
        return self.path.with_name(f"{self.path.name}.tmp")

    def _reconstruct_file(self):
        """
        Reconstructs the DNS file with the current records and writes it to a temporary file.
        """
        # Open the file
        new_file = self.__create_tmp_file()

        # Add the default TTL
        if self.ttl is not None and not self.config.omit_ttl:
            _ = new_file.write(f"$TTL\t{self.ttl}\n")

        # Add the $ORIGIN directive
        if self.origin is not None and not self.config.omit_origin:
            _ = new_file.write(f"$ORIGIN\t{self.origin}\n")

        # Add a blank line for readability
        _ = new_file.write("\n")

        # Add the SOA record
        if self.soa_record:
            _ = new_file.write(f"{self.soa_record}\n")

        # Add a blank line for readability
        _ = new_file.write("\n")

        # Add the NS records
        if RecordType.NS in self.records:
            for record in self.records[RecordType.NS]:
                _ = new_file.write(f"{record}\n")

        # Add a blank line for readability
        _ = new_file.write("\n")

        # Add the rest of the records
        for r_type, records in self.records.items():
            if r_type != RecordType.NS:
                for record in records:
                    _ = new_file.write(f"{record}\n")

        # Close the file
        new_file.close()

    def __create_tmp_file(self):
        """
        Creates a temporary file for writing the new DNS zone data.
        If the file already exists, it will be overwritten.
        """
        # Create tmp file in the same directory as the original to ensure atomic move later
        try:
            self.logger.info(f"Creating the file {self.__tmp_path.name} ...")
            return open(self.__tmp_path, "x")
        except FileExistsError:
            self.logger.warning(f"The file {self.__tmp_path.name} already exists and is going to be overwritten.")
            return open(self.__tmp_path, "w")

    def _replace_file(self):
        """
        Replaces the original DNS file with the newly reconstructed temporary file,
        while creating a backup of the original file with a timestamped name.
        """

        current_date = datetime.now().strftime("%Y-%m-%d_%H-%M-%S-%f")
        backup_path = self.path.with_name(f"{self.path.name}.{current_date}")

        if self.path.exists():
            # Create a backup copy (preserves metadata and keeps original safe until the very end)
            _ = shutil.copy2(self.path, backup_path)
            # Apply original file permissions to the new temp file
            shutil.copymode(self.path, self.__tmp_path)

        # Atomic replacement: Overwrites self.path with tmp_path in one operation
        os.replace(self.__tmp_path, self.path)

    def save(self):
        """
        Saves the changes to the DNS file by reconstructing it and replacing the original file.
        The original file is backed up with a timestamped name before replacement.
        """
        if self.modified:
            self.increment_serial()
            self._reconstruct_file()
            self._replace_file()
