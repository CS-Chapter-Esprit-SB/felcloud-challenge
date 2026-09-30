"""Fixed ports for each instance and the floating IP for inbound traffic."""
import pulumi
import pulumi_openstack as openstack

from .config import  ha_proxy_pool, squid_proxy_pool
from .helpers import create_floating_ip
from .network import (
    inbound_net,
    inbound_subnet,
    outbound_net,
    outbound_subnet,
    router_interface_inbound,
    router_interface_outbound,
)
from .security_groups import (
    secgroup_fwd_proxy, 
    secgroup_haproxy,
    secgroup_bastion,
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

bastion_port = openstack.networking.Port(
    "bastion-port",
    name="port-bastion",
    network_id=inbound_subnet.network_id,
    fixed_ips=[
        openstack.networking.PortFixedIpArgs(
            subnet_id=inbound_subnet.id,
            ip_address="10.0.1.254",  # Fixed private management IP
        )
    ],
    security_group_ids=[secgroup_bastion.id],
)
client_vm_port = openstack.networking.Port(
    "client-vm-port",
    name="port-client-vm",
    network_id=outbound_subnet.network_id,  # Point to outbound network
    fixed_ips=[
        openstack.networking.PortFixedIpArgs(
            subnet_id=outbound_subnet.id,   # Point to outbound subnet
        )
    ],
    security_group_ids=[secgroup_client_vm.id],
)


# -----------------------------------------------------------------------------
# Reserved floating IPs
# -----------------------------------------------------------------------------
# Both are protected: `pulumi down --exclude-protected` keeps them allocated to the
# project, so a redeploy never has to ask an often-exhausted pool for new addresses.
# The associations are replaced delete-first so `pulumi up --replace <association>`
# detaches and re-attaches the IP (needed once after the VIP holder changes, see readme).

allocated_fip = create_floating_ip(
    "haproxy",
    pulumi.ResourceOptions(
        protect=True,
        # Adopt 197.5.133.85, reserved earlier under the logical name "floating-ip".
        aliases=[pulumi.Alias(name="floating-ip")],
    ),
)

fip_associate_haproxy = openstack.networking.FloatingIpAssociate(
    "fip-associate-haproxy",
    floating_ip=allocated_fip.address,
    port_id=vip_haproxy_port.id,
    opts=pulumi.ResourceOptions(
        depends_on=[router_interface_inbound], delete_before_replace=True
    ),
)

allocated_fip_bastian = create_floating_ip("bastion", pulumi.ResourceOptions(protect=True))

# Same race as the HAProxy association: Neutron rejects the association until the
# inbound subnet is attached to the router.
fip_associate_bastion = openstack.networking.FloatingIpAssociate(
    "fip-bastion-associate",
    floating_ip=allocated_fip_bastian.address,
    port_id=bastion_port.id,
    opts=pulumi.ResourceOptions(
        depends_on=[router_interface_inbound], delete_before_replace=True
    ),
)

# -----------------------------------------------------------------------------
# Reserved egress IPs for the Squid nodes
# -----------------------------------------------------------------------------
# FelCloud's router SNAT does not forward traffic (verified 2026-09-30: packets reach
# the router and die), while floating-IP egress works. So each Squid node gets its own
# floating IP to reach the internet. Per node rather than on the Squid VIP: the nodes'
# own traffic (apt) is sourced from their fixed IPs, and a FIP on a VIP breaks when the
# VIP holder changes. Not an inbound exposure: sg-forward-proxy only admits 10.0.0.0/16.
squid_egress_fips = {}
for node, port in (("squid-master", squid_primary_port), ("squid-backup", squid_backup_port)):
    fip = create_floating_ip(node, pulumi.ResourceOptions(protect=True))
    openstack.networking.FloatingIpAssociate(
        f"fip-{node}-associate",
        floating_ip=fip.address,
        port_id=port.id,
        opts=pulumi.ResourceOptions(
            depends_on=[router_interface_outbound], delete_before_replace=True
        ),
    )
    squid_egress_fips[node] = fip
