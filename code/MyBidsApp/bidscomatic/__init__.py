"""Proxy module mirroring the packaged :mod:`bidscomatic` implementation.

The project structure places the real implementation under the nested
``bidscomatic/bidscomatic`` directory so that packaging tools can include
tests and auxiliary files. Importing :mod:`bidscomatic` directly from the
source tree would otherwise expose this lightweight wrapper module and hide
subpackages such as ``bidscomatic.resources``. Mirroring the installed
package behaviour keeps the public surface consistent during development.
"""

from pathlib import Path

from . import bidscomatic as _impl

# Re‑export public attributes so ``import bidscomatic`` behaves the same
# whether the package is executed from a source checkout or an installed
# distribution.
__all__ = getattr(_impl, "__all__", [])
__version__ = _impl.__version__
load_config = _impl.load_config

# Mirror the implementation package path and append the in-tree ``tests``
# directory so that ``import bidscomatic.tests`` succeeds when running the
# bundled test-suite from a source checkout.
__path__ = list(_impl.__path__)
_tests_dir = Path(__file__).resolve().parent / "tests"
if _tests_dir.is_dir():
    __path__.append(str(_tests_dir))

