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
import pulumi

from .network import (
    inbound_net,
    inbound_subnet,
    outbound_net,
    outbound_subnet,
    router_interface_inbound,
)

# -----------------------------------------------------------------------------
# 1. HAProxy Active/Passive Cluster Ports & VIP
# -----------------------------------------------------------------------------

# Unattached Virtual IP Port for HAProxy Cluster (10.0.1.100)
vip_haproxy_port = openstack.networking.Port(
    "vip-haproxy-port",
    name="port-vip-haproxy",
    network_id=inbound_net.id,
    fixed_ips=[
        openstack.networking.PortFixedIpArgs(
            subnet_id=inbound_subnet.id,
            ip_address=ha_proxy_pool[0],
        )
    ],
    security_group_ids=[secgroup_haproxy.id],
)

# HAProxy Primary Port
haproxy_primary_port = openstack.networking.Port(
    "haproxy-primary-port",
    name="port-haproxy-master",
    network_id=inbound_net.id,
    fixed_ips=[
        openstack.networking.PortFixedIpArgs(
            subnet_id=inbound_subnet.id,
            ip_address=ha_proxy_pool[1],
        )
    ],
    security_group_ids=[secgroup_haproxy.id],
    allowed_address_pairs=[
        openstack.networking.PortAllowedAddressPairArgs(
            ip_address=vip_haproxy_port.fixed_ips[0].ip_address
        )
    ],
)

# HAProxy Secondary Port
haproxy_backup_port = openstack.networking.Port(
    "haproxy-backup-port",
    name="port-haproxy-backup",
    network_id=inbound_net.id,
    fixed_ips=[
        openstack.networking.PortFixedIpArgs(
            subnet_id=inbound_subnet.id,
            ip_address=ha_proxy_pool[2],
        )
    ],
    security_group_ids=[secgroup_haproxy.id],
    allowed_address_pairs=[
        openstack.networking.PortAllowedAddressPairArgs(
            ip_address=vip_haproxy_port.fixed_ips[0].ip_address
        )
    ],
)



# -----------------------------------------------------------------------------
# 2. Squid Active/Passive Cluster Ports & VIP
# -----------------------------------------------------------------------------

# Unattached Virtual IP Port for Squid Cluster (10.0.2.100)
vip_squid_port = openstack.networking.Port(
    "vip-squid-port",
    name="port-vip-squid",
    network_id=outbound_net.id,
    fixed_ips=[
        openstack.networking.PortFixedIpArgs(
            subnet_id=outbound_subnet.id,
            ip_address=squid_proxy_pool[0],
        )
    ],
    security_group_ids=[secgroup_fwd_proxy.id],
)

# Squid Primary Port
squid_primary_port = openstack.networking.Port(
    "squid-primary-port",
    name="port-squid-master",
    network_id=outbound_net.id,
    fixed_ips=[
        openstack.networking.PortFixedIpArgs(
            subnet_id=outbound_subnet.id,
            ip_address=squid_proxy_pool[1],
        )
    ],
    security_group_ids=[secgroup_fwd_proxy.id],
    allowed_address_pairs=[
        openstack.networking.PortAllowedAddressPairArgs(
            ip_address=vip_squid_port.fixed_ips[0].ip_address
        )
    ],
)

# Squid Secondary Port
squid_backup_port = openstack.networking.Port(
    "squid-backup-port",
    name="port-squid-backup",
    network_id=outbound_net.id,
    fixed_ips=[
        openstack.networking.PortFixedIpArgs(
            subnet_id=outbound_subnet.id,
            ip_address=squid_proxy_pool[2],
        )
    ],
    security_group_ids=[secgroup_fwd_proxy.id],
    allowed_address_pairs=[
        openstack.networking.PortAllowedAddressPairArgs(
            ip_address=vip_squid_port.fixed_ips[0].ip_address
        )
    ],
)

# -----------------------------------------------------------------------------
# Floating IP (inbound traffic only)
# -----------------------------------------------------------------------------


ext_network = openstack.networking.get_network(name=external_network_name)
ext_subnets = openstack.networking.get_subnet_ids_v2(network_id=ext_network.id)
allocated_fip = openstack.networking.FloatingIp("floatip_1",
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
