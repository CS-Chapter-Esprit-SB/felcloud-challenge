"""Bastion / Jump Host resources for SSH access into private subnets."""

import pulumi_openstack as openstack
import pulumi
from .config import flavor_name, image_name
from .network import inbound_subnet
from .keypairs import keypair

def create_bastion(
    allocated_fip: openstack.networking.FloatingIp,
) -> openstack.compute.Instance:
    """Create a Bastion VM with a Floating IP and restricted SSH access."""

    # 1. Dedicated Security Group for Bastion
    secgroup_bastion = openstack.networking.SecGroup(
        "secgroup-bastion",
        name="sg-bastion",
        description="Allow external SSH ingress to Bastion Jump Host",
    )

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

    # 2. Bastion Network Port on Inbound Subnet
    bastion_port = openstack.networking.Port(
        "bastion-port",
        name="port-bastion",
        network_id=inbound_subnet.network_id,
        fixed_ips=[
            openstack.networking.PortFixedIpArgs(
                subnet_id=inbound_subnet.id,
                ip_address="10.0.1.254",  # Fixed private management IP
            )
        ],
        security_group_ids=[secgroup_bastion.id],
    )

    # 3. Associate Floating IP with Bastion Port
    fip_associate_bastion = openstack.networking.FloatingIpAssociate(
        "fip-bastion-associate",
        floating_ip=allocated_fip.address,
        port_id=bastion_port.id,
    )

    # 4. Provision Bastion Compute Instance
    image = openstack.images.get_image(name=image_name)
    flavor = openstack.compute.get_flavor(name=flavor_name)

    bastion_vm = openstack.compute.Instance(
        "bastion-instance",
        name="vm-bastion",
        image_id=image.id,
        flavor_id=flavor.id,
        networks=[openstack.compute.InstanceNetworkArgs(port=bastion_port.id)],
        opts=pulumi.ResourceOptions(
            custom_timeouts=pulumi.CustomTimeouts(
                create="15m",
                update="15m",
                delete="15m",
            )
        ),
        key_pair=keypair.name,
    )

    return bastion_vm