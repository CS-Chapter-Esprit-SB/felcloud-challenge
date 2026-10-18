"""Compute instances for HAProxy and Forward Proxy Active/Passive HA Clusters."""
import pulumi
import pulumi_openstack as openstack
from resources.keypairs import keypair
from resources.models import SharedInfrastructure
from resources.config import image, flavor
from resources.ports import (
    haproxy_backup_port,
    haproxy_primary_port,
    squid_backup_port,
    squid_primary_port,
    bastion_port_inbound,
    bastion_port_outbound,
    client_vm_port,
    vip_haproxy_port,
    vip_squid_port,
)

from resources.helpers import get_user_data_config

USER_DATA = get_user_data_config()


def create() -> SharedInfrastructure:
    """Create primary and backup instances for HAProxy and Forward Proxy clusters."""


    # -------------------------------------------------------------------------
    # 1. HAProxy Cluster Instances (Inbound)
    # -------------------------------------------------------------------------
    haproxy_master = openstack.compute.Instance(
        "haproxy-master-instance",
        name="vm-haproxy-master",
        image_id=image.id,
        flavor_id=flavor.id,
        networks=[
            openstack.compute.InstanceNetworkArgs(port=haproxy_primary_port.id)
        ],
        key_pair=keypair.name,
    )

    haproxy_backup = openstack.compute.Instance(
        "haproxy-backup-instance",
        name="vm-haproxy-backup",
        image_id=image.id,
        flavor_id=flavor.id,
        networks=[
            openstack.compute.InstanceNetworkArgs(port=haproxy_backup_port.id)
        ],
        key_pair=keypair.name,
    )

    # -------------------------------------------------------------------------
    # 2. Squid Forward Proxy Cluster Instances (Outbound)
    # -------------------------------------------------------------------------
    squid_master = openstack.compute.Instance(
        "squid-master-instance",
        name="vm-squid-master",
        image_id=image.id,
        flavor_id=flavor.id,
        networks=[
            openstack.compute.InstanceNetworkArgs(port=squid_primary_port.id)
        ],
        key_pair=keypair.name,
    )

    squid_backup = openstack.compute.Instance(
        "squid-backup-instance",
        name="vm-squid-backup",
        image_id=image.id,
        flavor_id=flavor.id,
        networks=[
            openstack.compute.InstanceNetworkArgs(port=squid_backup_port.id)
        ],
        key_pair=keypair.name,
    )

    bastion_vm = openstack.compute.Instance(
        "bastion-instance",
        name="vm-bastion",
        image_id=image.id,
        flavor_id=flavor.id,
        networks=[
            openstack.compute.InstanceNetworkArgs(port=bastion_port_inbound.id), 
            openstack.compute.InstanceNetworkArgs(port=bastion_port_outbound.id)
        ],
        opts=pulumi.ResourceOptions(
            custom_timeouts=pulumi.CustomTimeouts(
                create="15m",
                update="15m",
                delete="15m",
            )
        ),
        key_pair=keypair.name,
        user_data=USER_DATA,
    )

    client_vm = openstack.compute.Instance(
        "client-vm-instance",
        name="vm-client",
        image_id=image.id,
        flavor_id=flavor.id,
        networks=[openstack.compute.InstanceNetworkArgs(port=client_vm_port.id)],
        opts=pulumi.ResourceOptions(
            custom_timeouts=pulumi.CustomTimeouts(
                create="15m",
                update="15m",
                delete="15m",
            )
        ),
        key_pair=keypair.name,
    )
    return SharedInfrastructure(
        haproxy_master=haproxy_master,
        haproxy_backup=haproxy_backup,
        squid_master=squid_master,
        squid_backup=squid_backup,
        bastion=bastion_vm,
        haproxy_vip_port=vip_haproxy_port,
        squid_vip_port=vip_squid_port,
        test_client=client_vm
    )