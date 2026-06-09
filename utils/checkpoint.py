import json, os, shutil
from utils.logger import get_logger

log = get_logger("Checkpoint")

CHECKPOINT_DIR = "data/checkpoints"
BACKUP_DIR = "data/checkpoints/backups"

def init_dirs():
    os.makedirs(CHECKPOINT_DIR, exist_ok=True)
    os.makedirs(BACKUP_DIR, exist_ok=True)

def save_checkpoint(name: str, data: dict):
    init_dirs()
    path = os.path.join(CHECKPOINT_DIR, f"{name}.json")
    backup = os.path.join(BACKUP_DIR, f"{name}_backup.json")

    # Save safely
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2)

    # Backup previous if exists
    if os.path.exists(path):
        shutil.copy2(path, backup)

    os.replace(tmp, path)

def load_checkpoint(name: str) -> dict | None:
    init_dirs()
    path = os.path.join(CHECKPOINT_DIR, f"{name}.json")
    backup = os.path.join(BACKUP_DIR, f"{name}_backup.json")

    try:
        if os.path.exists(path):
            with open(path, "r") as f:
                return json.load(f)
    except Exception as e:
        log.error(f"Checkpoint corruption {name}: {e}. Trying backup.")
        if os.path.exists(backup):
            try:
                with open(backup, "r") as f:
                    return json.load(f)
            except Exception:
                pass
    return None

def clear_checkpoints():
    init_dirs()
    for f in os.listdir(CHECKPOINT_DIR):
        if f.endswith(".json"):
            os.remove(os.path.join(CHECKPOINT_DIR, f))
