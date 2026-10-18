from dataclasses import dataclass

from pulumi_openstack.compute import Instance
from pulumi_openstack.networking import Port


@dataclass
class SharedInfrastructure:
    haproxy_master: Instance
    haproxy_backup: Instance
    squid_master: Instance
    squid_backup: Instance
    bastion: Instance
    test_client: Instance
    haproxy_vip_port: Port
    squid_vip_port: Port