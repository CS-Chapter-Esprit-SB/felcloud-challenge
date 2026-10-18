# -----------------------------------------------------------------------------
import pulumi_openstack as openstack
from jinja2 import Environment, FileSystemLoader
from pathlib import Path
from .config import inbound_gateway_ip, outbound_gateway_ip, backend_ip

def get_root()->Path:
    """
    Return the root directory of the project. recursivly look for .git or .lock file to find the root directory of the project.
    """
    current_dir = Path(__file__).resolve().parent
    while current_dir != current_dir.parent:
        if (current_dir / ".git").exists() or (current_dir / "Pipfile.lock").exists():
            return current_dir
        current_dir = current_dir.parent
    raise RuntimeError("Could not find the root directory of the project.")


ROOT_DIR = get_root()


def generate_inventory_file(args: list[str]) -> None:
    (
        bastion_fip,
        h_master,
        h_backup,
        s_master,
        s_backup,
        h_vip_ip,
        s_vip_ip,
        bastion_inbound_ip,
        bastion_outbound_ip,
        inbound_cidr,
        outbound_cidr,
    ) = args

    env = Environment(loader=FileSystemLoader(ROOT_DIR/"resources"/"configs"))
    template = env.get_template("inventory.j2")

    # 2. Define your context variables (your python variables)
    context = {
        "bastion_fip": bastion_fip,
        "h_master": h_master,
        "h_backup": h_backup,
        "s_master": s_master,
        "s_backup": s_backup,
        "backend_ip": backend_ip,
        "bastion_inbound_ip": bastion_inbound_ip,
        "bastion_outbound_ip": bastion_outbound_ip,
        "inbound_cidr": inbound_cidr,
        "outbound_cidr": outbound_cidr,
        "inbound_gateway_ip": inbound_gateway_ip,
        "outbound_gateway_ip": outbound_gateway_ip,
        "h_vip_ip": h_vip_ip,
        "s_vip_ip": s_vip_ip,
    }

    # 3. Render the template
    inventory_content = template.render(context) + "\n"
    with open(ROOT_DIR/"inventory.ini", "w", encoding="utf-8") as f:
        _ = f.write(inventory_content)

def get_reserved_floating_ip(name: str, fip_id: str) -> openstack.networking.FloatingIp:
    """Adopt a pre-reserved floating IP by ID. Pulumi never creates or deletes it."""
    return openstack.networking.FloatingIp.get(f"floatip_{name}", id=fip_id)

def get_user_data_config()-> str:
    """Read the user_data.sh file and return its content as a string."""
    with open(ROOT_DIR/"resources"/"configs"/"user.config", "r", encoding="utf-8") as f:
        return f.read()