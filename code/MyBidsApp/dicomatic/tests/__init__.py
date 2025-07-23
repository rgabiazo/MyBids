import sys
from pathlib import Path

# Ensure the dicomatic package is importable when run from the repository root
pkg_root = Path(__file__).resolve().parents[1]
if str(pkg_root) not in sys.path:
    sys.path.insert(0, str(pkg_root))
