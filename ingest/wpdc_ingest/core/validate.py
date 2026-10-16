"""Run the repository validator (the same one the site build runs)."""
from __future__ import annotations

import subprocess
import sys

from .archive import REPO_ROOT


def run() -> int:
    return subprocess.call([sys.executable, str(REPO_ROOT / "scripts" / "validate.py")], cwd=REPO_ROOT)
