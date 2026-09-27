"""The two gateway instances. Their software (HAProxy, Keepalived) is installed by Ansible."""
import pulumi
import pulumi_openstack as openstack

from .cloud_init import gateway_user_data
from .config import gateway_flavor, image_name
from .ports import gateway_ports

image = openstack.images.get_image(name=image_name)


def create_gateways() -> dict[str, openstack.compute.Instance]:
    flavor = openstack.compute.get_flavor(name=gateway_flavor)
    return {
        name: openstack.compute.Instance(
            f"{name}-instance",
            name=f"vm-{name}",
            image_id=image.id,
            flavor_id=flavor.id,
            networks=[openstack.compute.InstanceNetworkArgs(port=port.id)],
            user_data=gateway_user_data(claim_vip=(name == "gw-1")),
            # The port outlives the VM and can only be bound to one server at a time.
            opts=pulumi.ResourceOptions(delete_before_replace=True),
        )
        for name, port in gateway_ports.items()
    }
