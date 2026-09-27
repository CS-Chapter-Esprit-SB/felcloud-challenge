import pulumi
import pulumi_command as command
from resources.compute import create
from resources.ports import (
    allocated_fip,
    haproxy_backup_port,
    haproxy_primary_port,
    squid_backup_port,
    squid_primary_port,
    vip_haproxy_port,
    vip_squid_port,
)

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
def generate_inventory_file(args: list[str]) -> str:
    (
        h_master,
        h_backup,
        s_master,
        s_backup,
        h_vip_ip,
        s_vip_ip,
    ) = args

    inventory_content = f"""[haproxy_nodes]
haproxy-master ansible_host={h_master} keepalived_role=MASTER keepalived_priority=101 peer_ip={h_backup}
haproxy-backup ansible_host={h_backup} keepalived_role=BACKUP keepalived_priority=100 peer_ip={h_master}

[squid_nodes]
squid-master ansible_host={s_master} keepalived_role=MASTER keepalived_priority=101 peer_ip={s_backup}
squid-backup ansible_host={s_backup} keepalived_role=BACKUP keepalived_priority=100 peer_ip={s_master}

[all:vars]
ansible_user=ubuntu
ansible_ssh_private_key_file=~/.ssh/id_rsa
haproxy_vip={h_vip_ip}
squid_vip={s_vip_ip}
network_interface=eth0
"""
    with open("inventory.ini", "w", encoding="utf-8") as f:
        _ = f.write(inventory_content)

    return "inventory.ini"


inventory_file = pulumi.Output.all(
    haproxy_master_ip,
    haproxy_backup_ip,
    squid_master_ip,
    squid_backup_ip,
    haproxy_vip,
    squid_vip,
).apply(generate_inventory_file)


# -----------------------------------------------------------------------------
# 3. Execute Ansible Playbooks Automatically via Local Command
# -----------------------------------------------------------------------------

# Execute HAProxy Playbook
run_haproxy_ansible = command.local.Command(
    "run-ansible-haproxy",
    create=inventory_file.apply(
        lambda inv: f"uv run ansible-playbook -i {inv} deploy_ha_proxy.yml"
    ),
    opts=pulumi.ResourceOptions(
        depends_on=[haproxy_master, haproxy_backup]
    ),
)

# Execute Squid Playbook
run_squid_ansible = command.local.Command(
    "run-ansible-squid",
    create=inventory_file.apply(
        lambda inv: f"uv run ansible-playbook -i {inv} deploy_ha_squid.yml"
    ),
    opts=pulumi.ResourceOptions(
        depends_on=[squid_master, squid_backup]
    ),
)


# -----------------------------------------------------------------------------
# 4. Stack Exports
# -----------------------------------------------------------------------------
pulumi.export("public_floating_ip", allocated_fip.address)
pulumi.export("haproxy_cluster_vip", haproxy_vip)
pulumi.export("squid_cluster_vip", squid_vip)

pulumi.export("haproxy_master_ip", haproxy_master_ip)
pulumi.export("haproxy_backup_ip", haproxy_backup_ip)
pulumi.export("squid_master_ip", squid_master_ip)
pulumi.export("squid_backup_ip", squid_backup_ip)