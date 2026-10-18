import shutil
from pathlib import Path


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

def archive_sandboxes() -> None:
    CLIENTS_BUILT.mkdir(parents=True, exist_ok=True)
    for source in sorted(CLIENTS_NEW.glob("*.yml")):
        destination = CLIENTS_BUILT / source.name

        if destination.exists():
            raise FileExistsError(
                f"Cannot archive {source.name}: {destination} already exists"
            )

        _ = shutil.move(str(source), str(destination))
        print(f"Archived {source.name}")


if __name__ == "__main__":
    archive_sandboxes()