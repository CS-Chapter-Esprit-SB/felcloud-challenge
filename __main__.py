import pulumi
#import pulumi_command as command
from resources.compute import create
from resources.helpers import generate_inventory_file 
from resources.sandboxes.loader import load_sandboxes
from resources.sandboxes.team_sandbox import SandboxManager
from resources.network import inbound_subnet,outbound_subnet
from resources.security_groups import secgroup_bastion
from resources.ports import (
    haproxy_backup_port,
    haproxy_primary_port,
    squid_backup_port,
    squid_primary_port,
    vip_haproxy_port,
    vip_squid_port,
    allocated_fip_bastian,
    bastion_port_inbound,
    bastion_port_outbound
)




# -----------------------------------------------------------------------------
# 1. Provision Infrastructure Instances
# -----------------------------------------------------------------------------
compute= create()

# Extract Dynamic IPs from Port Resources
haproxy_master_ip = haproxy_primary_port.fixed_ips[0].ip_address
haproxy_backup_ip = haproxy_backup_port.fixed_ips[0].ip_address
squid_master_ip = squid_primary_port.fixed_ips[0].ip_address
squid_backup_ip = squid_backup_port.fixed_ips[0].ip_address

haproxy_vip = vip_haproxy_port.fixed_ips[0].ip_address
squid_vip = vip_squid_port.fixed_ips[0].ip_address


# -----------------------------------------------------------------------------
# 2. Automatically Generate `inventory.ini`
# -----------------------------------------------------------------------------



inventory_file = pulumi.Output.all(
    allocated_fip_bastian.address,
    haproxy_master_ip,
    haproxy_backup_ip,
    squid_master_ip,
    squid_backup_ip,
    haproxy_vip,
    squid_vip,
    bastion_port_inbound.fixed_ips[0].ip_address,
    bastion_port_outbound.fixed_ips[0].ip_address,
    "10.0.1.0/24",
    "10.0.2.0/24",
).apply(generate_inventory_file)

# -----------------------------------------------------------------------------
# 3. Load Sandboxes from YAML and Create TeamSandboxes
# -----------------------------------------------------------------------------
sandbox_configs = load_sandboxes()

manager = SandboxManager(
    subnets={"inbound_subnet": inbound_subnet, "outbound_subnet": outbound_subnet},
    allowed_ingress=[(secgroup_bastion.id, 22)],
)

# Provision each sandbox.
for config_path, sandbox_config in sandbox_configs:
    sandbox = manager.create_instance(sandbox_config)

pulumi.export("squid_cluster_vip", squid_vip)

pulumi.export("haproxy_master_ip", haproxy_master_ip)
pulumi.export("haproxy_backup_ip", haproxy_backup_ip)
pulumi.export("squid_master_ip", squid_master_ip)
pulumi.export("squid_backup_ip", squid_backup_ip)