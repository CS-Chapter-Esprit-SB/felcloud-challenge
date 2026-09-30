"""Security groups and rules for the HAProxy and forward proxy instances."""
import pulumi_openstack as openstack

# -----------------------------------------------------------------------------
# Security Groups
# -----------------------------------------------------------------------------
secgroup_haproxy = openstack.networking.SecGroup(
    "secgroup-haproxy", 
    name="sg-haproxy", 
    description="Allow external HTTPS ingress to HAProxy Cluster"
)
secgroup_fwd_proxy = openstack.networking.SecGroup(
    "secgroup-fwd-proxy", 
    name="sg-forward-proxy",
    description="Allow external HTTP ingress to Forward Proxy"
)

secgroup_bastion = openstack.networking.SecGroup(
    "secgroup-bastion",
    name="sg-bastion",
    description="Allow external SSH ingress to Bastion Jump Host",
)
secgroup_client_vm = openstack.networking.SecGroup(
    "secgroup-client-vm",
    name="sg-client-vm",
    description="Allow external SSH ingress to Client VM",
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

# 4. Egress: Allow outbound TCP to Squid Forward Proxy (Port 3128 on Outbound Subnet)
rule_client_vm_egress_squid = openstack.networking.SecGroupRule(
    "rule-client-vm-egress-squid",
    direction="egress",
    ethertype="IPv4",
    protocol="tcp",
    port_range_min=3128,
    port_range_max=3128,
    remote_ip_prefix="10.0.2.0/24",  # Outbound Subnet CIDR where Squid resides
    security_group_id=secgroup_client_vm.id,
)