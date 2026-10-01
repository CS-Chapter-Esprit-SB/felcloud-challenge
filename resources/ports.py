"""Fixed ports for each instance and the floating IP for inbound traffic."""
import pulumi
import pulumi_openstack as openstack

from .config import  ha_proxy_pool, squid_proxy_pool,backend_ip, haproxy_fip_id, bastion_fip_id
from .helpers import get_reserved_floating_ip
from .network import (
    inbound_net,
    inbound_subnet,
    outbound_net,
    outbound_subnet,
    router_interface_inbound,
)
from .security_groups import (
    secgroup_fwd_proxy, 
    secgroup_haproxy,
    secgroup_client_vm

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
            ip_address=ha_proxy_pool[0]
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
            ip_address=ha_proxy_pool[0]
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
            ip_address=squid_proxy_pool[0]
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
            ip_address=squid_proxy_pool[0]
        )
    ],
)

bastion_port_inbound = openstack.networking.Port(
    "bastion-port",
    name="port-bastion",
    network_id=inbound_subnet.network_id,
    fixed_ips=[
        openstack.networking.PortFixedIpArgs(
            subnet_id=inbound_subnet.id,
            ip_address="10.0.1.254",  # Fixed private management IP
        )
    ],
    port_security_enabled=False,
    #security_group_ids=[secgroup_bastion.id],
)

bastion_port_outbound = openstack.networking.Port(
    "bastion-port-outbound",
    name="port-bastion-outbound",
    network_id=outbound_subnet.network_id,
    fixed_ips=[
        openstack.networking.PortFixedIpArgs(
            subnet_id=outbound_subnet.id,
            ip_address="10.0.2.254",  # Fixed private management IP
        )
    ],
    port_security_enabled=False,
    #security_group_ids=[secgroup_bastion.id],

)


client_vm_port = openstack.networking.Port(
    "client-vm-port",
    name="port-client-vm",
    network_id=outbound_subnet.network_id,
    fixed_ips=[
        openstack.networking.PortFixedIpArgs(
            subnet_id=outbound_subnet.id,
            ip_address=backend_ip,
        )
    ],
    security_group_ids=[secgroup_client_vm.id],
)


# -----------------------------------------------------------------------------
# Floating IP (inbound traffic only)


allocated_fip = get_reserved_floating_ip("haproxy", haproxy_fip_id)

fip_associate_haproxy = openstack.networking.FloatingIpAssociate(
    "fip-associate-haproxy",
    floating_ip=allocated_fip.address,
    port_id=vip_haproxy_port.id,
    opts=pulumi.ResourceOptions(depends_on=[router_interface_inbound]),
)



allocated_fip_bastian = get_reserved_floating_ip("bastion", bastion_fip_id)

fip_associate_bastion = openstack.networking.FloatingIpAssociate(
    "fip-bastion-associate",
    floating_ip=allocated_fip_bastian.address,
    port_id=bastion_port_inbound.id,

)

