"""Gateway ports, the shared VIP port, and the single floating IP.

How the VIP works on Neutron:
  1. `vip_port` exists only to own 10.0.1.10. No VM boots on it.
  2. The floating IP is attached to `vip_port`, so it never has to move by API call.
  3. Both gateway ports list the VIP in allowed_address_pairs. Without that, Neutron port
     security drops every packet a gateway sends or receives as 10.0.1.10.
  4. Keepalived on the MASTER adds 10.0.1.10 to its interface and sends gratuitous ARP.
     On failover the BACKUP does the same. Failover is pure L2: no OpenStack API call.
"""
import pulumi
import pulumi_openstack as openstack

from .config import gateway_ips, vip_address
from .network import ext_net, gateway_net, gateway_subnet, router_interface_gateway
from .security_groups import sg_gateway


def _gateway_net_port(logical_name: str, ip: str, **kwargs) -> openstack.networking.Port:
    return openstack.networking.Port(
        logical_name,
        name=f"port-{logical_name.removesuffix('-port')}",
        network_id=gateway_net.id,
        fixed_ips=[openstack.networking.PortFixedIpArgs(subnet_id=gateway_subnet.id, ip_address=ip)],
        security_group_ids=[sg_gateway.id],
        **kwargs,
    )


vip_port = _gateway_net_port("vip-port", vip_address)

gateway_ports = {
    name: _gateway_net_port(
        f"{name}-port",
        ip,
        allowed_address_pairs=[openstack.networking.PortAllowedAddressPairArgs(ip_address=vip_address)],
    )
    for name, ip in gateway_ips.items()
}

# -----------------------------------------------------------------------------
# Floating IP: the one public address all inbound traffic uses
# -----------------------------------------------------------------------------
ext_subnets = openstack.networking.get_subnet_ids_v2(network_id=ext_net.id)
floating_ip = openstack.networking.FloatingIp(
    "floating-ip",
    pool=ext_net.name,
    subnet_ids=ext_subnets.ids,
)

# Neutron refuses to bind a floating IP to a port whose subnet has no path to the
# external network, so the association must wait for the router interface on the
# gateway subnet. Pulumi cannot infer that ordering from the arguments alone.
floating_ip_vip = openstack.networking.FloatingIpAssociate(
    "floating-ip-vip",
    floating_ip=floating_ip.address,
    port_id=vip_port.id,
    opts=pulumi.ResourceOptions(depends_on=[router_interface_gateway]),
)
