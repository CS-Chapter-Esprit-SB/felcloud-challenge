"""Team sandboxes, one per active lease in the `sandboxes` stack config.

Each sandbox is a private port in `sg-sandbox` plus a VM configured entirely by cloud-init.
The lease expiry is copied into the VM metadata so it is visible from OpenStack itself;
renewing a lease updates that metadata in place without rebuilding the VM.
"""
import pulumi
import pulumi_openstack as openstack

from .cloud_init import sandbox_user_data
from .compute import image
from .config import active_sandboxes, sandbox_flavor
from .network import sandbox_net, sandbox_subnet
from .security_groups import sg_sandbox


def create_sandboxes() -> dict[str, dict]:
    """Create the active sandboxes and return {team: {ip, expires}} for the stack outputs."""
    flavor = openstack.compute.get_flavor(name=sandbox_flavor)
    created = {}
    for sandbox in active_sandboxes():
        team = sandbox["team"]
        port = openstack.networking.Port(
            f"sandbox-{team}-port",
            name=f"port-sandbox-{team}",
            network_id=sandbox_net.id,
            fixed_ips=[openstack.networking.PortFixedIpArgs(subnet_id=sandbox_subnet.id)],
            security_group_ids=[sg_sandbox.id],
        )
        openstack.compute.Instance(
            f"sandbox-{team}",
            name=f"vm-sandbox-{team}",
            image_id=image.id,
            flavor_id=flavor.id,
            networks=[openstack.compute.InstanceNetworkArgs(port=port.id)],
            user_data=sandbox_user_data(team),
            metadata={"rio-team": team, "rio-expires": sandbox["expires"]},
            # The port outlives the VM and can only be bound to one server at a time.
            opts=pulumi.ResourceOptions(delete_before_replace=True),
        )
        created[team] = {"ip": port.all_fixed_ips[0], "expires": sandbox["expires"]}
    return created
