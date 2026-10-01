"""Security groups and rules for the HAProxy, Squid, Bastion and client instances."""

import pulumi_openstack as openstack


# =============================================================================
# Security Groups
# =============================================================================

secgroup_haproxy = openstack.networking.SecGroup(
    "secgroup-haproxy",
    name="sg-haproxy",
    description="Security group for HAProxy cluster",
)

secgroup_fwd_proxy = openstack.networking.SecGroup(
    "secgroup-fwd-proxy",
    name="sg-forward-proxy",
    description="Security group for Squid forward proxy cluster",
)

secgroup_bastion = openstack.networking.SecGroup(
    "secgroup-bastion",
    name="sg-bastion",
    description="Security group for Bastion NAT gateway and SSH jump host",
)

secgroup_client_vm = openstack.networking.SecGroup(
    "secgroup-client-vm",
    name="sg-client-vm",
    description="Security group for client VM",
)


# =============================================================================
# 1. HAProxy Security Group
# =============================================================================

# -----------------------------------------------------------------------------
# Public HTTPS
# -----------------------------------------------------------------------------

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

# -----------------------------------------------------------------------------
# Keepalived / VRRP
# VRRP = IP protocol 112
# -----------------------------------------------------------------------------

rule_haproxy_vrrp = openstack.networking.SecGroupRule(
    "rule-haproxy-vrrp",
    direction="ingress",
    ethertype="IPv4",
    protocol="vrrp",
    remote_ip_prefix="10.0.1.0/24",
    security_group_id=secgroup_haproxy.id,
)
# -----------------------------------------------------------------------------
# SSH from Bastion / inbound network
# -----------------------------------------------------------------------------

rule_haproxy_ssh = openstack.networking.SecGroupRule(
    "rule-haproxy-ssh",
    direction="ingress",
    ethertype="IPv4",
    protocol="tcp",
    port_range_min=22,
    port_range_max=22,
    remote_ip_prefix="10.0.1.0/24",
    security_group_id=secgroup_haproxy.id,
)

# -----------------------------------------------------------------------------
# Internal ICMP
# -----------------------------------------------------------------------------

rule_haproxy_icmp = openstack.networking.SecGroupRule(
    "rule-haproxy-icmp",
    direction="ingress",
    ethertype="IPv4",
    protocol="icmp",
    remote_ip_prefix="10.0.0.0/16",
    security_group_id=secgroup_haproxy.id,
)


# =============================================================================
# 2. Squid Forward Proxy Security Group
# =============================================================================

# -----------------------------------------------------------------------------
# Squid proxy port
# -----------------------------------------------------------------------------

rule_fwd_proxy_3128 = openstack.networking.SecGroupRule(
    "rule-fwd-proxy-3128",
    direction="ingress",
    ethertype="IPv4",
    protocol="tcp",
    port_range_min=3128,
    port_range_max=3128,
    remote_ip_prefix="10.0.0.0/16",
    security_group_id=secgroup_fwd_proxy.id,
)

# -----------------------------------------------------------------------------
# Keepalived / VRRP
# -----------------------------------------------------------------------------

rule_fwd_proxy_vrrp = openstack.networking.SecGroupRule(
    "rule-fwd-proxy-vrrp",
    direction="ingress",
    ethertype="IPv4",
    protocol="vrrp",
    remote_ip_prefix="10.0.2.0/24",
    security_group_id=secgroup_fwd_proxy.id,
)

# -----------------------------------------------------------------------------
# SSH from inbound subnet / Bastion
# -----------------------------------------------------------------------------

rule_fwd_proxy_ssh = openstack.networking.SecGroupRule(
    "rule-fwd-proxy-ssh",
    direction="ingress",
    ethertype="IPv4",
    protocol="tcp",
    port_range_min=22,
    port_range_max=22,
    remote_ip_prefix="10.0.1.0/24",
    security_group_id=secgroup_fwd_proxy.id,
)

# -----------------------------------------------------------------------------
# Internal ICMP
# -----------------------------------------------------------------------------

rule_fwd_proxy_icmp = openstack.networking.SecGroupRule(
    "rule-fwd-proxy-icmp",
    direction="ingress",
    ethertype="IPv4",
    protocol="icmp",
    remote_ip_prefix="10.0.0.0/16",
    security_group_id=secgroup_fwd_proxy.id,
)


# =============================================================================
# 3. Bastion / NAT Gateway Security Group
# =============================================================================

# -----------------------------------------------------------------------------
# Public SSH
# -----------------------------------------------------------------------------

rule_bastion_ssh = openstack.networking.SecGroupRule(
    "rule-bastion-ssh",
    direction="ingress",
    ethertype="IPv4",
    protocol="tcp",
    port_range_min=22,
    port_range_max=22,
    remote_ip_prefix="0.0.0.0/0",
    security_group_id=secgroup_bastion.id,
)

# -----------------------------------------------------------------------------
# ICMP from internal networks
#
# Required for:
#   HAProxy -> Bastion ping
#   Squid -> Bastion ping
#   Network diagnostics
# -----------------------------------------------------------------------------

rule_bastion_icmp_inbound = openstack.networking.SecGroupRule(
    "rule-bastion-icmp-inbound",
    direction="ingress",
    ethertype="IPv4",
    protocol="icmp",
    remote_ip_prefix="10.0.1.0/24",
    security_group_id=secgroup_bastion.id,
)

rule_bastion_icmp_squid = openstack.networking.SecGroupRule(
    "rule-bastion-icmp-squid",
    direction="ingress",
    ethertype="IPv4",
    protocol="icmp",
    remote_ip_prefix="10.0.2.0/24",
    security_group_id=secgroup_bastion.id,
)

# -----------------------------------------------------------------------------
# TCP from internal networks
#
# Allows internal VMs to reach services on the Bastion when required.
# -----------------------------------------------------------------------------

rule_bastion_tcp_inbound = openstack.networking.SecGroupRule(
    "rule-bastion-tcp-inbound",
    direction="ingress",
    ethertype="IPv4",
    protocol="tcp",
    port_range_min=1,
    port_range_max=65535,
    remote_ip_prefix="10.0.1.0/24",
    security_group_id=secgroup_bastion.id,
)

rule_bastion_tcp_outbound = openstack.networking.SecGroupRule(
    "rule-bastion-tcp-outbound",
    direction="ingress",
    ethertype="IPv4",
    protocol="tcp",
    port_range_min=1,
    port_range_max=65535,
    remote_ip_prefix="10.0.2.0/24",
    security_group_id=secgroup_bastion.id,
)

# -----------------------------------------------------------------------------
# UDP from internal networks
#
# Useful for general routed/NAT traffic and future services.
# -----------------------------------------------------------------------------

rule_bastion_udp_inbound = openstack.networking.SecGroupRule(
    "rule-bastion-udp-inbound",
    direction="ingress",
    ethertype="IPv4",
    protocol="udp",
    port_range_min=1,
    port_range_max=65535,
    remote_ip_prefix="10.0.1.0/24",
    security_group_id=secgroup_bastion.id,
)

rule_bastion_udp_outbound = openstack.networking.SecGroupRule(
    "rule-bastion-udp-outbound",
    direction="ingress",
    ethertype="IPv4",
    protocol="udp",
    port_range_min=1,
    port_range_max=65535,
    remote_ip_prefix="10.0.2.0/24",
    security_group_id=secgroup_bastion.id,
)


# =============================================================================
# 4. Client VM Security Group
# =============================================================================

# -----------------------------------------------------------------------------
# SSH from Bastion / inbound network
# -----------------------------------------------------------------------------

rule_client_vm_ssh = openstack.networking.SecGroupRule(
    "rule-client-vm-ssh",
    direction="ingress",
    ethertype="IPv4",
    protocol="tcp",
    port_range_min=22,
    port_range_max=22,
    remote_ip_prefix="10.0.1.0/24",
    security_group_id=secgroup_client_vm.id,
)

# -----------------------------------------------------------------------------
# HTTP application traffic from internal network
# -----------------------------------------------------------------------------

rule_client_vm_http = openstack.networking.SecGroupRule(
    "rule-client-vm-http",
    direction="ingress",
    ethertype="IPv4",
    protocol="tcp",
    port_range_min=80,
    port_range_max=80,
    remote_ip_prefix="10.0.0.0/16",
    security_group_id=secgroup_client_vm.id,
)

# -----------------------------------------------------------------------------
# Internal ICMP
# -----------------------------------------------------------------------------

rule_client_vm_icmp = openstack.networking.SecGroupRule(
    "rule-client-vm-icmp",
    direction="ingress",
    ethertype="IPv4",
    protocol="icmp",
    remote_ip_prefix="10.0.0.0/16",
    security_group_id=secgroup_client_vm.id,
)

# -----------------------------------------------------------------------------
# Client -> Squid proxy
# -----------------------------------------------------------------------------

rule_client_vm_to_squid = openstack.networking.SecGroupRule(
    "rule-client-vm-to-squid",
    direction="egress",
    ethertype="IPv4",
    protocol="tcp",
    port_range_min=3128,
    port_range_max=3128,
    remote_ip_prefix="10.0.2.0/24",
    security_group_id=secgroup_client_vm.id,
)


rule_fwd_proxy_ssh_bastion = openstack.networking.SecGroupRule(
    "rule-fwd-proxy-ssh-bastion",
    direction="ingress",
    ethertype="IPv4",
    protocol="tcp",
    port_range_min=22,
    port_range_max=22,
    remote_ip_prefix="10.0.2.254/32",
    security_group_id=secgroup_fwd_proxy.id,
)

rule_client_vm_ssh_bastion = openstack.networking.SecGroupRule(
    "rule-client-vm-ssh-bastion",
    direction="ingress",
    ethertype="IPv4",
    protocol="tcp",
    port_range_min=22,
    port_range_max=22,
    remote_ip_prefix="10.0.2.254/32",
    security_group_id=secgroup_client_vm.id,
)