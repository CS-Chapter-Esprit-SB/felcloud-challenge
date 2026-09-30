#!/usr/bin/env bash
# Detach and re-attach the HAProxy floating IP to its VIP port.
#
# Run once after the playbooks have started Keepalived (and again after a HAProxy VM is
# rebuilt). On FelCloud, a floating IP that was attached to a VIP port before any node
# held the VIP stays unroutable until it is re-attached (observed 2026-09-27). Normal
# Keepalived failovers afterwards do not need this.
set -euo pipefail
cd "$(dirname "$0")/.."
stack=$(pulumi stack --show-name)
urn="urn:pulumi:${stack}::felcloud-challenge::openstack:networking/floatingIpAssociate:FloatingIpAssociate::fip-associate-haproxy"
pulumi up --yes --replace "$urn"
