# -----------------------------------------------------------------------------
import os
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
        bastion_inbound_ip,
        bastion_outbound_ip,
        inbound_cidr,
        outbound_cidr,
    ) = args

    inventory_content = inspect.cleandoc(
        f"""
        [bastion]
        bastion-host ansible_host={bastion_fip}

        [haproxy_nodes]
        haproxy-master ansible_host={h_master} keepalived_role=MASTER keepalived_priority=101 peer_ip={h_backup}
        haproxy-backup ansible_host={h_backup} keepalived_role=BACKUP keepalived_priority=100 peer_ip={h_master}

        [squid_nodes]
        squid-master ansible_host={s_master} keepalived_role=MASTER keepalived_priority=101 peer_ip={s_backup}
        squid-backup ansible_host={s_backup} keepalived_role=BACKUP keepalived_priority=100 peer_ip={s_master}

        [internal_nodes:children]
        haproxy_nodes
        squid_nodes

        [internal_nodes:vars]
        ansible_ssh_common_args='-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ForwardAgent=yes -o ProxyJump=ubuntu@{bastion_fip}'

        [haproxy_nodes:vars]
        network_interface=ens3
        bastion_gateway={bastion_inbound_ip}
        subnet_cidr={inbound_cidr}

        [squid_nodes:vars]
        network_interface=ens3
        bastion_gateway={bastion_outbound_ip}
        subnet_cidr={outbound_cidr}

        [bastion:vars]
        bastion_inbound_ip={bastion_inbound_ip}
        bastion_outbound_ip={bastion_outbound_ip}
        inbound_cidr={inbound_cidr}
        outbound_cidr={outbound_cidr}

        [all:vars]
        ansible_user=ubuntu
        ansible_ssh_private_key_file=~/.ssh/openstack_ansible.pem

        haproxy_vip={h_vip_ip}
        squid_vip={s_vip_ip}

        inbound_cidr={inbound_cidr}
        outbound_cidr={outbound_cidr}
    """) + "\n"

    with open("inventory.ini", "w", encoding="utf-8") as f:
        _ = f.write(inventory_content)

def create_floating_ip(name: str)-> openstack.networking.FloatingIp:

    ext_network = openstack.networking.get_network(name=external_network_name)
    ext_subnets = openstack.networking.get_subnet_ids_v2(network_id=ext_network.id)
    allocated_fip = openstack.networking.FloatingIp(f"floatip_{name}",
        pool=ext_network.name,
        subnet_ids=ext_subnets.ids)
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