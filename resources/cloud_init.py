"""Cloud-init user_data for gateways and sandboxes.

Gateways only get SSH keys here; HAProxy and Keepalived are installed by Ansible.
Sandboxes are never touched by Ansible: cloud-init fully configures them at boot.
JSON is valid YAML, so documents are serialised with json to avoid quoting bugs.
"""
import json

from .config import sandbox_app_port, ssh_public_keys, vip_address


def _cloud_config(doc: dict) -> str:
    return "#cloud-config\n" + json.dumps(doc, indent=2)


# Gratuitous ARP sender (arping is not on the Ubuntu cloud image). OVN only delivers traffic
# for a shared VIP once its holder has spoken as that address, so whoever claims the VIP
# must announce it. Keepalived does the same on every failover.
_GARP = r'''#!/usr/bin/env python3
import socket, struct, sys, time
ifname, vip = sys.argv[1], sys.argv[2]
s = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.htons(0x0806))
s.bind((ifname, 0x0806))
mac, ip = s.getsockname()[4], socket.inet_aton(vip)
for _ in range(3):
    for op, tha in ((1, bytes(6)), (2, b"\xff" * 6)):  # gratuitous request, then reply
        arp = struct.pack("!HHBBH6s4s6s4s", 1, 0x0800, 6, 4, op, mac, ip, tha, ip)
        s.send(b"\xff" * 6 + mac + b"\x08\x06" + arp)
    time.sleep(1)
'''


def gateway_user_data(claim_vip: bool = False) -> str:
    """SSH keys for every gateway; `claim_vip` additionally bootstraps the VIP (gw-1 only).

    The floating IP points at the VIP, and until Keepalived is installed nobody holds the
    VIP, so Ansible would have no way in. gw-1 claims it once at first boot; Keepalived
    takes ownership when Ansible installs it.
    """
    doc: dict = {"ssh_authorized_keys": ssh_public_keys}
    if claim_vip:
        script = (
            "#!/bin/sh\n"
            "set -eu\n"
            "IF=$(ip -o route show default | awk '{print $5}')\n"
            f"ip addr replace {vip_address}/24 dev \"$IF\"\n"
            f"/usr/local/sbin/rio-garp \"$IF\" {vip_address}\n"
        )
        doc["write_files"] = [
            {"path": "/usr/local/sbin/rio-claim-vip", "permissions": "0755", "content": script},
            {"path": "/usr/local/sbin/rio-garp", "permissions": "0755", "content": _GARP},
        ]
        doc["runcmd"] = [["/usr/local/sbin/rio-claim-vip"]]
    return _cloud_config(doc)


def sandbox_user_data(team: str) -> str:
    """Placeholder app on :8000 that names its team, so routing is visible in a browser."""
    page = f"<h1>{team}</h1><p>Served by vm-sandbox-{team}</p>\n"
    unit = (
        "[Unit]\nDescription=RIO sandbox placeholder app\nAfter=network-online.target\n\n"
        "[Service]\n"
        f"ExecStart=/usr/bin/python3 -m http.server {sandbox_app_port} --directory /srv/rio\n"
        "Restart=always\nDynamicUser=yes\n\n"
        "[Install]\nWantedBy=multi-user.target\n"
    )
    return _cloud_config({
        "ssh_authorized_keys": ssh_public_keys,
        "write_files": [
            {"path": "/srv/rio/index.html", "content": page},
            {"path": "/etc/systemd/system/rio-app.service", "content": unit},
        ],
        "runcmd": [["systemctl", "daemon-reload"], ["systemctl", "enable", "--now", "rio-app"]],
    })
