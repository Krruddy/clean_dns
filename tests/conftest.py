import pytest
from cleandns.config import DNSConfig

@pytest.fixture
def default_config():
    return DNSConfig(omit_origin=False, human_readable=False, omit_ttl=False, omit_record_ttl=False)


@pytest.fixture
def sample_ttl_line():
    return "$TTL 3600"

@pytest.fixture
def sample_origin_line():
    return "$ORIGIN example.com."

@pytest.fixture
def sample_soa_block():
    return """@   IN  SOA ns1.example.com. admin.example.com. (
            2023101001 ; serial
            3600       ; refresh
            1800       ; retry
            604800     ; expire
            86400 )    ; minimum"""

@pytest.fixture
def sample_ns_block():
    return """@   IN  NS  ns1.example.com.
@   IN  NS  ns2.example.com."""

@pytest.fixture
def simple_sample_a_records_block():
    return """www     IN  A   192.168.1.10
mail    IN  A   192.168.1.20"""

@pytest.fixture
def complex_sample_a_records_block():
    return """web-prod-01    IN    A    10.100.5.20
web-prod-02    IN    A    10.2.40.5
web-prod-03    IN    A    10.200.1.10
web-prod-04    IN    A    10.50.3.1
web-prod-05    IN    A    10.10.10.10

; Database Clusters (Backend)
db-primary-01  IN    A    10.0.5.50
db-replica-01  IN    A    10.0.5.51
db-replica-02  IN    A    10.0.5.52
redis-cache-01 IN    A    10.255.255.1
redis-cache-02 IN    A    10.1.1.1

; Mail Servers
smtp-relay-01  IN    A    10.15.0.99
imap-store-01  IN    A    10.15.0.20
pop-gw-01      IN    A    10.15.100.5

; Infrastructure / Management
auth-ldap-01   IN    A    10.5.0.2
jump-host-01   IN    A    10.0.0.254
monitor-01     IN    A    10.120.50.30
backup-svr-01  IN    A    10.99.99.99
cicd-runner-01 IN    A    10.45.60.70
k8s-master-01  IN    A    10.8.8.8
k8s-worker-01  IN    A    10.8.8.20"""

@pytest.fixture
def simple_sample_cname_records_block():
    return """ftp    IN  CNAME   www
"""

@pytest.fixture
def simple_sample_ptr_records_block():
    return """10  IN  PTR www.example.com.
20  IN  PTR mail.example.com."""

@pytest.fixture
def complex_sample_ptr_records_block():
    return """20.5.100       IN    PTR    web-prod-01.krruddy.com.
5.40.2         IN    PTR    web-prod-02.krruddy.com.
10.1.200       IN    PTR    web-prod-03.krruddy.com.
1.3.50         IN    PTR    web-prod-04.krruddy.com.
10.10.10       IN    PTR    web-prod-05.krruddy.com.

; Database Clusters (Backend)
50.5.0         IN    PTR    db-primary-01.krruddy.com.
51.5.0         IN    PTR    db-replica-01.krruddy.com.
52.5.0         IN    PTR    db-replica-02.krruddy.com.
1.255.255      IN    PTR    redis-cache-01.krruddy.com.
1.1.1          IN    PTR    redis-cache-02.krruddy.com.

; Mail Servers
99.0.15        IN    PTR    smtp-relay-01.krruddy.com.
20.0.15        IN    PTR    imap-store-01.krruddy.com.
5.100.15       IN    PTR    pop-gw-01.krruddy.com.

; Infrastructure / Management
2.0.5          IN    PTR    auth-ldap-01.krruddy.com.
254.0.0        IN    PTR    jump-host-01.krruddy.com.
30.50.120      IN    PTR    monitor-01.krruddy.com.
99.99.99       IN    PTR    backup-svr-01.krruddy.com.
70.60.45       IN    PTR    cicd-runner-01.krruddy.com.
8.8.8          IN    PTR    k8s-master-01.krruddy.com.
20.8.8         IN    PTR    k8s-worker-01.krruddy.com."""

@pytest.fixture
def forward_sample_zone_content(sample_ttl_line, sample_origin_line, sample_soa_block, sample_ns_block, simple_sample_a_records_block, simple_sample_cname_records_block):
    return f"{sample_ttl_line}\n{sample_origin_line}\n{sample_soa_block}\n\n{sample_ns_block}\n{simple_sample_a_records_block}\n{simple_sample_cname_records_block}\n"

@pytest.fixture
def reverse_sample_zone_content(sample_ttl_line, sample_origin_line, sample_soa_block, sample_ns_block, simple_sample_ptr_records_block):
    return f"{sample_ttl_line}\n{sample_origin_line}\n{sample_soa_block}\n\n{sample_ns_block}\n{simple_sample_ptr_records_block}\n"

@pytest.fixture
def complex_reverse_zone_content(sample_ttl_line, sample_origin_line, sample_soa_block, sample_ns_block, complex_sample_ptr_records_block):
    return f"{sample_ttl_line}\n{sample_origin_line}\n{sample_soa_block}\n\n{sample_ns_block}\n{complex_sample_ptr_records_block}\n"

@pytest.fixture
def complex_forward_zone_content(sample_ttl_line, sample_origin_line, sample_soa_block, sample_ns_block, complex_sample_a_records_block):
    return f"{sample_ttl_line}\n{sample_origin_line}\n{sample_soa_block}\n\n{sample_ns_block}\n{complex_sample_a_records_block}\n"

@pytest.fixture
def expected_sorted_a_names():
    """Returns the expected order of names from the complex A block after alphabetical sorting."""
    return [
        "auth-ldap-01", "backup-svr-01", "cicd-runner-01", "db-primary-01",
        "db-replica-01", "db-replica-02", "imap-store-01", "jump-host-01",
        "k8s-master-01", "k8s-worker-01", "monitor-01", "pop-gw-01", "redis-cache-01",
        "redis-cache-02", "smtp-relay-01", "web-prod-01", "web-prod-02", "web-prod-03",
        "web-prod-04", "web-prod-05"
    ]

@pytest.fixture
def expected_sorted_ptr_names():
    """Returns the expected order of names from the complex PTR block after numeric sorting."""
    return [
        "254.0.0",  
        "50.5.0",   
        "51.5.0",   
        "52.5.0",   
        "1.1.1",    
        "5.40.2",   
        "2.0.5",    
        "8.8.8",    
        "20.8.8",   
        "10.10.10", 
        "20.0.15",  
        "99.0.15",  
        "5.100.15", 
        "70.60.45", 
        "1.3.50",   
        "99.99.99", 
        "20.5.100", 
        "30.50.120",
        "10.1.200", 
        "1.255.255" 
    ]
