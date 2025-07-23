"""
Helpers reused by several Click commands (*query*, *bids*, *download*).

The functions in this module focus on querying a PACS (via **findscu**)
and providing interactive convenience wrappers.  They do **not** perform
any I/O beyond the PACS network calls, making the helpers suitable for
unit-level testing.
"""

from __future__ import annotations

import logging
import os
from typing import Dict, List, Optional, Tuple

import click
from click import Context

from dicomatic.query.builder import build_findscu
from dicomatic.query.findscu import run_findscu
from dicomatic.query.parser import parse_studies_with_demographics
from dicomatic.utils.input_helpers import prompt_input
from dicomatic.utils.prompts import prompt_yes_no

log = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Core study-fetching helpers                                                 #
# --------------------------------------------------------------------------- #
def fetch_studies(ctx: Context, description: str) -> List[Dict[str, str]]:
    """Return studies matching ``StudyDescription``.

    Args:
        ctx: Click context; ``ctx.obj`` holds the merged configuration.
        description: PACS ``StudyDescription`` value to query for.

    Returns:
        list[dict[str, str]]: One study dictionary per match, as produced by
        :func:`dicomatic.query.parser.parse_studies_with_demographics`.
    """
    cfg = ctx.obj
    dic = cfg.dicom
    tags = cfg.dicom_query_tags
    tag_map = cfg.dicom_tag_map

    filters = {"StudyDescription": description}

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

    log.debug("Running findscu: %s", " ".join(cmd))
    raw = run_findscu(cmd)
    if not raw:
        log.error("No response from findscu")
        return []

    return parse_studies_with_demographics(raw, tag_map)


def fetch_studies_by_uids(ctx: Context, uids: List[str]) -> List[Dict[str, str]]:
    """Fetch studies individually by ``StudyInstanceUID``.

    The dcm4che C-FIND transaction typically emits two responses per UID
    (status ``ff00H`` followed by ``0H``). The duplicate guard collapses
    those repeats so that downstream code receives only one entry per UID.

    Args:
        ctx: Click context holding configuration in ``ctx.obj``.
        uids: ``StudyInstanceUID`` strings to fetch.

    Returns:
        list[dict[str, str]]: Study dictionaries with duplicate UIDs removed.
    """
    cfg = ctx.obj
    dic = cfg.dicom
    tags = cfg.dicom_query_tags
    tag_map = cfg.dicom_tag_map

    studies: List[Dict[str, str]] = []

    for uid in uids:
        filters = {"StudyInstanceUID": uid}

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

        log.debug("Running findscu for UID %s: %s", uid, " ".join(cmd))
        raw = run_findscu(cmd)
        if raw:
            studies.extend(parse_studies_with_demographics(raw, tag_map))
        else:
            log.warning("No response for UID %s", uid)

    # Collapse duplicate UID entries (later entries overwrite earlier)
    dedup: Dict[str, Dict[str, str]] = {}
    for st in studies:
        dedup[st.get("study_uid")] = st

    return list(dedup.values())


# --------------------------------------------------------------------------- #
# Interactive convenience helper                                              #
# --------------------------------------------------------------------------- #
def fetch_studies_interactive(
    ctx: Context,
    desc: Optional[str],
) -> Tuple[str, List[Dict[str, str]]]:
    """Prompt repeatedly until a valid ``StudyDescription`` yields results.

    The helper loops until either a non-empty result set is returned or a
    request to exit to the parent menu is made.

    Args:
        ctx: Click context carrying configuration.
        desc: Optional initial ``StudyDescription``. When ``None``, the function
            checks ``$DICOMATIC_STUDY_DESCRIPTION`` and then prompts.

    Returns:
        tuple[str, list[dict[str, str]]]:
            The validated ``StudyDescription`` and its matching study list.

    Notes:
        The function terminates the current Click command via
        :py:meth:`click.Context.exit` when a return to the main menu is
        requested.
    """
    # Attempt implicit value from CLI flag or environment variable
    if not desc:
        desc = os.environ.get("DICOMATIC_STUDY_DESCRIPTION")

    # First try without prompting
    if desc:
        studies = fetch_studies(ctx, desc)
        if studies:
            return desc, studies

        click.echo(f"[WARNING] '{desc}' not found. Provide a valid StudyDescription.", err=True)

    # Loop until a valid description is provided or the operation is aborted
    while True:
        user_desc = prompt_input("Enter StudyDescription to search for")
        if not user_desc:
            continue  # Empty input → re-prompt

        studies = fetch_studies(ctx, user_desc)
        if studies:
            return user_desc, studies

        click.echo(f"[ERROR] '{user_desc}' not found.", err=True)
        if prompt_yes_no("Return to main menu?"):
            ctx.exit()
