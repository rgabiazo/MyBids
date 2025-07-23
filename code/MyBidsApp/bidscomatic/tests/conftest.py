"""Pytest configuration for bidscomatic tests."""

# No manual modification of ``sys.path`` is required.  The tests rely solely on
# the standard Python import mechanism and the package installation performed by
# the test environment.

import pytest

# Skip the entire suite when optional heavy dependencies are unavailable.
pytest.importorskip("pandas")
pytest.importorskip("nibabel")

