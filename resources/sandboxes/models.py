from ipaddress import IPv4Address, IPv4Network
from typing import ClassVar, Literal, Self

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, model_validator
from dataclasses import dataclass
from pulumi import Output
from pulumi_openstack import compute, networking

class SecurityGroupRuleSpec(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    protocol: Literal["tcp", "udp", "icmp", "any"] = "tcp"
    port: int | None = Field(default=None, ge=1, le=65535)
    port_range: tuple[int, int] | None = None
    ethertype: Literal["IPv4", "IPv6"] = "IPv4"
    remote_ip_prefix: IPv4Network | None = None
    remote_group: Literal["self"] | None = None
    description: str | None = None

    @model_validator(mode="after")
    def _validate(self) -> Self:
        if self.port is not None and self.port_range is not None:
            raise ValueError("use either 'port' or 'port_range', not both")

        if self.port_range is not None:
            lo, hi = self.port_range
            if not (1 <= lo <= hi <= 65535):
                raise ValueError(f"invalid port_range {self.port_range}")

        has_ports = self.port is not None or self.port_range is not None
        if has_ports and self.protocol not in ("tcp", "udp"):
            raise ValueError("ports are only valid for tcp/udp")

        if (self.remote_ip_prefix is None) == (self.remote_group is None):
            raise ValueError("set exactly one of 'remote_ip_prefix' or 'remote_group'")
        return self

    @property
    def min_max(self) -> tuple[int | None, int | None]:
        if self.port is not None:
            return self.port, self.port
        if self.port_range is not None:
            return self.port_range
        return None, None


class SecurityGroupSpec(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    description: str = ""
    ingress: list[SecurityGroupRuleSpec] = Field(default_factory=list)
    egress: list[SecurityGroupRuleSpec] = Field(default_factory=list)


class Sandbox(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    name: str
    url: AnyHttpUrl
    subnet: Literal["inbound_subnet", "outbound_subnet"]
    ip: IPv4Address | None = None
    security_group: SecurityGroupSpec = Field(default_factory=SecurityGroupSpec)

@dataclass(frozen=True)
class SandboxResources:
    """Everything created for one sandbox."""

    name: str
    hostname: str | None
    security_group: networking.SecGroup
    ingress_rules: list[networking.SecGroupRule]
    egress_rules: list[networking.SecGroupRule]
    port: networking.Port
    instance: compute.Instance
    @property
    def id(self) -> Output[str]:
        return self.instance.id

    @property
    def port_id(self) -> Output[str]:
        return self.port.id

    @property
    def security_group_id(self) -> Output[str]:
        return self.security_group.id