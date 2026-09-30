# High Availability OpenStack Infrastructure with Pulumi & Ansible

This repository provisions and configures a highly available (HA) production-grade OpenStack infrastructure utilizing **Pulumi (Python)** for Infrastructure as Code (IaC) and **Ansible** (managed via `uv`) for configuration management.

The setup includes:
- **HAProxy** instances with **Keepalived** for VRRP high availability.
- **Forward Proxy (Squid)** setup.
- Internal networking, router configuration, and security groups with OpenStack anti-spoofing / VRRP allowed address pair management.

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
k
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

Once the infrastructure is up and running, execute the Ansible playbooks using `uv`:

```bash
# Run the site playbook using uv
uv run ansible-playbook -i inventory.ini notebooks/site.yml
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

