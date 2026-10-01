"""Networks, subnets and the router connecting them to the external provider network."""
import pulumi_openstack as openstack

from .config import external_network_name,inbound_gateway_ip,outbound_gateway_ip

# External provider network
ext_net = openstack.networking.get_network(name=external_network_name)

# -----------------------------------------------------------------------------
# Networks & Subnets
# -----------------------------------------------------------------------------
inbound_net = openstack.networking.Network("inbound-network", name="net-inbound-proxy")


outbound_net = openstack.networking.Network("outbound-network", name="net-outbound-proxy")



inbound_subnet = openstack.networking.Subnet(
    "inbound-subnet",
    name="subnet-inbound-proxy",
    network_id=inbound_net.id,
    cidr="10.0.1.0/24",
    ip_version=4,
    gateway_ip=inbound_gateway_ip,
    allocation_pools=[
        openstack.networking.SubnetAllocationPoolArgs(start="10.0.1.2", end="10.0.1.99")
    ],
    dns_nameservers=["8.8.8.8", "1.1.1.1"],
    enable_dhcp=True,
)

outbound_subnet = openstack.networking.Subnet(
    "outbound-subnet",
    name="subnet-outbound-proxy",
    network_id=outbound_net.id,
    cidr="10.0.2.0/24",
    ip_version=4,
    gateway_ip=outbound_gateway_ip,
    allocation_pools=[
        openstack.networking.SubnetAllocationPoolArgs(start="10.0.2.2", end="10.0.2.99")
    ],
    dns_nameservers=["8.8.8.8", "1.1.1.1"],
    enable_dhcp=True,
)

# -----------------------------------------------------------------------------
# Router & Router Interfaces
# -----------------------------------------------------------------------------
router = openstack.networking.Router(
    "main-router",
    name="router-gateway",
    admin_state_up=True,
    external_network_id=ext_net.id,

)

router_interface_inbound = openstack.networking.RouterInterface(
    "router-interface-inbound",
    router_id=router.id,
    subnet_id=inbound_subnet.id,
)

router_interface_outbound = openstack.networking.RouterInterface(
    "router-interface-outbound",
    router_id=router.id,
    subnet_id=outbound_subnet.id,
)