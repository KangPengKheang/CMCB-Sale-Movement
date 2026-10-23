"""Package the shared map boundaries into the independently built backend."""
from pathlib import Path
import shutil

backend = Path(__file__).resolve().parents[1]
source = backend.parent / "frontend/src/data/boundaries/phnom_penh_khans.json"
destination = backend / "boundaries/phnom_penh_khans.json"
destination.parent.mkdir(parents=True, exist_ok=True)
shutil.copyfile(source, destination)
print("Packaged Phnom Penh boundaries for the backend service.")
