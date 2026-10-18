from __future__ import annotations

import re
from collections.abc import Mapping, Sequence


import pulumi
from pulumi import Input
from pulumi_openstack import compute, networking

from resources.config import flavor, image
from .models import Sandbox, SecurityGroupRuleSpec

from .models import SandboxResources


class SandboxManager:
    """
    Provisions isolated client VMs.

    The constructor only stores shared configuration and creates nothing.
    Call `create_instance(sandbox)` to provision a sandbox's security group,
    rules, port and VM.
    """

    def __init__(
        self,
        *,
        subnets: Mapping[str, networking.Subnet],
        allowed_ingress: Sequence[tuple[Input[str], int]] = (),
        image_id: Input[str] = image.id,
        flavor_id: Input[str] = flavor.id,
        key_pair: str | None = None,
    ) -> None:
        self.subnets: Mapping[str, networking.Subnet] = subnets
        self.allowed_ingress: tuple[tuple[Input[str], int], ...] = tuple(allowed_ingress)
        self.image_id: Input[str] = image_id
        self.flavor_id: Input[str] = flavor_id
        self.key_pair: str | None = key_pair

        self.sandboxes: dict[str, SandboxResources] = {}

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def create_instance(self, sandbox: Sandbox) -> SandboxResources:
        name = self._resource_name(sandbox.name)

        if name in self.sandboxes:
            raise ValueError(f"Sandbox {name!r} was already created")

        subnet = self.subnets.get(sandbox.subnet)
        if subnet is None:
            raise ValueError(f"Unknown subnet {sandbox.subnet!r} for {name}")

        hostname = sandbox.url.host

        security_group = self._create_security_group(name, sandbox, hostname)
        ingress_rules, egress_rules = self._create_rules(name, sandbox, security_group)
        port = self._create_port(
            name, sandbox, subnet, security_group, [*ingress_rules, *egress_rules]
        )
        instance = self._create_vm(name, port)

        resources = SandboxResources(
            name=name,
            hostname=hostname,
            security_group=security_group,
            ingress_rules=ingress_rules,
            egress_rules=egress_rules,
            port=port,
            instance=instance,
        )
        self.sandboxes[name] = resources
        return resources

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    @staticmethod
    def _resource_name(raw: str) -> str:
        return re.sub(r"[^a-zA-Z0-9-]", "-", raw).strip("-").lower()

    def _create_security_group(
        self, name: str, sandbox: Sandbox, hostname: str | None
    ) -> networking.SecGroup:
        return networking.SecGroup(
            f"{name}-sg",
            name=f"{name}-sg",
            description=(
                sandbox.security_group.description
                or f"Isolated security group for {hostname}"
            ),
            # Egress is exactly what the YAML declares.
            delete_default_rules=True,
        )

    def _create_rules(
        self, name: str, sandbox: Sandbox, sg: networking.SecGroup
    ) -> tuple[list[networking.SecGroupRule], list[networking.SecGroupRule]]:
        spec = sandbox.security_group
        ingress: list[networking.SecGroupRule] = []
        egress: list[networking.SecGroupRule] = []

        # Rules declared in the sandbox YAML
        for direction, rules, bucket in (
            ("ingress", spec.ingress, ingress),
            ("egress", spec.egress, egress),
        ):
            for index, rule in enumerate(rules):
                bucket.append(self._make_rule(name, sg, direction, index, rule))

        # Shared-infra groups explicitly allowed to connect to the VM
        for index, (source_sg_id, port) in enumerate(self.allowed_ingress):
            ingress.append(
                networking.SecGroupRule(
                    f"{name}-sg-shared-ingress-{index}",
                    security_group_id=sg.id,
                    direction="ingress",
                    ethertype="IPv4",
                    protocol="tcp",
                    port_range_min=port,
                    port_range_max=port,
                    remote_group_id=source_sg_id,
                )
            )

        return ingress, egress

    @staticmethod
    def _make_rule(
        name: str,
        sg: networking.SecGroup,
        direction: str,
        index: int,
        rule: SecurityGroupRuleSpec,
    ) -> networking.SecGroupRule:
        port_min, port_max = rule.min_max
        return networking.SecGroupRule(
            f"{name}-sg-{direction}-{index}",
            security_group_id=sg.id,
            direction=direction,
            ethertype=rule.ethertype,
            protocol=None if rule.protocol == "any" else rule.protocol,
            port_range_min=port_min,
            port_range_max=port_max,
            remote_ip_prefix=str(rule.remote_ip_prefix) if rule.remote_ip_prefix else None,
            remote_group_id=sg.id if rule.remote_group == "self" else None,
            description=rule.description,
        )

    @staticmethod
    def _create_port(
        name: str,
        sandbox: Sandbox,
        subnet: networking.Subnet,
        sg: networking.SecGroup,
        rules: Sequence[networking.SecGroupRule],
    ) -> networking.Port:
        # Neutron allocates an IP from the subnet when ip is None.
        fixed_ip = networking.PortFixedIpArgs(
            subnet_id=subnet.id,
            ip_address=str(sandbox.ip) if sandbox.ip else None,
        )
        return networking.Port(
            f"{name}-port",
            network_id=subnet.network_id,
            fixed_ips=[fixed_ip],
            security_group_ids=[sg.id],
            admin_state_up=True,
            opts=pulumi.ResourceOptions(depends_on=list(rules)),
        )

    def _create_vm(self, name: str, port: networking.Port) -> compute.Instance:
        # Attach to the pre-built port so Nova doesn't pick its own network.
        return compute.Instance(
            f"{name}-instance",
            name=name,
            image_id=self.image_id,
            flavor_id=self.flavor_id,
            key_pair=self.key_pair,
            networks=[compute.InstanceNetworkArgs(port=port.id)],
        )