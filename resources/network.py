"""Networks, subnets and the router connecting them to the external provider network."""
import pulumi
import pulumi_openstack as openstack

from .config import external_network_name

# External provider network
ext_net = openstack.networking.get_network(name=external_network_name)

# -----------------------------------------------------------------------------
# Networks & Subnets
# -----------------------------------------------------------------------------
inbound_net = openstack.networking.Network("inbound-network", name="net-inbound-proxy")

inbound_subnet = openstack.networking.Subnet(
    "inbound-subnet",
    name="subnet-inbound-proxy",
    network_id=inbound_net.id,
    cidr="10.0.1.0/24",
    ip_version=4,
    dns_nameservers=["8.8.8.8", "1.1.1.1"],
    enable_dhcp=True,
)

outbound_net = openstack.networking.Network("outbound-network", name="net-outbound-proxy")

outbound_subnet = openstack.networking.Subnet(
    "outbound-subnet",
    name="subnet-outbound-proxy",
    network_id=outbound_net.id,
    cidr="10.0.2.0/24",
    ip_version=4,
    dns_nameservers=["8.8.8.8", "1.1.1.1"],
    # Must stay on: without DHCP the VMs get no address at boot, so cloud-init
    # never reaches the metadata service and the SSH key is never installed.
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
    # Floating IPs only work behind a router with an external gateway, so the router
    # (and its gateway IP) is kept across `pulumi down --exclude-protected`.
    # Its SNAT does not forward traffic on FelCloud (verified 2026-09-30), so
    # internet egress goes through the Squid nodes' own floating IPs instead.
    opts=pulumi.ResourceOptions(protect=True),
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