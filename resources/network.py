"""Networks, subnets and the router connecting them to the external provider network.

Two networks, one router:
  - gateway network: the two gateways and the VIP. The only network reachable from outside.
  - sandbox network: team sandboxes. Private only; reached through the gateways.
The router routes between them and SNATs all outbound traffic through its single
external IP, so sandboxes get internet access without consuming public addresses.
"""
import pulumi_openstack as openstack

from .config import (
    external_network_name,
    gateway_cidr,
    gateway_dhcp_pool,
    sandbox_cidr,
    sandbox_dhcp_pool,
)

ext_net = openstack.networking.get_network(name=external_network_name)

# -----------------------------------------------------------------------------
# Networks & Subnets
# -----------------------------------------------------------------------------
gateway_net = openstack.networking.Network("gateway-network", name="net-gateway")

gateway_subnet = openstack.networking.Subnet(
    "gateway-subnet",
    name="subnet-gateway",
    network_id=gateway_net.id,
    cidr=gateway_cidr,
    ip_version=4,
    allocation_pools=[
        openstack.networking.SubnetAllocationPoolArgs(
            start=gateway_dhcp_pool[0], end=gateway_dhcp_pool[1]
        )
    ],
    dns_nameservers=["8.8.8.8", "1.1.1.1"],
)

sandbox_net = openstack.networking.Network("sandbox-network", name="net-sandbox")

sandbox_subnet = openstack.networking.Subnet(
    "sandbox-subnet",
    name="subnet-sandbox",
    network_id=sandbox_net.id,
    cidr=sandbox_cidr,
    ip_version=4,
    allocation_pools=[
        openstack.networking.SubnetAllocationPoolArgs(
            start=sandbox_dhcp_pool[0], end=sandbox_dhcp_pool[1]
        )
    ],
    dns_nameservers=["8.8.8.8", "1.1.1.1"],
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

router_interface_gateway = openstack.networking.RouterInterface(
    "router-interface-gateway",
    router_id=router.id,
    subnet_id=gateway_subnet.id,
)

router_interface_sandbox = openstack.networking.RouterInterface(
    "router-interface-sandbox",
    router_id=router.id,
    subnet_id=sandbox_subnet.id,
)
