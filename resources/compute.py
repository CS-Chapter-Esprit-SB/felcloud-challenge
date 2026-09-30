"""Compute instances for HAProxy and Forward Proxy Active/Passive HA Clusters."""
import pulumi
import pulumi_openstack as openstack
from .keypairs import keypair

from .config import flavor_name, image_name
from .ports import (
    haproxy_backup_port,
    haproxy_primary_port,
    squid_backup_port,
    squid_primary_port,
    bastion_port,
    client_vm_port,
)


def create() -> tuple[
    openstack.compute.Instance,
    openstack.compute.Instance,
    openstack.compute.Instance,
    openstack.compute.Instance,
    openstack.compute.Instance,
    openstack.compute.Instance,
]:
    """Create primary and backup instances for HAProxy and Forward Proxy clusters."""
    image = openstack.images.get_image(name=image_name)
    flavor = openstack.compute.get_flavor(name=flavor_name)

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
        opts=pulumi.ResourceOptions(depends_on=[keypair]),
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
        opts=pulumi.ResourceOptions(depends_on=[keypair]),
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
        opts=pulumi.ResourceOptions(depends_on=[keypair]),
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
        opts=pulumi.ResourceOptions(depends_on=[keypair]),
    )

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
    return haproxy_master, haproxy_backup, squid_master, squid_backup, bastion_vm,client_vm