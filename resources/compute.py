"""Compute instances for HAProxy and Forward Proxy Active/Passive HA Clusters."""
import json

import pulumi
import pulumi_openstack as openstack
from .keypairs import keypair

from .config import flavor_name, image_name, squid_proxy_pool
from .ports import (
    haproxy_backup_port,
    haproxy_primary_port,
    squid_backup_port,
    squid_primary_port,
    bastion_port,
    client_vm_port,
)


SQUID_VIP = squid_proxy_pool[0]


def _client_user_data() -> str:
    """Demo app on :80 (HAProxy's backend) and proxy settings pointing at the Squid VIP.

    The security group already blocks direct internet egress; these settings make
    standard tools (curl, apt, pip) use Squid instead of failing.
    """
    proxy = f"http://{SQUID_VIP}:3128"
    no_proxy = "localhost,127.0.0.1,10.0.0.0/16,169.254.169.254"
    doc = {
        "write_files": [
            {
                "path": "/etc/environment",
                "append": True,
                "content": (
                    f"http_proxy={proxy}\nhttps_proxy={proxy}\n"
                    f"HTTP_PROXY={proxy}\nHTTPS_PROXY={proxy}\n"
                    f"no_proxy={no_proxy}\nNO_PROXY={no_proxy}\n"
                ),
            },
            {
                "path": "/etc/apt/apt.conf.d/95proxy",
                "content": f'Acquire::http::Proxy "{proxy}";\nAcquire::https::Proxy "{proxy}";\n',
            },
            {"path": "/srv/app/index.html", "content": "<h1>FelCloud demo app</h1><p>vm-client</p>\n"},
            {
                "path": "/etc/systemd/system/demo-app.service",
                "content": (
                    "[Unit]\nDescription=Demo app behind HAProxy\nAfter=network-online.target\n\n"
                    "[Service]\nExecStart=/usr/bin/python3 -m http.server 80 --directory /srv/app\n"
                    "DynamicUser=yes\nAmbientCapabilities=CAP_NET_BIND_SERVICE\nRestart=always\n\n"
                    "[Install]\nWantedBy=multi-user.target\n"
                ),
            },
        ],
        "runcmd": [["systemctl", "daemon-reload"], ["systemctl", "enable", "--now", "demo-app"]],
    }
    return "#cloud-config\n" + json.dumps(doc, indent=2)


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
        opts=pulumi.ResourceOptions(depends_on=[keypair], delete_before_replace=True),
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
        opts=pulumi.ResourceOptions(depends_on=[keypair], delete_before_replace=True),
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
        opts=pulumi.ResourceOptions(depends_on=[keypair], delete_before_replace=True),
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
        opts=pulumi.ResourceOptions(depends_on=[keypair], delete_before_replace=True),
    )

    bastion_vm = openstack.compute.Instance(
        "bastion-instance",
        name="vm-bastion",
        image_id=image.id,
        flavor_id=flavor.id,
        networks=[openstack.compute.InstanceNetworkArgs(port=bastion_port.id)],
        opts=pulumi.ResourceOptions(
            delete_before_replace=True,
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
        user_data=_client_user_data(),
        opts=pulumi.ResourceOptions(
            delete_before_replace=True,
            custom_timeouts=pulumi.CustomTimeouts(
                create="15m",
                update="15m",
                delete="15m",
            )
        ),
        key_pair=keypair.name,
    )
    return haproxy_master, haproxy_backup, squid_master, squid_backup, bastion_vm,client_vm