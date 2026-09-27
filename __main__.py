#import os 
from pathlib import Path
import pulumi
#import pulumi_command as command
from resources.compute import create
from resources.bastion import create_bastion
from resources.helpers import create_floating_ip,generate_inventory_file , save_private_key

from resources.ports import (
    allocated_fip,
    haproxy_backup_port,
    haproxy_primary_port,
    squid_backup_port,
    squid_primary_port,
    vip_haproxy_port,
    vip_squid_port,
)
from resources.keypairs import keypair


NOTEBOOK_ROOT = Path(__file__).parent / "notebooks"
## bastion

bastion_pip = create_floating_ip("bastion")
bastion_vm = create_bastion(bastion_pip)

# -----------------------------------------------------------------------------
# 1. Provision Infrastructure Instances
# -----------------------------------------------------------------------------
haproxy_master, haproxy_backup, squid_master, squid_backup = create()

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
    bastion_pip.address,
    haproxy_master_ip,
    haproxy_backup_ip,
    squid_master_ip,
    squid_backup_ip,
    haproxy_vip,
    squid_vip,
).apply(generate_inventory_file)

_ = keypair.private_key.apply(save_private_key)




# -----------------------------------------------------------------------------
# 3. Execute Ansible Playbooks Automatically via Local Command
# -----------------------------------------------------------------------------

# Execute HAProxy Playbook
# run_ansible = command.local.Command(
#     "run-ansible-cluster",
#     create=inventory_file.apply(
#         lambda inv: f"uv run ansible-playbook -i {inv} {NOTEBOOK_ROOT}/site.yml"
#     ),
#     opts=pulumi.ResourceOptions(
#         depends_on=[
#             bastion_vm,
#             haproxy_master,
#             haproxy_backup,
#             squid_master,
#             squid_backup,
#         ]
#     ),
# )


# -----------------------------------------------------------------------------
# 4. Stack Exports
# -----------------------------------------------------------------------------
pulumi.export("private_key_pem", keypair.private_key)
pulumi.export("public_floating_ip", allocated_fip.address)
pulumi.export("haproxy_cluster_vip", haproxy_vip)
pulumi.export("squid_cluster_vip", squid_vip)

pulumi.export("haproxy_master_ip", haproxy_master_ip)
pulumi.export("haproxy_backup_ip", haproxy_backup_ip)
pulumi.export("squid_master_ip", squid_master_ip)
pulumi.export("squid_backup_ip", squid_backup_ip)
pulumi.export("private_key_pem", keypair.private_key)