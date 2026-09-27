"""Security groups for gateways and sandboxes.

Rules reference *groups* (remote_group_id), not IP addresses. A new sandbox only needs its
port placed in `sg-sandbox`; no rule is ever added or edited per sandbox. The rule count is
constant no matter how many sandboxes exist.

Egress keeps OpenStack's default allow-all rules for now. Restricting sandbox egress is a
Phase 2 isolation item.
"""
import pulumi_openstack as openstack

from .config import admin_cidrs, sandbox_app_port

# -----------------------------------------------------------------------------
# Gateways: public HTTP(S), SSH from admins only, VRRP between the pair
# -----------------------------------------------------------------------------
sg_gateway = openstack.networking.SecGroup(
    "sg-gateway",
    name="sg-gateway",
    description="RIO gateways: public HTTP/S, admin SSH, VRRP between peers",
)

for port in (80, 443):
    openstack.networking.SecGroupRule(
        f"sg-gateway-tcp-{port}",
        direction="ingress",
        ethertype="IPv4",
        protocol="tcp",
        port_range_min=port,
        port_range_max=port,
        remote_ip_prefix="0.0.0.0/0",
        security_group_id=sg_gateway.id,
    )

for i, cidr in enumerate(admin_cidrs):
    openstack.networking.SecGroupRule(
        f"sg-gateway-ssh-admin-{i}",
        direction="ingress",
        ethertype="IPv4",
        protocol="tcp",
        port_range_min=22,
        port_range_max=22,
        remote_ip_prefix=cidr,
        security_group_id=sg_gateway.id,
    )

# Keepalived adverts (IP protocol 112), accepted only from the other gateway.
openstack.networking.SecGroupRule(
    "sg-gateway-vrrp",
    direction="ingress",
    ethertype="IPv4",
    protocol="vrrp",
    remote_group_id=sg_gateway.id,
    security_group_id=sg_gateway.id,
)

# -----------------------------------------------------------------------------
# Sandboxes: reachable from the gateways only. No rule admits sg-sandbox itself,
# so sandboxes cannot reach each other.
# -----------------------------------------------------------------------------
sg_sandbox = openstack.networking.SecGroup(
    "sg-sandbox",
    name="sg-sandbox",
    description="RIO sandboxes: app port and break-glass SSH from gateways only",
)

for name, port in (("app", sandbox_app_port), ("ssh", 22)):
    openstack.networking.SecGroupRule(
        f"sg-sandbox-{name}-from-gateways",
        direction="ingress",
        ethertype="IPv4",
        protocol="tcp",
        port_range_min=port,
        port_range_max=port,
        remote_group_id=sg_gateway.id,
        security_group_id=sg_sandbox.id,
    )
