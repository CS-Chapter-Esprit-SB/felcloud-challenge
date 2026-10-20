import yaml
from pathlib import Path
from .models import Sandbox
from pydantic import ValidationError

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
LoadedSandbox = tuple[Path, Sandbox]


def load_sandboxes() -> tuple[list[LoadedSandbox], list[str]]:
    paths = sorted([*CLIENTS_NEW.glob("*.yaml"), *CLIENTS_NEW.glob("*.yml")])
    loaded: list[LoadedSandbox] = []
    errors: list[str] = []

    for path in paths:
        try:
            raw = yaml.safe_load(path.read_text())  # pyright: ignore[reportAny]
            if not isinstance(raw, dict):
                errors.append(f"{path.name}: top level must be a mapping")
                continue
            loaded.append((path, Sandbox.model_validate(raw)))
        except yaml.YAMLError as exc:
            errors.append(f"{path.name}: invalid YAML: {str(exc).splitlines()[0]}")
        except ValidationError as exc:
            for err in exc.errors():
                loc = ".".join(str(p) for p in err["loc"]) or "<root>"
                errors.append(f"{path.name}: {loc}: {err['msg']}")

    return loaded, errors


