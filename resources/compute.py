"""Compute instances for HAProxy and Forward Proxy Active/Passive HA Clusters."""

import pulumi_openstack as openstack

from .config import flavor_name, image_name
from .ports import (
    haproxy_backup_port,
    haproxy_primary_port,
    squid_backup_port,
    squid_primary_port,
)


def create() -> tuple[
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
    )

    haproxy_backup = openstack.compute.Instance(
        "haproxy-backup-instance",
        name="vm-haproxy-backup",
        image_id=image.id,
        flavor_id=flavor.id,
        networks=[
            openstack.compute.InstanceNetworkArgs(port=haproxy_backup_port.id)
        ],
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
    )

    squid_backup = openstack.compute.Instance(
        "squid-backup-instance",
        name="vm-squid-backup",
        image_id=image.id,
        flavor_id=flavor.id,
        networks=[
            openstack.compute.InstanceNetworkArgs(port=squid_backup_port.id)
        ],
    )

    return haproxy_master, haproxy_backup, squid_master, squid_backup