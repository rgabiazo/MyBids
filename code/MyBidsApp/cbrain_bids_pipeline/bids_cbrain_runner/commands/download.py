"""bids_cbrain_runner.commands.download

Utilities for downloading CBRAIN-generated derivative folders via SFTP
into a local BIDS-formatted dataset.

The public helper :func:`download_tool_outputs` resolves **where** files
should be placed in the ``derivatives`` tree, connects to the *data
provider* specified in the project configuration, and mirrors each
*Userfile* that matches the requested *tool*.

Design principles
-----------------
* **BIDS compliance** – Destination paths are derived from the dataset
  root and (optionally) from override rules in ``code/config/config.yaml``.
* **Safety first** – A *dry-run* mode prints every planned operation so
  large transfers can be previewed before execution.
* **Configurability** – Skip / keep directories and flattening behaviour
  are driven by *tools.yaml* entries to avoid hard-coding tool-specific
  quirks.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Mapping, Sequence

import requests

from bids_cbrain_runner.api.client import cbrain_get
from bids_cbrain_runner.api.client_openapi import CbrainClient
from bids_cbrain_runner.api.config_loaders import (
    load_pipeline_config,
    load_tools_config,
)
from bids_cbrain_runner.commands.bids_validator import find_bids_root_upwards
from bids_cbrain_runner.commands.sftp import sftp_connect_from_config
from bids_cbrain_runner.commands.userfiles import list_userfiles_by_group
from bids_cbrain_runner.utils.download_utils import (
    flattened_download,
    maybe_write_dataset_description,
    naive_download,
    resolve_output_dir,
)
from bids_cbrain_runner.utils.progress import run_with_spinner

logger = logging.getLogger(__name__)


# -----------------------------------------------------------------------------#
# Public API                                                                    #
# -----------------------------------------------------------------------------#
def download_tool_outputs(
    base_url: str,
    token: str,
    cfg: Mapping[str, Any],
    tool_name: str,
    output_type: str | None = None,
    userfile_id: int | None = None,
    group_id: int | None = None,
    *,
    flatten: bool = True,
    skip_dirs: Sequence[str] | None = None,
    dry_run: bool = False,
    force: bool = False,
    timeout: float | None = None,
    show_spinner: bool = True,
) -> None:
    """Download outputs of a *CBRAIN* tool into the local BIDS derivatives tree.

    The helper locates all *Userfiles* that belong to *tool_name* (filtered
    either by *userfile_id* or by *group_id*), opens an SFTP session with the
    data-provider defined in *cfg*, and transfers each matching folder into
    ``<BIDS_ROOT>/derivatives/<tool_name>`` (or an override specified in the
    project YAML).

    Args:
        base_url: Full CBRAIN portal URL (no trailing slash).
        token: Valid ``cbrain_api_token`` for authentication.
        cfg: SFTP provider configuration returned by
            :func:`bids_cbrain_runner.api.config_loaders.get_sftp_provider_config`.
        tool_name: Short name of the CBRAIN tool (e.g. ``"hippunfold"``).
        output_type: Optional CBRAIN file-type to match
            (defaults to ``"<ToolName>Output"``).
        userfile_id: Download a **single** userfile when supplied.
        group_id: Download **all** matching userfiles that belong to the
            specified **project** (*Group*).  Ignored when *userfile_id* is
            given.
        flatten: When *True*, strip the extra wrapper directory commonly used
            by CBRAIN pipelines so that outputs land directly under the
            subject/session hierarchy.
        skip_dirs: Additional directory names to ignore during the transfer
            (merged with any ``skip_dirs`` declared for *tool_name* in
            ``tools.yaml``).
        dry_run: Print the planned transfer operations without touching the
            network or filesystem.
        force: Overwrite existing local files when *True*.
        show_spinner: Display a console spinner while retrieving userfile
            metadata.

    Raises:
        ValueError: If neither *userfile_id* nor *group_id* is supplied.
        FileNotFoundError: When the BIDS dataset root cannot be located.

    Returns:
        None.  Progress and diagnostics are emitted via :pymod:`logging`.
    """
    skip_dirs = list(skip_dirs or [])  # ensure mutability

    # ------------------------------------------------------------------#
    # 1) Determine the expected CBRAIN *type* for this tool              #
    # ------------------------------------------------------------------#
    if not output_type:
        # Convention: strip dashes and capitalise each component, then append
        # the literal "Output" (e.g. "hippunfold" → "HippunfoldOutput").
        output_type = "".join(p.capitalize() for p in tool_name.split("-")) + "Output"

    # ------------------------------------------------------------------#
    # 2) Retrieve the set of Userfiles to be downloaded                  #
    # ------------------------------------------------------------------#
    if userfile_id:
        def fetch_single() -> List[Dict[str, Any]]:
            """Return metadata for the specific ``userfile_id``.

            Returns:
                A one-element list containing the JSON description of the
                requested userfile.

            Raises:
                RuntimeError: If the HTTP request fails or does not return
                    status ``200``.
            """
            try:
                resp = cbrain_get(
                    base_url, f"userfiles/{userfile_id}", token, timeout=timeout
                )
            except requests.exceptions.RequestException as exc:
                msg = f"Could not fetch userfile {userfile_id}: {exc}"
                logger.error(msg)
                raise RuntimeError(msg) from exc

            if resp.status_code != 200:
                msg = (
                    f"Could not fetch userfile {userfile_id}: HTTP {resp.status_code}"
                )
                logger.error(msg)
                raise RuntimeError(msg)

            return [resp.json()]

        userfiles: List[Dict[str, Any]] = run_with_spinner(
            fetch_single, "Retrieving downloads", show=show_spinner
        )
    elif group_id:
        client = CbrainClient(base_url, token)

        def fetch_group() -> List[Dict[str, Any]]:
            """Return all output userfiles available for ``group_id``.

            Returns:
                A list of userfile dictionaries filtered to ``output_type``.

            Raises:
                Exception: Propagated from ``list_userfiles_by_group`` on
                    network failures.
            """
            all_uf = list_userfiles_by_group(
                client, group_id, per_page=500, timeout=timeout
            )
            return [uf for uf in all_uf if uf.get("type") == output_type]

        userfiles = run_with_spinner(
            fetch_group, "Retrieving downloads", show=show_spinner
        )
    else:
        raise ValueError("Either *userfile_id* or *group_id* must be supplied.")

    if not userfiles:
        logger.info("No %s userfiles found for tool=%s", output_type, tool_name)
        return

    # ------------------------------------------------------------------#
    # 3) Resolve output directory and ensure dataset metadata            #
    # ------------------------------------------------------------------#
    bids_root = find_bids_root_upwards(os.getcwd())
    if not bids_root:
        raise FileNotFoundError("Could not locate dataset_description.json.")

    pipeline_cfg = load_pipeline_config()

    outdir = resolve_output_dir(
        bids_root=bids_root,
        tool_name=tool_name,
        config_dict=pipeline_cfg,
        force=force,
        dry_run=dry_run,
    )
    maybe_write_dataset_description(
        out_dir=outdir,
        tool_name=tool_name,
        config_dict=pipeline_cfg,
        dry_run=dry_run,
    )

    # ------------------------------------------------------------------#
    # 4) Open the SFTP session                                           #
    # ------------------------------------------------------------------#
    ssh, sftp = sftp_connect_from_config(cfg)
    if not ssh or not sftp:
        logger.error("SFTP connection failed; aborting download.")
        return

    # ------------------------------------------------------------------#
    # 5) Merge *skip/keep* directives from tools.yaml                    #
    # ------------------------------------------------------------------#
    tools_cfg = load_tools_config()
    tool_conf = tools_cfg.get(tool_name, {})
    cfg_skip: Sequence[str] = tool_conf.get("skip_dirs", [])
    cfg_keep: Sequence[str] = tool_conf.get("keep_dirs", [])
    final_skip = list(set(cfg_skip).union(skip_dirs))

    # ------------------------------------------------------------------#
    # 6) Transfer each userfile                                          #
    # ------------------------------------------------------------------#
    for uf in userfiles:
        remote_root = f"/{uf['name']}"
        logger.info(
            "Downloading %s → %s  (flatten=%s, skip_dirs=%s, dry_run=%s, force=%s)",
            remote_root,
            outdir,
            flatten,
            final_skip,
            dry_run,
            force,
        )

        if flatten:
            flattened_download(
                sftp=sftp,
                remote_dir=remote_root,
                local_root=outdir,
                tool_name=tool_name,
                skip_dirs=final_skip,
                keep_dirs=cfg_keep,
                wrapper=tool_name,
                dry_run=dry_run,
                force=force,
            )
        else:
            naive_download(
                sftp=sftp,
                remote_dir=remote_root,
                local_root=outdir,
                skip_dirs=final_skip,
                dry_run=dry_run,
                force=force,
            )

    # ------------------------------------------------------------------#
    # 7) Clean-up                                                        #
    # ------------------------------------------------------------------#
    sftp.close()
    ssh.close()
