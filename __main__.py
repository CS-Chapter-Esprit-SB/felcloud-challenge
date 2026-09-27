"""Pulumi entry point for the RIO gateway stack.

    Internet -> floating IP -> VIP port (10.0.1.10) -> gw-1 / gw-2 (HAProxy + Keepalived)
             -> sandboxes on the private sandbox network (routed by Host header)

Pulumi owns what exists (networks, ports, VMs, sandbox lifecycle).
Ansible owns what runs inside the gateways; it reads the outputs below as its inventory.
"""
import pulumi

from resources.compute import create_gateways
from resources.config import gateway_ips, vip_address
from resources.ports import floating_ip
from resources.sandboxes import create_sandboxes

create_gateways()
sandboxes = create_sandboxes()

# -----------------------------------------------------------------------------
# Outputs (consumed by the Ansible inventory)
# -----------------------------------------------------------------------------
pulumi.export("public_ip", floating_ip.address)
pulumi.export("vip", vip_address)
pulumi.export("gateways", gateway_ips)
pulumi.export("sandboxes", sandboxes)
pulumi.export("ssh_jump", floating_ip.address.apply(lambda ip: f"ubuntu@{ip}"))
