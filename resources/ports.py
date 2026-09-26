"""Fixed ports for each instance and the floating IP for inbound traffic."""
import pulumi
import pulumi_openstack as openstack

from .config import external_network_name
from .network import (
    inbound_net,
    inbound_subnet,
    outbound_net,
    outbound_subnet,
    router_interface_inbound,
)
from .security_groups import secgroup_fwd_proxy, secgroup_haproxy

# -----------------------------------------------------------------------------
# Fixed Ports
# -----------------------------------------------------------------------------
haproxy_port = openstack.networking.Port(
    "haproxy-port",
    name="port-haproxy",
    network_id=inbound_net.id,
    fixed_ips=[
        openstack.networking.PortFixedIpArgs(
            subnet_id=inbound_subnet.id,
        )
    ],
    security_group_ids=[secgroup_haproxy.id],
)

fwd_proxy_port = openstack.networking.Port(
    "fwd-proxy-port",
    name="port-fwd-proxy",
    network_id=outbound_net.id,
    fixed_ips=[
        openstack.networking.PortFixedIpArgs(
            subnet_id=outbound_subnet.id,
            ip_address="10.0.2.10",
        )
    ],
    security_group_ids=[secgroup_fwd_proxy.id],
)

# -----------------------------------------------------------------------------
# Floating IP (inbound traffic only)
# -----------------------------------------------------------------------------


ext_network = openstack.networking.get_network(name=external_network_name)
ext_subnets = openstack.networking.get_subnet_ids_v2(network_id=ext_network.id)
floatip1 = openstack.networking.FloatingIp("floatip_1",
    pool=ext_network.name,
    subnet_ids=ext_subnets.ids)

# Neutron refuses to bind a floating IP to a port whose subnet has no path to the
# external network, so the association must wait for the router interface on the
# inbound subnet. Pulumi cannot infer that ordering from the arguments alone.
fip_associate_haproxy = openstack.networking.FloatingIpAssociate(
    "fip-associate-haproxy",
    floating_ip=floatip1.address,
    port_id=haproxy_port.id,
    opts=pulumi.ResourceOptions(depends_on=[router_interface_inbound]),
)