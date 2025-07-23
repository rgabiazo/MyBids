"""
Small helpers concerned with credential handling and authentication against the
remote DICOM archive.  All logic is kept free of I/O side‑effects (apart from
interactive prompting) so the functions remain easy to unit‑test.
"""

from __future__ import annotations

import sys

import click

from dicomatic.query.builder import build_findscu
from dicomatic.query.findscu import run_findscu

# -----------------------------------------------------------------------------
# Interactive helpers
# -----------------------------------------------------------------------------


def prompt_for_credentials(dic):  # noqa: D401 – imperative is clearer here
    """Prompt for missing DICOM credentials.

    Args:
        dic: ``cfg.dicom`` namespace populated by :pyfunc:`dicomatic.config_loader.load_config`.

    Returns:
        tuple[str, str]: ``(username, password)`` provided by *dic* or entered
        interactively by the operator.
    """
    user = dic.username
    pwd = dic.password

    # Only prompt when placeholders or blanks are detected ---------------------
    if not user or user in ("YOUR_USERNAME", ""):
        user = click.prompt("DICOM username", type=str)
    if not pwd or pwd in ("YOUR_PASSWORD", ""):
        pwd = click.prompt("DICOM password", hide_input=True)

    return user, pwd


# -----------------------------------------------------------------------------
# Connection test
# -----------------------------------------------------------------------------


def test_connection(cfg):
    """Verify that the current credentials are accepted by the PACS.

    A zero‑match C‑FIND query is issued so no actual data is returned yet the
    server still authenticates the association.  Running *findscu* via Docker
    means the validation behaves the same on all platforms.

    Args:
        cfg: Parsed YAML/CLI configuration namespace.

    Returns:
        bool: ``True`` when *findscu* exits with status *0* (credentials ok);
        ``False`` otherwise.
    """
    dic = cfg.dicom
    tags = cfg.dicom_query_tags
    # Force an empty result set by filtering on an unlikely description --------
    filters = {"StudyDescription": "__DICOM_AUTH_TEST__"}

    cmd = build_findscu(
        container=dic.container,
        bind=dic.bind,
        server=dic.server,
        port=dic.port,
        tls=dic.tls,
        username=dic.username,
        password=dic.password,
        query_tags=tags,
        filters=filters,
    )
    out = run_findscu(cmd)
    return out is not None


# -----------------------------------------------------------------------------
# Public orchestration helper
# -----------------------------------------------------------------------------


def ensure_authenticated(cfg):  # noqa: D401 – imperative form preferred
    """Exit early unless the PACS accepts the configured credentials.

    The helper attempts a silent check first, falling back to a single prompt
    when the initial attempt fails.  All messaging is intentionally minimal so
    scripts embedding *dicomatic* can parse stdout/stderr deterministically.

    Workflow:
        1. Call :func:`test_connection` with the current configuration.
        2. If the test fails, obtain fresh credentials via
           :func:`prompt_for_credentials`.
        3. On a second failure, emit a short *INFO* banner then abort the
           process with status *1*.
        4. On success, emit the success banner exactly once.

    Args:
        cfg: Parsed YAML/CLI configuration namespace.  ``cfg.dicom.username``
            and ``cfg.dicom.password`` may be mutated when prompting occurs.
    """
    # 1) Fast‑path – configuration is already valid ---------------------------
    if test_connection(cfg):
        return

    # 2) Retry with fresh interactive credentials -----------------------------
    user, pwd = prompt_for_credentials(cfg.dicom)
    cfg.dicom.username, cfg.dicom.password = user, pwd

    # Separate the prompt from subsequent INFO banners for clarity ------------
    click.echo()

    if not test_connection(cfg):
        click.echo("[INFO] Authentication failed. Please try again.")
        sys.exit(1)

    click.echo("[INFO] Authentication successful.")