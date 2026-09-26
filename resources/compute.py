"""Compute instances for HAProxy and the forward proxy."""
import pulumi_openstack as openstack

from .config import flavor_name, image_name
from .ports import fwd_proxy_port, haproxy_port
def create()-> tuple[openstack.compute.Instance, openstack.compute.Instance]:
    """Create the HAProxy and forward proxy instances."""
    image = openstack.images.get_image(name=image_name)
    flavor = openstack.compute.get_flavor(name=flavor_name)

    haproxy_vm = openstack.compute.Instance(
        "haproxy-instance",
        name="vm-haproxy",
        image_id=image.id,
        flavor_id=flavor.id,
        networks=[openstack.compute.InstanceNetworkArgs(port=haproxy_port.id)],
    )

    fwd_proxy_vm = openstack.compute.Instance(
        "fwd-proxy-instance",
        name="vm-forward-proxy",
        image_id=image.id,
        flavor_id=flavor.id,
        networks=[openstack.compute.InstanceNetworkArgs(port=fwd_proxy_port.id)],
    )
    return haproxy_vm, fwd_proxy_vm