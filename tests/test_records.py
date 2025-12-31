import pytest
from cleandns.records import DNSFile
from cleandns.record_types import RecordType
from tests.conftest import forward_sample_zone_content, complex_reverse_zone_content, expected_sorted_ptr_names

def test_load_dns_file(tmp_path, sample_zone_content):
    """Test that the file is parsed correctly."""
    # Create a dummy file
    f = tmp_path / "example.db"
    f.write_text(forward_sample_zone_content)
    
    dns = DNSFile(f)
    
    assert dns.ttl == 3600
    assert dns.soa_record.serial == 2023101001
    assert len(dns.records[RecordType.A]) == 2
    assert len(dns.records[RecordType.NS]) == 2

#def test_remove_duplicates(tmp_path):
#    """Test that duplicates are removed and the modified flag is set."""
#    content = """$TTL 3600
#@ IN SOA ns1.example.com. admin.example.com. ( 1 3600 1800 604800 86400 )
#www IN A 1.2.3.4
#www IN A 1.2.3.4
#"""
#    f = tmp_path / "dup.db"
#    f.write_text(content)
#    
#    dns = DNSFile(f)
#    # Verify we start with 2 records
#    assert len(dns.records[RecordType.A]) == 2
#    
#    dns.remove_duplicates()
#    
#    # Verify we end with 1 record and modified is True
#    assert len(dns.records[RecordType.A]) == 1
#    assert dns.modified is True
#
#def test_sort_logic(tmp_path):
#    """Test that records are sorted alphabetically/numerically."""
#    content = """ 3600
#@ IN SOA ns1.example.com. admin.example.com. ( 1 3600 1800 604800 86400 )
#b.example.com. IN A 1.2.3.4
#a.example.com. IN A 1.2.3.5
#"""
#    f = tmp_path / "sort.db"
#    f.write_text(content)
#    
#    dns = DNSFile(f)
#    dns.sort()
#    
#    records = dns.records[RecordType.A]
#    assert records[0].name == "a.example.com."
#    assert records[1].name == "b.example.com."
#    assert dns.modified is True
#
#def test_save_increments_serial(tmp_path, sample_zone_content):
#    """Test that saving a modified file increments the SOA serial."""
#    f = tmp_path / "serial.db"
#    f.write_text(sample_zone_content)
#    
#    dns = DNSFile(f)
#    # Force modification
#    dns.modified = True 
#    dns.save()
#    
#    # Read the file back to check the serial
#    with open(f, 'r') as f_read:
#        new_content = f_read.read()
#        
#    # Original was 2023101001, should now be 2023101002
#    assert "2023101002" in new_content
