"""Pulumi entry point for the felcloud.esprit.tn proxy stack.

Resource creation lives in the `resources` package, split by concern:
  - resources/config.py            shared configuration values
  - resources/network.py           networks, subnets, router
  - resources/security_groups.py   security groups & rules
  - resources/ports.py             fixed ports & floating IP
  - resources/compute.py           HAProxy / forward-proxy instances

Importing `resources.compute` here pulls in `resources.ports`, which in
turn pulls in `resources.network` and `resources.security_groups`, so the
whole dependency chain is instantiated by this single import.
"""
import pulumi

from resources.compute import create  # noqa: F401  (imported for its side effects: creates the VMs)
from resources.ports import floatip1, fwd_proxy_port, haproxy_port

_ = create()
# -----------------------------------------------------------------------------
# Outputs
# -----------------------------------------------------------------------------
pulumi.export("public_floating_ip", floatip1.address)
pulumi.export("haproxy_private_ip", haproxy_port.fixed_ips[0].ip_address)
pulumi.export("forward_proxy_private_ip", fwd_proxy_port.fixed_ips[0].ip_address)