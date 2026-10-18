import yaml
from pathlib import Path
from .models import Sandbox


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

PROJECT_ROOT = get_root()

CLIENTS_NEW = PROJECT_ROOT / "clients" / "new"
CLIENTS_BUILT = PROJECT_ROOT / "clients" / "built"

def load_sandboxes() -> list[tuple[Path, Sandbox]]:
    """
    Load pending and previously provisioned sandbox configurations.

    Both directories are included so that moving a YAML file does not
    remove its corresponding resources from Pulumi's desired state.
    """
    loaded: list[tuple[Path, Sandbox]] = []

    for directory in (CLIENTS_NEW, CLIENTS_BUILT):
        directory.mkdir(parents=True, exist_ok=True)

        for path in sorted(directory.glob("*.yml")):
            with path.open("r", encoding="utf-8") as file:
                data = yaml.safe_load(file)  # pyright: ignore[reportAny]

            sandbox = Sandbox.model_validate(data)
            loaded.append((path, sandbox))

    return loaded