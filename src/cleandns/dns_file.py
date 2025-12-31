from datetime import datetime

from project.logger.Logger import Logger
from project.records.DNSRecords import DNSRecords
import re
import os

import dns.zone
import dns.rdatatype
import dns.rdataclass

from project.records.record.ARecord import ARecord
from project.records.record.CNAMERecord import CNAMERecord
from project.records.record.NSRecord import NSRecord
from project.records.record.PTRRecord import PTRRecord
from project.records.record.SOARecord import SOARecord

from pathlib import Path


class DNSFile:
    # The constructor takes the name of the file and sets the type of file, the file content, the space before the incrementation value, the incrementation value and the list of DNS entries.
    def __init__(self, path: Path):
        self.logger = Logger()
        self.path = path
        self.__set_lookup_type()
        self.__set_TTL()
        self.__set_DNS_records()

    def __set_TTL(self):
        with open(self.path, "r") as file:
            for line in file:
                if "$TTL" in line:
                    self.TTL = int(line.split()[1])
                    break

    def __set_DNS_records(self):
        self.records = DNSRecords(self.is_forward)
        with open(self.path, "r") as f:
            file_content = f.read()
        zone = dns.zone.from_text(file_content, origin="", relativize=False, check_origin=False)

        for name, node in zone.nodes.items():
            for rdataset in node.rdatasets:
                for rdata in rdataset:
                    TTL = self.TTL
                    if rdataset.rdtype == 1:  # A
                        current_record = ARecord(server_name=name.to_text(),
                                                 class_=dns.rdataclass.to_text(rdataset.rdclass),
                                                 type_=dns.rdatatype.to_text(rdataset.rdtype), target=rdata.to_text())
                        current_record.show()
                        self.records.A_records.add_record(current_record)
                    elif rdataset.rdtype == 2:  # NS
                        current_record = NSRecord(TTL=rdataset.ttl,
                                                  server_name=name.to_text(),
                                                  class_=dns.rdataclass.to_text(rdataset.rdclass),
                                                  type_=dns.rdatatype.to_text(rdataset.rdtype),
                                                  target=rdata.to_text(),
                                                  zone=name.to_text())
                        current_record.show()
                        self.records.NS_records.add_record(current_record)
                    elif rdataset.rdtype == 5:  # CNAME
                        current_record = CNAMERecord(alias=name.to_text(),
                                                     class_=dns.rdataclass.to_text(rdataset.rdclass),
                                                     type_=dns.rdatatype.to_text(rdataset.rdtype),
                                                     target=rdata.to_text())
                        current_record.show()
                        self.records.CNAME_records.add_record(current_record)
                    elif rdataset.rdtype == 6:  # SOA
                        current_record = SOARecord(primary_name_server=rdata.mname.to_text(),
                                                   hostmaster=rdata.rname.to_text(),
                                                   serial=rdata.serial,
                                                   refresh=rdata.refresh,
                                                   retry=rdata.retry,
                                                   expire=rdata.expire,
                                                   minimum_ttl=rdata.minimum)
                        current_record.show()
                        self.records.SOA_record = current_record
                    elif rdataset.rdtype == 12:  # PTR
                        current_record = PTRRecord(ip=name.to_text(), class_=dns.rdataclass.to_text(rdataset.rdclass),
                                                   type_=dns.rdatatype.to_text(rdataset.rdtype),
                                                   domain_name=rdata.to_text())
                        current_record.show()
                        self.records.PTR_records.add_record(current_record)

    def __set_lookup_type(self, rev_pattern=r"(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.db$"):
        if re.search(rev_pattern, self.path.name):
            self.is_forward = False
        else:
            self.is_forward = True

    def increment_serial(self):
        self.records.SOA_record.increment_serial()

    def remove_duplicates(self):
        self.records.remove_duplicates()

    def sort(self):
        self.records.sort()
        self.increment_serial()

        # a function named reconstruct_file that reconstructs the file with the new incrementation value and the sorted DNS entries

    def reconstruct_file(self):
        # Open the file
        new_file = self.__create_tmp_file()

        # Add the default TTL
        new_file.write(f"$TTL\t{self.TTL}\n")

        # Add the SOA record
        new_file.write(self.records.SOA_record.generate_output())

        # Add the NS records
        new_file.write(self.records.NS_records.generate_output())

        # Add the rest of the records
        for record_type in self.records.all_records.values():
            if record_type != self.records.NS_records:
                new_file.write(record_type.generate_output())

        # Close the file
        new_file.close()

    def __create_tmp_file(self):
        try:
            self.logger.info(f"Creating the file {self.path.name}.tmp ...")
            return open(f"{self.path.name}.tmp", "x")
        except FileExistsError:
            self.logger.warning(f"The file {self.path.name}.tmp already exists and is going to be overwritten.")
            # clear the file
            file = open(f"{self.path.name}.tmp", "r+")
            file.truncate(0)
            file.close()
            return open(f"{self.path.name}.tmp", "w")

    # a function named reconstruct_line that takes the amount of spaces and the incremented value and returns the line
    def __reconstruct_first_line(self):
        reconstructed_first_line = ""
        for i in range(self.space_before_incre_value):  #(Is there a way to do this in one line ?)
            reconstructed_first_line += ' '
        reconstructed_first_line += str(self.incre_value) + " ;\n"
        return reconstructed_first_line

    # a function named replace_file that takes the name of the file and replaces the old file with the new one
    def replace_file(self):

        current_date = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

        # Rename the original file to a "old" file
        os.rename(self.path, f"{self.path}.{current_date}")
        # Rename the tmp file to the original file
        os.rename(f"{self.path.name}.tmp", self.path)

    def save(self):
        self.reconstruct_file()
        self.replace_file()
