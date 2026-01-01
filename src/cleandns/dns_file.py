from datetime import datetime
from collections import defaultdict
from typing import Dict, List, Optional

from cleandns.exceptions import MissingSOArecord
from cleandns.logger import Logger
import os
import shutil
import dns.zone
import dns.rdataclass
import dns.ttl
import dns.rdatatype

from cleandns.record_types import ARecord, NSRecord, CNAMERecord, SOARecord, PTRRecord, RecordType, DNSClass

from pathlib import Path

class DNSFile:
    """
    A class to represent a DNS zone file.
    """
    path: Path
    logger: Logger
    ttl: Optional[int]
    soa_record: Optional[SOARecord]
    records: Dict[RecordType, List]
    modified: bool

    # The constructor takes the name of the file and sets the type of file, the file content, the space before the incrementation value, the incrementation value and the list of DNS entries.
    def __init__(self, path: Path):
        self.logger = Logger()
        self.path = path
        self.__set_TTL()
        self.__set_DNS_records()
        self.modified = False

    def __set_TTL(self):
        self.ttl = None
        with open(self.path, "r") as file:
            for line in file:
                line_clean = line.split(';')[0].strip()
                if line_clean.upper().startswith("$TTL"):
                    parts = line_clean.split()
                    if len(parts) >= 2:
                        try:
                            self.ttl = dns.ttl.from_text(parts[1])
                        except (ValueError, dns.ttl.BadTTL):
                            raise ValueError(f"Invalid TTL format in {self.path.name}: {parts[1]}")
                    break

    def __set_DNS_records(self):
        self.soa_record = None
        self.records = defaultdict(list)

        with open(self.path, "r") as file:
            file_content = file.read()
        zone = dns.zone.from_text(file_content, origin="", relativize=False, check_origin=False)

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
                            name=name.to_text(omit_final_dot=True),
                            ttl=rdataset.ttl,
                            class_=DNSClass(dns.rdataclass.to_text(rdataset.rdclass)),
                            type=enum_type,
                            rdata=rdata.to_text(),
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
                                                   minimum=rdata.minimum)
                        self.soa_record = current_record

        if self.soa_record is None:
            raise MissingSOArecord(f"Missing SOA record in {self.path.name}")

    def increment_serial(self):
        self.soa_record.increment_serial()

    def remove_duplicates(self):
        for r_type in self.records:
            unique_records = []
            seen = set()
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
        for records in self.records.values():
            new_order = sorted(records)
            if new_order != records:
                # Update the list in-place and mark as modified
                records[:] = new_order
                self.modified = True


    @property
    def tmp_path(self) -> Path:
        return self.path.with_name(f"{self.path.name}.tmp")

    def reconstruct_file(self):
        # Open the file
        new_file = self.__create_tmp_file()

        # Add the default TTL
        if self.ttl is not None:
            new_file.write(f"$TTL\t{self.ttl}\n")

        # Add the SOA record
        if self.soa_record:
            new_file.write(f"{self.soa_record}\n")

        # Add the NS records
        if RecordType.NS in self.records:
            for record in self.records[RecordType.NS]:
                new_file.write(f"{record}\n")

        # Add the rest of the records
        for r_type, records in self.records.items():
            if r_type != RecordType.NS:
                for record in records:
                    new_file.write(f"{record}\n")

        # Close the file
        new_file.close()

    def __create_tmp_file(self):
        # Create tmp file in the same directory as the original to ensure atomic move later
        try:
            self.logger.info(f"Creating the file {self.tmp_path.name} ...")
            return open(self.tmp_path, "x")
        except FileExistsError:
            self.logger.warning(f"The file {self.tmp_path.name} already exists and is going to be overwritten.")
            return open(self.tmp_path, "w")

    def replace_file(self):
        """
        Takes the name of the file and replaces the old file with the new one
        """

        current_date = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        backup_path = self.path.with_name(f"{self.path.name}.{current_date}")

        if self.path.exists():
            # Create a backup copy (preserves metadata and keeps original safe until the very end)
            shutil.copy2(self.path, backup_path)
            # Apply original file permissions to the new temp file
            shutil.copymode(self.path, self.tmp_path)

        # Atomic replacement: Overwrites self.path with tmp_path in one operation
        os.replace(self.tmp_path, self.path)

    def save(self):
        if self.modified:
            self.increment_serial()
        self.reconstruct_file()
        self.replace_file()
