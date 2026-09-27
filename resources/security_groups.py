"""Security groups and rules for the HAProxy and forward proxy instances."""
import pulumi_openstack as openstack

# -----------------------------------------------------------------------------
# HAProxy security group (public HTTPS)
# -----------------------------------------------------------------------------
secgroup_haproxy = openstack.networking.SecGroup("secgroup-haproxy", name="sg-haproxy")

# -----------------------------------------------------------------------------
# Forward proxy security group (internal only)
# -----------------------------------------------------------------------------
secgroup_fwd_proxy = openstack.networking.SecGroup("secgroup-fwd-proxy", name="sg-forward-proxy")


# =============================================================================
# 1. HAProxy Security Group Updates
# =============================================================================

# Existing HTTPS Rule
rule_haproxy_https = openstack.networking.SecGroupRule(
    "rule-haproxy-https",
    direction="ingress",
    ethertype="IPv4",
    protocol="tcp",
    port_range_min=443,
    port_range_max=443,
    remote_ip_prefix="0.0.0.0/0",
    security_group_id=secgroup_haproxy.id,
)

# ADD: SSH Access for Ansible Management
rule_haproxy_ssh = openstack.networking.SecGroupRule(
    "rule-haproxy-ssh",
    direction="ingress",
    ethertype="IPv4",
    protocol="tcp",
    port_range_min=22,
    port_range_max=22,
    remote_ip_prefix="0.0.0.0/0",  # Restrict to your management IP CIDR if possible
    security_group_id=secgroup_haproxy.id,
)

# ADD: VRRP protocol for Keepalived HA clustering (IP Protocol 112)
rule_haproxy_vrrp = openstack.networking.SecGroupRule(
    "rule-haproxy-vrrp",
    direction="ingress",
    ethertype="IPv4",
    protocol="vrrp",
    remote_ip_prefix="10.0.1.0/24",
    security_group_id=secgroup_haproxy.id,
)


# =============================================================================
# 2. Forward Proxy Security Group Updates
# =============================================================================

# Existing Squid Traffic Rule
rule_fwd_proxy_internal = openstack.networking.SecGroupRule(
    "rule-fwd-proxy-internal",
    direction="ingress",
    ethertype="IPv4",
    protocol="tcp",
    port_range_min=3128,
    port_range_max=3128,
    remote_ip_prefix="10.0.0.0/16",
    security_group_id=secgroup_fwd_proxy.id,
)

# ADD: SSH Access for Ansible Management
rule_fwd_proxy_ssh = openstack.networking.SecGroupRule(
    "rule-fwd-proxy-ssh",
    direction="ingress",
    ethertype="IPv4",
    protocol="tcp",
    port_range_min=22,
    port_range_max=22,
    remote_ip_prefix="0.0.0.0/0",  # Or "10.0.0.0/16" if accessing strictly via Bastion/VPN
    security_group_id=secgroup_fwd_proxy.id,
)

# ADD: VRRP protocol for Keepalived HA clustering
rule_fwd_proxy_vrrp = openstack.networking.SecGroupRule(
    "rule-fwd-proxy-vrrp",
    direction="ingress",
    ethertype="IPv4",
    protocol="vrrp",
    remote_ip_prefix="10.0.2.0/24",
    security_group_id=secgroup_fwd_proxy.id,
)