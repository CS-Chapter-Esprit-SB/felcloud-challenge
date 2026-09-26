"""Security groups and rules for the HAProxy and forward proxy instances."""
import pulumi_openstack as openstack

# -----------------------------------------------------------------------------
# HAProxy security group (public HTTPS)
# -----------------------------------------------------------------------------
secgroup_haproxy = openstack.networking.SecGroup("secgroup-haproxy", name="sg-haproxy")

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
# Forward proxy security group (internal only)
# -----------------------------------------------------------------------------
secgroup_fwd_proxy = openstack.networking.SecGroup("secgroup-fwd-proxy", name="sg-forward-proxy")

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