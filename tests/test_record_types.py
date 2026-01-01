from cleandns.record_types import PTRRecord, RecordType, DNSClass

#def test_a_record_creation(sample_a_record):
#    """Test the creation of an A record."""
#    assert sample_a_record.name == "www.example.com"
#    assert sample_a_record.ttl == 3600
#    assert sample_a_record.type == RecordType.A
#    assert sample_a_record.class_ == DNSClass.IN
#    assert sample_a_record.rdata == "1.2.3.4"
#    assert sample_a_record.comment == "Sample A record"

#def test_ptr_record_sorting():
#    """Test that PTR records sort numerically by IP segments, not alphabetically."""
#    # '10' comes before '2' alphabetically, but after '2' numerically.
#    # Your custom __lt__ should handle this.
#    
#    r1 = PTRRecord(
#        name="10.in-addr.arpa", 
#        ttl=300, 
#        type=RecordType.PTR, 
#        class_=DNSClass.IN, 
#        rdata="host10.com", 
#        comment=None
#    )
#    r2 = PTRRecord(
#        name="2.in-addr.arpa", 
#        ttl=300, 
#        type=RecordType.PTR, 
#        class_=DNSClass.IN, 
#        rdata="host2.com", 
#        comment=None
#    )
#    
#    # Verify r2 is "less than" r1
#    assert r2 < r1
#    
#    # Verify list sorting
#    records = [r1, r2]
#    records.sort()
#    
#    assert records[0] == r2
#    assert records[1] == r1
