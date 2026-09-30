"""Security groups and rules for the HAProxy and forward proxy instances.

Egress policy: only the Squid nodes may talk to the internet. Every other group is
created without OpenStack's default allow-all egress rules and may only reach the
private network (which includes the Squid VIP on 3128) and the metadata service.
Anything internet-bound is dropped at the port unless it goes through Squid.
"""
import pulumi_openstack as openstack

INTERNAL_CIDR = "10.0.0.0/16"
METADATA_IP = "169.254.169.254/32"


def _egress_internal_only(prefix: str, security_group: openstack.networking.SecGroup) -> None:
    """Allow egress to the private network and the metadata service, nothing else."""
    openstack.networking.SecGroupRule(
        f"{prefix}-egress-internal",
        direction="egress",
        ethertype="IPv4",
        remote_ip_prefix=INTERNAL_CIDR,
        security_group_id=security_group.id,
    )
    # DHCP discovery is broadcast, which the private-network rule above does not cover.
    # Without it a VM never gets an address, never reaches metadata, never gets its key.
    openstack.networking.SecGroupRule(
        f"{prefix}-egress-dhcp",
        direction="egress",
        ethertype="IPv4",
        protocol="udp",
        port_range_min=67,
        port_range_max=67,
        remote_ip_prefix="255.255.255.255/32",
        security_group_id=security_group.id,
    )
    # cloud-init fetches the SSH key and user data from here at boot.
    openstack.networking.SecGroupRule(
        f"{prefix}-egress-metadata",
        direction="egress",
        ethertype="IPv4",
        protocol="tcp",
        port_range_min=80,
        port_range_max=80,
        remote_ip_prefix=METADATA_IP,
        security_group_id=security_group.id,
    )


# -----------------------------------------------------------------------------
# Security Groups
# -----------------------------------------------------------------------------
secgroup_haproxy = openstack.networking.SecGroup(
    "secgroup-haproxy", 
    name="sg-haproxy",
    description="Allow external HTTP/HTTPS ingress to HAProxy Cluster",
    delete_default_rules=True,
)
secgroup_fwd_proxy = openstack.networking.SecGroup(
    "secgroup-fwd-proxy", 
    name="sg-forward-proxy",
    # Keeps the default allow-all egress: Squid is the only way out to the internet.
    description="Squid forward proxy: 3128 from the private network, the only internet egress",
)

secgroup_bastion = openstack.networking.SecGroup(
    "secgroup-bastion",
    name="sg-bastion",
    description="Allow external SSH ingress to Bastion Jump Host",
    delete_default_rules=True,
)
secgroup_client_vm = openstack.networking.SecGroup(
    "secgroup-client-vm",
    name="sg-client-vm",
    description="Client VM: SSH from bastion, app port from HAProxy; egress via Squid only",
    delete_default_rules=True,
)

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

# Ingress: Public HTTP (80), redirected to HTTPS by HAProxy
rule_haproxy_http = openstack.networking.SecGroupRule(
    "rule-haproxy-http",
    direction="ingress",
    ethertype="IPv4",
    protocol="tcp",
    port_range_min=80,
    port_range_max=80,
    remote_ip_prefix="0.0.0.0/0",
    security_group_id=secgroup_haproxy.id,
)

_egress_internal_only("rule-haproxy", secgroup_haproxy)

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

# =============================================================================
# 3. Bastian Security Group Rules
# =============================================================================


# Ingress SSH from internet (0.0.0.0/0)
ssh_rule = openstack.networking.SecGroupRule(
    "rule-bastion-ssh",
    direction="ingress",
    ethertype="IPv4",
    protocol="tcp",
    port_range_min=22,
    port_range_max=22,
    remote_ip_prefix="0.0.0.0/0",
    security_group_id=secgroup_bastion.id,
)

_egress_internal_only("rule-bastion", secgroup_bastion)

# =============================================================================
# 4. client vm Security Group Rules
# =============================================================================

rule_client_vm_ssh_from_bastion = openstack.networking.SecGroupRule(
    "rule-client-vm-ssh-bastion",
    direction="ingress",
    ethertype="IPv4",
    protocol="tcp",
    port_range_min=22,
    port_range_max=22,
    remote_ip_prefix="10.0.1.0/24",  # Inbound Subnet CIDR (Bastion Host)
    security_group_id=secgroup_client_vm.id,
)

# 2. Ingress: Allow HTTP/HTTPS traffic forwarding from HAProxy (10.0.1.0/24 or 10.0.2.0/24)
rule_client_vm_app_from_haproxy = openstack.networking.SecGroupRule(
    "rule-client-vm-app-haproxy",
    direction="ingress",
    ethertype="IPv4",
    protocol="tcp",
    port_range_min=80,
    port_range_max=80,
    remote_ip_prefix="10.0.0.0/16",  # Internal network range
    security_group_id=secgroup_client_vm.id,
)

# 3. Ingress: Allow ICMP for internal network diagnostics / ping
rule_client_vm_icmp = openstack.networking.SecGroupRule(
    "rule-client-vm-icmp",
    direction="ingress",
    ethertype="IPv4",
    protocol="icmp",
    remote_ip_prefix="10.0.0.0/16",
    security_group_id=secgroup_client_vm.id,
)

# 4. Egress: private network (Squid VIP included) and metadata only
_egress_internal_only("rule-client-vm", secgroup_client_vm)
