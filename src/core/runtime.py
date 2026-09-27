"""Shared execution controls for the GUI and analysis engines."""
from datetime import datetime
from pathlib import Path
import tempfile


class AnalysisCancelled(Exception):
    """Raised only at safe checkpoints; never terminate a thread during a write."""


def create_run_directory(output_root, label="analysis"):
    root = Path(output_root)
    root.mkdir(parents=True, exist_ok=True)
    prefix = f"{label}_{datetime.now():%Y%m%d_%H%M%S}_"
    return tempfile.mkdtemp(prefix=prefix, dir=str(root))
