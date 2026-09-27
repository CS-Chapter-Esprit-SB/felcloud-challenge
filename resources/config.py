"""Stack configuration: platform constants, addressing plan, and per-stack values.

Per-stack values live in Pulumi.<stack>.yaml under the `felcloud-challenge:` namespace:
    adminCidrs     CIDRs allowed to SSH into the gateways (the only SSH door from outside)
    sshPublicKeys  one public key per teammate, baked in via cloud-init
    sandboxes      list of {team, expires}; an expired entry is dropped on the next `pulumi up`
    sandboxPoolSize  how many private IPs sandboxes may use (default 20)
"""
import ipaddress
import re
from datetime import datetime, timezone

import pulumi

config = pulumi.Config()

external_network_name = "INTERNET"
image_name = config.get("image") or "Ubuntu 22.04 LTS - Jammy Jellyfish"
gateway_flavor = config.get("gatewayFlavor") or "G0.basic.1c2g"
sandbox_flavor = config.get("sandboxFlavor") or "G0.basic.1c1g"

admin_cidrs: list[str] = config.require_object("adminCidrs")
# Changing this list changes the cloud-init user_data, which REPLACES every VM.
# Collect every teammate's key before the first `pulumi up`; add later keys with Ansible.
ssh_public_keys: list[str] = config.require_object("sshPublicKeys")

# -----------------------------------------------------------------------------
# Addressing plan
# -----------------------------------------------------------------------------
# Gateways need static IPs because keepalived's unicast peers are configured by address.
# The VIP is the address that moves between them. All three sit below the DHCP pool so
# Neutron can never hand them to another port.
gateway_cidr = "10.0.1.0/24"
gateway_dhcp_pool = ("10.0.1.100", "10.0.1.250")
vip_address = "10.0.1.10"
gateway_ips = {"gw-1": "10.0.1.11", "gw-2": "10.0.1.12"}

sandbox_cidr = "10.0.2.0/24"
sandbox_app_port = 8000

# Deliberately small so exhaustion and reclamation are easy to observe. The pool gets one
# extra address because OVN's metadata port takes the first free IP of every subnet.
sandbox_pool_size = config.get_int("sandboxPoolSize") or 20
_pool_start = ipaddress.ip_address("10.0.2.10")
sandbox_dhcp_pool = (str(_pool_start), str(_pool_start + sandbox_pool_size))

# -----------------------------------------------------------------------------
# Sandbox leases
# -----------------------------------------------------------------------------
_TEAM_SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{0,30}$")


def active_sandboxes() -> list[dict]:
    """Return the configured sandboxes whose lease has not expired yet.

    Reclamation is declarative: an expired lease simply stops being part of the desired
    state, so the next `pulumi up` deletes the VM and its port, and Neutron returns the
    IP to the pool.
    """
    now = datetime.now(timezone.utc)
    active = []
    for entry in config.get_object("sandboxes") or []:
        team = entry["team"]
        if not _TEAM_SLUG.match(team):
            raise ValueError(f"sandbox team {team!r} must be a lowercase DNS label")
        expires = datetime.fromisoformat(entry["expires"])
        if expires.tzinfo is None:
            raise ValueError(f"sandbox {team!r}: 'expires' needs a timezone, e.g. +01:00")
        if expires <= now:
            pulumi.log.info(f"sandbox {team} expired at {expires.isoformat()}, reclaiming")
            continue
        active.append({"team": team, "expires": expires.isoformat()})
    if len(active) > sandbox_pool_size:
        raise ValueError(
            f"{len(active)} active sandboxes but the pool holds {sandbox_pool_size}: "
            "remove or expire a lease, or raise sandboxPoolSize"
        )
    return active
