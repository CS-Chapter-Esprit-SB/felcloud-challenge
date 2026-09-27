"""Security groups and rules for the HAProxy and forward proxy instances."""
import pulumi_openstack as openstack

# -----------------------------------------------------------------------------
# Security Groups
# -----------------------------------------------------------------------------
secgroup_haproxy = openstack.networking.SecGroup("secgroup-haproxy", name="sg-haproxy")
secgroup_fwd_proxy = openstack.networking.SecGroup("secgroup-fwd-proxy", name="sg-forward-proxy")


# =============================================================================
# 1. HAProxy Security Group Rules
# =============================================================================

# Ingress: Public HTTPS (443)
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

# Ingress: VRRP Protocol 112 (Keepalived HA)
rule_haproxy_vrrp = openstack.networking.SecGroupRule(
    "rule-haproxy-vrrp",
    direction="ingress",
    ethertype="IPv4",
    protocol="vrrp",
    remote_ip_prefix="10.0.1.0/24",
    security_group_id=secgroup_haproxy.id,
)

# Ingress: SSH from Inbound Subnet / Bastion
rule_haproxy_ssh_from_bastion = openstack.networking.SecGroupRule(
    "rule-haproxy-ssh-bastion",
    direction="ingress",
    ethertype="IPv4",
    protocol="tcp",
    port_range_min=22,
    port_range_max=22,
    remote_ip_prefix="10.0.1.0/24",
    security_group_id=secgroup_haproxy.id,
)

# Ingress: Internal ICMP (PMTU Discovery & Ping)
rule_haproxy_icmp = openstack.networking.SecGroupRule(
    "rule-haproxy-icmp",
    direction="ingress",
    ethertype="IPv4",
    protocol="icmp",
    remote_ip_prefix="10.0.0.0/16",
    security_group_id=secgroup_haproxy.id,
)

# # Egress: Allow All Outbound Traffic
# rule_haproxy_egress = openstack.networking.SecGroupRule(
#     "rule-haproxy-egress-all",
#     direction="egress",
#     ethertype="IPv4",
#     security_group_id=secgroup_haproxy.id,
# )


# =============================================================================
# 2. Forward Proxy (Squid) Security Group Rules
# =============================================================================

# Ingress: Squid HTTP Proxy Port (3128)
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

# Ingress: VRRP Protocol 112 (Keepalived HA)
rule_fwd_proxy_vrrp = openstack.networking.SecGroupRule(
    "rule-fwd-proxy-vrrp",
    direction="ingress",
    ethertype="IPv4",
    protocol="vrrp",
    remote_ip_prefix="10.0.2.0/24",
    security_group_id=secgroup_fwd_proxy.id,
)

# Ingress: SSH from Inbound Subnet / Bastion
rule_squid_ssh_from_bastion = openstack.networking.SecGroupRule(
    "rule-squid-ssh-bastion",
    direction="ingress",
    ethertype="IPv4",
    protocol="tcp",
    port_range_min=22,
    port_range_max=22,
    remote_ip_prefix="10.0.1.0/24",
    security_group_id=secgroup_fwd_proxy.id,
)

# Ingress: Internal ICMP (PMTU Discovery & Ping)
rule_squid_icmp = openstack.networking.SecGroupRule(
    "rule-squid-icmp",
    direction="ingress",
    ethertype="IPv4",
    protocol="icmp",
    remote_ip_prefix="10.0.0.0/16",
    security_group_id=secgroup_fwd_proxy.id,
)

# # Egress: Allow All Outbound Traffic
# rule_squid_egress = openstack.networking.SecGroupRule(
#     "rule-squid-egress-all",
#     direction="egress",
#     ethertype="IPv4",
#     security_group_id=secgroup_fwd_proxy.id,
# )