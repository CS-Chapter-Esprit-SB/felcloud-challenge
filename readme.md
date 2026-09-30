# High Availability OpenStack Infrastructure with Pulumi & Ansible

This repository provisions and configures a highly available (HA) production-grade OpenStack infrastructure utilizing **Pulumi (Python)** for Infrastructure as Code (IaC) and **Ansible** (managed via `uv`) for configuration management.

The setup includes:
- **HAProxy** instances with **Keepalived** for VRRP high availability (inbound traffic).
- **Squid forward proxy** pair with **Keepalived** (outbound traffic). It is the *only* way out to the internet: every other VM's security group blocks internet egress, and Squid only allows an allowlist of domains.
- A **bastion** host for SSH access, and a demo app on the client VM behind HAProxy.
- **Reserved public IPs** that survive teardown (see section 5).

---

## Prerequisites

Before running the deployment, ensure you have the following installed on your local control machine:

- **Python 3.10+**
- **[uv](https://github.com/astral-sh/uv)** (Fast Python package installer and runner)
- **[Pulumi CLI](https://www.pulumi.com/docs/install/)**
- **[OpenStack CLI](https://docs.openstack.org/python-openstackclient/latest/)**

---

## 1. Environment Setup

### OpenStack Credentials
Download your OpenStack clouds.yaml file and put it in the root folder of repo 

### Python Virtual Environment & Ansible
Initialize project dependencies using `uv`:

```bash
# Sync dependencies and install Ansible/OpenStack SDKs
uv sync
```

Install [pulumi](https://www.pulumi.com/docs/install/)


---

## 2. Infrastructure Provisioning (Pulumi)

### Initialize Stack & Configuration

```bash
# Select or create your Pulumi stack
pulumi stack select dev || pulumi stack init dev

# Install Pulumi Python dependencies
pulumi install
#authenticate with ur github account
```

### Preview & Deploy

Run Pulumi to provision networks, security groups, ports, and compute instances:

```bash
# Preview changes
uv run pulumi preview 

# Deploy infrastructure
uv run  pulumi up --yes --parallel 4
```

> **Note on VRRP Ports & Address Pairs:**
> Pulumi automatically configures `allowed_address_pairs` on the primary and backup HAProxy ports using `vip_haproxy_port.all_fixed_ips[0]` to allow Keepalived VRRP IP floating (`10.0.1.100`) without binding a static MAC address.

---

## 3. Post-Deployment Egress & SSH Verification

If deploying behind a bastion host or restricted OpenStack network, clear local SSH host keys if infrastructure has been recreated:

```bash
# Clear stale SSH keys for Bastion Floating IP if necessary
ssh-keygen -f '~/.ssh/known_hosts' -R '<BASTION_FLOATING_IP>'
```

Verify egress internet connectivity on the backup instance via Bastion:

```bash
ssh -J ubuntu@<BASTION_FLOATING_IP> ubuntu@10.0.1.12 
```

---

## 4. Configuration Management (Ansible)

Once the infrastructure is up and running, execute the Ansible playbooks using `uv`
(`pulumi up` writes `inventory.ini` and `~/.ssh/openstack_ansible.pem`; no Galaxy roles needed):

```bash
# Squid is deployed first: the HAProxy nodes install their packages through it
uv run ansible-playbook -i inventory.ini notebooks/site.yml
```

Check the public entry point:

```bash
curl -k https://<public_floating_ip>/     # -> "FelCloud demo app"
```

If it does not answer, re-attach the floating IP once. On 2026-09-27 FelCloud did not route a
floating IP attached to a VIP port before any node held the VIP; it did not happen on 2026-09-30.

```bash
scripts/reattach_haproxy_fip.sh
```

### Common Playbook Options

- **Target specific host groups:**
  ```bash
  uv run ansible-playbook -i inventory.ini notebooks/site.yml 
  ```

- **Run with verbose output:**
  ```bash
  uv run ansible-playbook -i inventory.ini notebooks/site.yml -vvv
  ```


---

## 5. Reserved Public IPs & Teardown

These resources are **protected** and survive teardown, so a redeploy never depends on
FelCloud's (often exhausted) floating IP pool:

| Resource | Purpose |
|---|---|
| `floatip_haproxy` | Public entry point (HAProxy VIP) |
| `floatip_bastion` | SSH access |
| `floatip_squid-master`, `floatip_squid-backup` | Internet egress for the Squid nodes |
| `main-router` | Required for floating IPs to work |

FelCloud's router SNAT does not forward traffic (verified 2026-09-30), so the Squid nodes
reach the internet through their own floating IPs. Their security group only admits the
private network, so they are not reachable from the internet.

Tear down everything else with:

```bash
uv run pulumi down --exclude-protected
```

Plain `pulumi down` stops with an error on the protected resources instead of deleting them.
To really release an IP: `pulumi state unprotect <urn>` first.

---

## 6. Failover Tests

`scripts/probe.sh <seconds> <url> [curl args]` requests a URL every 0.2 s and prints every
state change plus the number of failed requests and the longest outage.

```bash
# HAProxy: probe from your laptop, then stop HAProxy (or the whole VM) on the MASTER
scripts/probe.sh 60 https://<public_floating_ip>/ -k
ssh -i ~/.ssh/openstack_ansible.pem -J ubuntu@<BASTION_FLOATING_IP> ubuntu@10.0.1.11 sudo systemctl stop haproxy

# Squid: probe from the client VM through the Squid VIP, then stop Squid on the MASTER
scp -i ~/.ssh/openstack_ansible.pem -o ProxyJump=ubuntu@<BASTION_FLOATING_IP> scripts/probe.sh ubuntu@<client_vm_ip>:
ssh -i ~/.ssh/openstack_ansible.pem -J ubuntu@<BASTION_FLOATING_IP> ubuntu@<client_vm_ip> \
    ./probe.sh 60 https://pypi.org/simple/ -x http://10.0.2.100:3128
ssh -i ~/.ssh/openstack_ansible.pem -J ubuntu@<BASTION_FLOATING_IP> ubuntu@10.0.2.11 sudo systemctl stop squid
```

### Results measured on FelCloud (2026-09-30)

Probe every 0.2 s. HAProxy probed from the internet through the public floating IP;
Squid probed from the client VM through the Squid VIP to `https://pypi.org/robots.txt`.

| Failure injected on the MASTER | Failover outage | Failback outage (master back) |
|---|---|---|
| `systemctl stop haproxy` | 4.8 s (14 failed requests) | 0.4 s (1 failed) |
| HAProxy VM stopped (Nova) | 0.3 s (1 failed) | 1.8 s (2 failed) |
| `systemctl stop squid` | 3.4 s (15 failed) | 0 failed |
| Squid VM stopped (Nova) | 0 failed | 0 failed |

Egress policy, tested from the client VM: allowlisted domains through Squid return 200,
other domains are denied by Squid (403), and direct connections that bypass Squid are
dropped by the security group, even when the VM is given a working route out.

The Keepalived health check is "does the service accept a TCP connection on localhost"
(`/usr/local/bin/check_local_port`), not "is the process running": a stopping Squid keeps its
process for up to 30 s while refusing connections (measured outage was 36 s with a process
check). Don't use `pidof` in Keepalived scripts: it is a symlink to `killall5`, and Keepalived
runs the resolved path, so the check always fails.
