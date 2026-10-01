# High Availability OpenStack Infrastructure with Pulumi & Ansible

This repository provisions and configures a highly available OpenStack infrastructure using **Pulumi (Python)** for Infrastructure as Code (IaC) and **Ansible**, managed through `uv`, for configuration management.

The infrastructure is designed around highly available networking and application routing, with automated provisioning, configuration, and failover.

## Architecture

The setup includes:

* **HAProxy** instances with **Keepalived/VRRP** for high availability.
* **Squid** forward proxies with Keepalived/VRRP.
* A **Bastion/NAT gateway** providing controlled access to internal instances.
* Internal OpenStack networks, routers, ports, and security groups.
* OpenStack **allowed address pairs** for VRRP virtual IPs and anti-spoofing.
* Host-based HAProxy routing using a configurable `hosts.map`.
* Automated HAProxy configuration validation before deployment.

### Network Overview

| Component        | Address                |
| ---------------- | ---------------------- |
| Inbound subnet   | `10.0.1.0/24`          |
| Outbound subnet  | `10.0.2.0/24`          |
| Neutron router   | `10.0.1.1`, `10.0.2.1` |
| HAProxy master   | `10.0.1.11`            |
| HAProxy backup   | `10.0.1.12`            |
| HAProxy VIP      | `10.0.1.100`           |
| Squid master     | `10.0.2.11`            |
| Squid backup     | `10.0.2.12`            |
| Squid VIP        | `10.0.2.100`           |
| Bastion inbound  | `10.0.1.254`           |
| Bastion outbound | `10.0.2.254`           |
| Client VM        | `10.0.2.179`           |

---

## Prerequisites

Before running the deployment, make sure the following are installed on the local control machine:

* **Python 3.10+**
* **[uv](https://github.com/astral-sh/uv)** — Python package and project manager
* **[Pulumi CLI](https://www.pulumi.com/docs/install/)**
* **[OpenStack CLI](https://docs.openstack.org/python-openstackclient/latest/)**

---

## 1. Environment Setup

### OpenStack Credentials

Download your OpenStack `clouds.yaml` file and place it in the root directory of the repository.

Example:

```text
project/
├── clouds.yaml
├── Pulumi.yaml
├── pyproject.toml
└── ...
```

Make sure the OpenStack cloud referenced by Pulumi is correctly configured.

### Install Python Dependencies

Initialize the project environment using `uv`:

```bash
uv sync
```

This installs the project dependencies, including Ansible and the OpenStack SDK.

### Install Pulumi

If Pulumi is not already installed, follow the official installation guide:

[Pulumi Installation](https://www.pulumi.com/docs/install/)

---

## 2. Infrastructure Provisioning with Pulumi

Pulumi provisions the OpenStack infrastructure, including:

* Networks and subnets
* Routers
* Security groups
* Keypairs
* Compute instances
* HAProxy and Squid ports
* VIP ports
* Floating IPs
* VRRP allowed address pairs

### Initialize the Pulumi Stack

Select an existing stack or create a new one:

```bash
pulumi stack select dev || pulumi stack init dev
```

Install Pulumi dependencies:

```bash
pulumi install
```

Authenticate with Pulumi if required:

```bash
pulumi login
```

### Preview Changes

Before deploying, review the infrastructure changes:

```bash
uv run pulumi preview
```

### Deploy Infrastructure

Deploy the infrastructure:

```bash
uv run pulumi up --yes --parallel 4
```

### VRRP and Allowed Address Pairs

Pulumi configures OpenStack `allowed_address_pairs` on the HAProxy nodes to allow Keepalived to move the virtual IP between the master and backup nodes.

The HAProxy VIP is:

```text
10.0.1.100
```

This allows the VIP to move between:

```text
HAProxy master  → 10.0.1.11
HAProxy backup  → 10.0.1.12
```

without OpenStack blocking the VRRP traffic because of anti-spoofing rules.

---

## 3. Post-Deployment SSH Verification

If the infrastructure has been recreated, SSH may detect that a host key has changed.

Remove the old key if necessary:

```bash
ssh-keygen -f ~/.ssh/known_hosts -R <BASTION_FLOATING_IP>
```

Connect to the Bastion:

```bash
ssh -i ~/.ssh/openstack_ansible.pem ubuntu@<BASTION_FLOATING_IP>
```

Internal instances are accessed through the Bastion.

For example:

```bash
ssh -J ubuntu@<BASTION_FLOATING_IP> ubuntu@10.0.1.12
```

You can also use the project's SSH configuration:

```bash
ssh -F ./ssh/config 10.0.1.11
```

---

## 4. Configuration Management with Ansible

After the infrastructure has been provisioned, use Ansible to configure the instances.

The main deployment playbook is:

```text
notebooks/site.yml
```

Run the complete configuration:

```bash
uv run ansible-playbook -i inventory.ini notebooks/site.yml
```

The site playbook configures the different infrastructure components, including:

* Bastion/NAT gateway
* Squid
* HAProxy
* Keepalived
* Client services

### Target Specific Hosts

Run a playbook against a specific group:

```bash
uv run ansible-playbook -i inventory.ini notebooks/deploy_ha_proxy.yml
```

### Verbose Output

For troubleshooting:

```bash
uv run ansible-playbook -i inventory.ini notebooks/site.yml -vvv
```

### Check Mode

Preview Ansible changes without applying them:

```bash
uv run ansible-playbook -i inventory.ini notebooks/site.yml --check --diff
```

---

## 5. HAProxy Routing

HAProxy uses hostname-based routing through `/etc/haproxy/hosts.map`.

For example:

```text
team5.cstam.felcloud.tn be_team5
api.team5.cstam.felcloud.tn be_team5-api
```

The HAProxy configuration dynamically generates a backend for each entry in `haproxy_clients`.

Example variables:

```yaml
haproxy_clients:
  - { host: team5.cstam.felcloud.tn, name: team5, address: 10.0.2.179, port: 80 }
  - { host: api.team5.cstam.felcloud.tn, name: team5-api, address: 10.0.2.179, port: 8080 }
```

This produces:

```text
team5.cstam.felcloud.tn      → 10.0.2.179:80
api.team5.cstam.felcloud.tn  → 10.0.2.179:8080
```

The HAProxy template generates the corresponding backends automatically:

```jinja2
{% for c in haproxy_clients %}

backend be_{{ c.name }}

    option forwardfor

    option httpchk GET /

    server {{ c.name }} {{ c.address }}:{{ c.port }} check

{% endfor %}
```

---

## 6. Hot-Update HAProxy Routing

HAProxy routing can be updated without redeploying the entire infrastructure.

The hot-update playbook is:

```text
notebooks/update_haproxy.yml
```

Run:

```bash
uv run ansible-playbook -i inventory.ini notebooks/update_haproxy.yml
```

The playbook uses:

```yaml
serial: 1
```

This means HAProxy nodes are updated **one at a time**. The other node continues serving traffic while the first node is updated.

The deployment process is:

```text
Update hosts.map
       ↓
Render haproxy.cfg
       ↓
Validate configuration
       ↓
Replace configuration
       ↓
Reload HAProxy
       ↓
Move to next node
```

### HAProxy Configuration Validation

The playbook validates the generated configuration before installing it:

```yaml
validate: "/usr/sbin/haproxy -c -f %s"
```

This prevents an invalid HAProxy configuration from replacing the active configuration.

You can manually validate the installed configuration with:

```bash
sudo haproxy -c -f /etc/haproxy/haproxy.cfg
```

Check the service:

```bash
sudo systemctl status haproxy --no-pager
```

---

## 7. Keepalived / VRRP

Keepalived provides HA for the HAProxy and Squid services.

For HAProxy:

```text
Master: 10.0.1.11
Backup: 10.0.1.12
VIP:    10.0.1.100
```

For Squid:

```text
Master: 10.0.2.11
Backup: 10.0.2.12
VIP:    10.0.2.100
```

Keepalived monitors the HAProxy process and adjusts VRRP priority when the service becomes unavailable.

The VIP can therefore move between the master and backup node without changing the public routing configuration.

---

## 8. Useful Verification Commands

### Check HAProxy VIP

```bash
ip addr show ens3
```

Expected:

```text
10.0.1.100
```

on the active HAProxy node.

### Check Keepalived

```bash
sudo systemctl status keepalived --no-pager
```

View logs:

```bash
sudo journalctl -u keepalived -f
```

### Check HAProxy

```bash
sudo systemctl status haproxy --no-pager
```

Validate configuration:

```bash
sudo haproxy -c -f /etc/haproxy/haproxy.cfg
```

### Check HAProxy Listeners

```bash
sudo ss -lntp | grep -E ':80|:443'
```

### Test Backend Directly

From an HAProxy node:

```bash
curl http://10.0.2.179:80/
```

### Test HTTPS Through HAProxy

```bash
curl -vk https://10.0.1.100/
```

---

## 9. Project Structure

```text
project/
├── ansible.cfg
├── clouds.yaml
├── inventory.ini
├── __main__.py
├── notebooks/
│   ├── configure_bastion_gateway.yml
│   ├── deploy_client.yml
│   ├── deploy_ha_proxy.yml
│   ├── deploy_squid.yml
│   ├── update_haproxy.yml
│   ├── site.yml
│   └── templates/
│       ├── haproxy.cfg.j2
│       └── hosts.map.j2
├── Pulumi.dev.yaml
├── Pulumi.yaml
├── pyproject.toml
├── resources/
│   ├── compute.py
│   ├── config.py
│   ├── helpers.py
│   ├── keypairs.py
│   ├── main.py
│   ├── network.py
│   └── security_groups.py
├── ssh/
│   └── config
└── uv.lock
```

---

## 10. Typical Deployment Workflow

A complete deployment follows this sequence:

```text
1. Configure clouds.yaml
          ↓
2. Install dependencies
          ↓
3. Initialize Pulumi
          ↓
4. pulumi preview
          ↓
5. pulumi up
          ↓
6. Verify SSH connectivity
          ↓
7. Run Ansible site.yml
          ↓
8. Verify HAProxy / Squid / Keepalived
          ↓
9. Configure application routing
          ↓
10. Hot-update HAProxy when routing changes
```

For normal infrastructure changes:

```bash
uv run pulumi preview
uv run pulumi up --yes --parallel 4
```

For configuration changes:

```bash
uv run ansible-playbook -i inventory.ini notebooks/site.yml
```

For HAProxy routing changes only:

```bash
uv run ansible-playbook -i inventory.ini notebooks/update_haproxy.yml
```
