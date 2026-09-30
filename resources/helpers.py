# -----------------------------------------------------------------------------
import os

import pulumi
from .config import external_network_name
import pulumi_openstack as openstack
import inspect


def generate_inventory_file(args: list[str]) -> None:
    (
        bastion_fip,
        h_master,
        h_backup,
        s_master,
        s_backup,
        h_vip_ip,
        s_vip_ip,
        app_ip,
    ) = args

    key = "~/.ssh/openstack_ansible.pem"
    ssh_opts = "-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"
    # ProxyJump would ignore ansible_ssh_private_key_file for the bastion hop, so the
    # key is passed explicitly to the jump connection as well.
    jump = f"ssh -W %h:%p -q -i {key} {ssh_opts} ubuntu@{bastion_fip}"

    # The interface name is not set here: the playbooks read it from facts
    # (it is ens3 on FelCloud's Ubuntu image, not eth0).
    inventory_content = inspect.cleandoc(f"""
        [haproxy_nodes]
        haproxy-master ansible_host={h_master} keepalived_role=MASTER keepalived_priority=101 peer_ip={h_backup}
        haproxy-backup ansible_host={h_backup} keepalived_role=BACKUP keepalived_priority=100 peer_ip={h_master}

        [squid_nodes]
        squid-master ansible_host={s_master} keepalived_role=MASTER keepalived_priority=101 peer_ip={s_backup}
        squid-backup ansible_host={s_backup} keepalived_role=BACKUP keepalived_priority=100 peer_ip={s_master}

        [all:vars]
        ansible_user=ubuntu
        ansible_ssh_private_key_file={key}
        haproxy_vip={h_vip_ip}
        squid_vip={s_vip_ip}
        app_backend_ip={app_ip}
        ansible_ssh_common_args='{ssh_opts} -o ProxyCommand="{jump}"'
    """) + "\n"

    with open("inventory.ini", "w", encoding="utf-8") as f:
        _ = f.write(inventory_content)

def create_floating_ip(name: str, opts: pulumi.ResourceOptions | None = None) -> openstack.networking.FloatingIp:

    ext_network = openstack.networking.get_network(name=external_network_name)
    ext_subnets = openstack.networking.get_subnet_ids_v2(network_id=ext_network.id)
    allocated_fip = openstack.networking.FloatingIp(f"floatip_{name}",
        pool=ext_network.name,
        subnet_ids=ext_subnets.ids,
        opts=opts)
    return allocated_fip

def save_private_key(key_content: str) -> None:
    if not key_content:
        return

    # Expand user path ~/.ssh/openstack_ansible.pem
    ssh_dir = os.path.expanduser("~/.ssh")
    key_path = os.path.join(ssh_dir, "openstack_ansible.pem")

    os.makedirs(ssh_dir, exist_ok=True)

    # Write key file
    with open(key_path, "w", encoding="utf-8") as f:
        _ = f.write(key_content)

    # Set strict SSH permissions (chmod 600)
    os.chmod(key_path, 0o600)