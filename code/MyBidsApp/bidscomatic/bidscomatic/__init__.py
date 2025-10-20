"""
bidscomatic package initialisation.

The module performs two small but essential tasks:

1. **Expose the version string**
   ``bidscomatic.__version__`` is resolved at import-time from the installed
   distribution metadata so that all runtime contexts (install, editable,
   frozen app) surface the same canonical value.

2. **Re-export the public YAML loader**
   The public helper :func:`bidscomatic.config.load_config` is re-exported at
   the top level for convenience so call-sites can simply do::

       from bidscomatic import load_config

Module attributes
-----------------
__version__ : str
    Semantic version derived from the installed wheel.
load_config : Callable
    Shortcut to :pyfunc:`bidscomatic.config.load_config`.

The implementation is intentionally minimal and side-effect free.
"""

import importlib.util
from pathlib import Path
from importlib.metadata import PackageNotFoundError, version

# --------------------------------------------------------------------------- #
# Version resolution
# --------------------------------------------------------------------------- #
try:
    # Using the *distribution* name works for both regular and editable installs.
    __version__: str = version("bidscomatic")
except PackageNotFoundError:
    # Source tree without an installed wheel (e.g. early development checkout).
    # Falling back to a sentinel makes it obvious in logs/tests that packaging
    # metadata is missing rather than silently mis-reporting the version.
    __version__ = "0.0.0"

# --------------------------------------------------------------------------- #
# Public re-exports
# --------------------------------------------------------------------------- #
# Deferred import keeps the module import graph slim and avoids a potential
# circular-import when bidscomatic.config later needs symbols from the top
# level.
from .config import load_config  # noqa: E402 – deliberate late import

__all__: list[str] = ["load_config", "__version__"]

# Ensure ``bidscomatic.tests`` can be imported from an editable checkout by
# appending the in-tree tests directory to the package search path.
_tests_dir = Path(__file__).resolve().parent.parent / "tests"
if _tests_dir.is_dir():
    __path__ = list(__path__)  # type: ignore[name-defined]
    if str(_tests_dir) not in __path__:
        __path__.append(str(_tests_dir))
    spec = importlib.util.spec_from_file_location("bidscomatic.tests", _tests_dir / "__init__.py")
    if spec and spec.loader:
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        import sys

        sys.modules.setdefault("bidscomatic.tests", module)
