from __future__ import annotations

import re
from collections.abc import Mapping, Sequence

from pulumi import Input
from pulumi_openstack import compute, networking

from resources.config import flavor, image
from .models import Sandbox, SandboxResources, SharedService


class SandboxManager:
    """
    Security groups are NEVER created here. Each shared service's existing group
    is attached to a port on that service's subnet, and those ports go on the VM.
    """

    def __init__(
        self,
        *,
        subnets: Mapping[str, networking.Subnet],
        shared_services: Sequence[SharedService] = (),
        image_id: Input[str] = image.id,
        flavor_id: Input[str] = flavor.id,
        key_pair: str | None = None,
    ) -> None:
        for svc in shared_services:
            if svc.subnet is not None and svc.subnet not in subnets:
                raise ValueError(f"Shared service {svc.name!r}: unknown subnet {svc.subnet!r}")

        self.subnets: Mapping[str, networking.Subnet] = subnets
        self.shared_services: tuple[SharedService, ...] = tuple(shared_services)
        self.image_id: Input[str] = image_id
        self.flavor_id: Input[str] = flavor_id
        self.key_pair: str | None = key_pair
        self.sandboxes: dict[str, SandboxResources] = {}

    def create_instance(self, sandbox: Sandbox) -> SandboxResources:
        name = self._resource_name(sandbox.name)
        if name in self.sandboxes:
            raise ValueError(f"Sandbox {name!r} was already created")

        home = sandbox.subnet
        if home not in self.subnets:
            raise ValueError(f"Unknown subnet {home!r} for {name}")

        ports = tuple(
            self._create_port(name, key, sandbox if key == home else None, sg_ids)
            for key, sg_ids in self._groups_by_subnet(home).items()
        )
        instance = self._create_vm(name, ports)

        resources = SandboxResources(
            name=name, hostname=sandbox.url.host, ports=ports, instance=instance
        )
        self.sandboxes[name] = resources
        return resources

    @staticmethod
    def _resource_name(raw: str) -> str:
        return re.sub(r"[^a-zA-Z0-9-]", "-", raw).strip("-").lower()

    def _groups_by_subnet(self, home: str) -> dict[str, list[Input[str]]]:
        """Which existing groups go on which subnet's port. The sandbox's own subnet comes first."""
        groups: dict[str, list[Input[str]]] = {home: []}
        for svc in self.shared_services:
            groups.setdefault(svc.subnet or home, []).append(svc.security_group_id)
        return groups

    def _create_port(
        self,
        name: str,
        subnet_key: str,
        sandbox: Sandbox | None,       # given only for the port on the sandbox's own subnet
        security_group_ids: list[Input[str]],
    ) -> networking.Port:
        subnet = self.subnets[subnet_key]
        fixed_ip = networking.PortFixedIpArgs(
            subnet_id=subnet.id,
            ip_address=str(sandbox.ip) if sandbox is not None and sandbox.ip else None,
        )
        resource = (
            f"{name}-port" if sandbox is not None
            else f"{name}-{subnet_key.replace('_', '-')}-port"
        )
        return networking.Port(
            resource,
            network_id=subnet.network_id,
            fixed_ips=[fixed_ip],
            security_group_ids=security_group_ids or None,
            # An empty list would otherwise mean "apply the default group" (allow-all egress).
            no_security_groups=True if not security_group_ids else None,
            admin_state_up=True,
        )

    def _create_vm(self, name: str, ports: Sequence[networking.Port]) -> compute.Instance:
        return compute.Instance(
            f"{name}-instance",
            name=name,
            image_id=self.image_id,
            flavor_id=self.flavor_id,
            key_pair=self.key_pair,
            networks=[compute.InstanceNetworkArgs(port=p.id) for p in ports],
        )