"""Top-level package initialisation.

The :data:`__version__` attribute is derived from the wheel metadata at
runtime. Only one authoritative version string is stored in
``pyproject.toml``.
"""
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _pkg_version

try:                           # installed (editable or regular)
    __version__ = _pkg_version(__name__)
except PackageNotFoundError:   # running from a git checkout without `pip install -e .`
    __version__ = "0.0.0.dev0"

del _pkg_version, PackageNotFoundError
