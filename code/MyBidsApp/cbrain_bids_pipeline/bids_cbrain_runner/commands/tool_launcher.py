"""Tool-launching helpers used by *cbrain-cli* (alias *bids-cbrain-cli*).

This module contains two thin wrappers around the OpenAPI façade
(:class:`bids_cbrain_runner.api.client_openapi.CbrainClient`) that simplify
the process of creating CBRAIN *tasks* either **once** (`launch_tool`) or
**in batch** over a project group (`launch_tool_batch_for_group`).

Key design choices
------------------
* **Stateless helpers** – All functions operate purely on the arguments that
  are passed in; they do not rely on global state.  This makes them easier to
  unit-test and to reuse in notebooks.
* **Early validation / fail-fast** – The functions raise quickly on missing
  or incompatible parameters so that errors surface close to their origin.
* **Separation of concerns** – Construction of the Boutiques JSON payload
  lives in :pymod:`bids_cbrain_runner.utils.task_builder`; OpenAPI calls are
  hidden behind :class:`CbrainClient`.

Typical usage
-------------
A single launch:

>>> launch_tool(
...     base_url="https://portal.cbrain.mcgill.ca",
...     token="abcdefgh",
...     tools_cfg=load_tools_config(),
...     tool_name="hippunfold",
...     extra_params={"modality": "T1w"},
...     group_id=12345,
... )

A batched launch over all *BidsSubject* userfiles in a group:

>>> launch_tool_batch_for_group(
...     base_url=base_url,
...     token=token,
...     tools_cfg=tools_cfg,
...     tool_name="hippunfold",
...     group_id=12345,
...     batch_type="BidsSubject",
... )
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional, Tuple

from ..api.client_openapi import CbrainClient, CbrainTaskError
from ..commands.userfiles import list_userfiles_by_group
from ..utils.task_builder import build_task_payload
from ..utils.progress import run_with_spinner

logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------#
# Public API                                                                   #
# -----------------------------------------------------------------------------#
def launch_tool(
    base_url: str,
    token: str,
    tools_cfg: Dict[str, Any],
    tool_name: str,
    extra_params: Optional[Dict[str, Any]] = None,
    group_id: Optional[int] = None,
    results_dp_id: Optional[int] = None,
    bourreau_id: Optional[int] = None,
    override_tool_config_id: Optional[int] = None,
    dry_run: bool = False,
    *,
    show_spinner: bool = True,
) -> None:
    """Launch a **single** CBRAIN task for *tool_name*.

    Args:
        base_url: Full CBRAIN portal URL (e.g. ``https://portal.cbrain.mcgill.ca``).
        token: ``cbrain_api_token`` with sufficient privileges to create tasks.
        tools_cfg: Parsed contents of *tools.yaml* (``load_tools_config()``).
        tool_name: Short name of the CBRAIN tool (matches the *type* field on tasks).
        extra_params: Optional overrides for the *invoke* section of the Boutiques
            descriptor (e.g. ``{"modality": "T1w"}``).
        group_id: Project (``Group``) ID that should own the new task.
        results_dp_id: Destination *Data Provider* for outputs (None → default).
        bourreau_id: Numeric ID of the execution server / HPC *Bourreau*.
        override_tool_config_id: Force a specific ``tool_config_id`` (bypasses
            cluster lookup in *tools.yaml*).
        dry_run: If **True**, print the JSON payload and exit without hitting
            the CBRAIN API.
        show_spinner: Display a console spinner for network operations.

    Raises:
        CbrainTaskError: For authentication issues, missing configuration or
            failed submissions.
        ValueError: When required parameters for a task are missing.

    Returns:
        None.  All status information is logged via :pymod:`logging`.
    """
    # ---------------------------------------------------------------------#
    # 1. Sanity checks                                                     #
    # ---------------------------------------------------------------------#
    if not token:
        # No valid session → cannot continue.
        raise CbrainTaskError("Missing CBRAIN API token.")

    # Retrieve the tool entry from tools.yaml to resolve cluster + IDs.
    tool_entry = tools_cfg.get(tool_name)
    if not tool_entry:
        raise CbrainTaskError(f"No entry for tool '{tool_name}' in tools.yaml.")

    clusters_cfg = tool_entry.get("clusters", {})
    default_cluster = tool_entry.get("default_cluster")

    # ---------------------------------------------------------------------#
    # 2. Determine which cluster (bourreau) to use                          #
    # ---------------------------------------------------------------------#
    cluster_name = default_cluster

    # If *bourreau_id* was supplied, try to map it back to a cluster name.
    if bourreau_id is not None:
        for cname, info in clusters_cfg.items():
            if info.get("bourreau_id") == bourreau_id:
                cluster_name = cname
                break

    if cluster_name not in clusters_cfg:
        raise CbrainTaskError(
            f"No cluster configuration for '{tool_name}' (requested '{cluster_name}')."
        )
    cluster_cfg = clusters_cfg[cluster_name]

    # ---------------------------------------------------------------------#
    # 3. Resolve IDs (tool_config_id, bourreau_id)                          #
    # ---------------------------------------------------------------------#
    tool_config_id = override_tool_config_id or cluster_cfg.get("tool_config_id")
    bourreau_id = bourreau_id or cluster_cfg.get("bourreau_id")

    if not tool_config_id or not bourreau_id:
        raise CbrainTaskError(
            "Missing *tool_config_id* or *bourreau_id* for "
            f"'{tool_name}' on cluster '{cluster_name}'."
        )

    # ---------------------------------------------------------------------#
    # 4. Fetch Boutiques descriptor to discover required inputs             #
    # ---------------------------------------------------------------------#
    client = CbrainClient(base_url, token)

    def _fetch_descriptor() -> dict:
        """Retrieve Boutiques descriptor for ``tool_config_id`` via API."""
        return client.fetch_boutiques_descriptor(tool_config_id)

    try:
        descriptor = run_with_spinner(
            _fetch_descriptor,
            "Submitting task",
            show=show_spinner,
        )
    except Exception as exc:
        raise CbrainTaskError(f"Error fetching Boutiques descriptor: {exc}") from exc

    inputs: List[Dict[str, Any]] = descriptor.get("inputs", [])

    # ---------------------------------------------------------------------#
    # 5. Construct default parameters from descriptor                       #
    # ---------------------------------------------------------------------#
    defaults: Dict[str, Any] = {}
    input_ids = set()
    for inp in inputs:
        inp_id = inp.get("id")
        if not inp_id:
            # Skip anonymous inputs (should not happen in valid descriptors).
            continue
        input_ids.add(inp_id)

        # Flags → default to string '0' (Boutiques convention for false).
        if inp.get("type") == "Flag":
            defaults[inp_id] = "0"

        # Use explicit default defined in descriptor.
        if "default-value" in inp or "defaultValue" in inp:
            dv = inp.get("default-value", inp.get("defaultValue"))
            # Ensure list-type inputs are serialised as lists.
            if inp.get("list") and not isinstance(dv, list):
                dv = [dv]
            defaults[inp_id] = dv

    # Overlay command-line overrides *after* descriptor defaults.
    combined_params = {**defaults, **(extra_params or {})}

    # ---------------------------------------------------------------------#
    # 6. Extract user-file IDs and separate non-Boutiques params            #
    # ---------------------------------------------------------------------#
    interface_ids: Optional[List[str]] = combined_params.pop("interface_userfile_ids", None)
    if interface_ids is not None and not isinstance(interface_ids, (list, tuple)):
        # Guarantee list-like type expected by CBRAIN.
        interface_ids = [interface_ids]
    if interface_ids is not None:
        interface_ids = [str(i) for i in interface_ids]

    invoke_params = {k: v for k, v in combined_params.items() if k in input_ids}
    cbrain_params = {k: v for k, v in combined_params.items() if k not in input_ids}

    # ---------------------------------------------------------------------#
    # 7. Validate required (non-optional) inputs                            #
    # ---------------------------------------------------------------------#
    required_ids = [
        inp["id"]
        for inp in inputs
        if not inp.get("optional", False)
        and "default-value" not in inp
        and "defaultValue" not in inp
    ]
    missing = [r for r in required_ids if r not in invoke_params]
    if missing:
        raise CbrainTaskError(
            f"Missing required parameter(s) for '{tool_name}': {', '.join(missing)}"
        )

    # ---------------------------------------------------------------------#
    # 8. Build Boutiques / CBRAIN task payload                              #
    # ---------------------------------------------------------------------#
    payload = build_task_payload(
        tool_name=tool_name,
        tool_config_id=tool_config_id,
        invoke=invoke_params,
        tools_cfg=tools_cfg,
        interface_userfile_ids=interface_ids,
        group_id=group_id,
        results_dp_id=results_dp_id,
        bourreau_id=bourreau_id,
        non_invoke_params=cbrain_params,
    )

    # ---------------------------------------------------------------------#
    # 9. Dry-run mode?                                                      #
    # ---------------------------------------------------------------------#
    if dry_run:
        logger.info("=== %s Dry-Run Payload ===", tool_name)
        logger.info(json.dumps({"cbrain_task": payload}, indent=2))
        logger.info("===================================")
        return

    # ---------------------------------------------------------------------#
    # 10. Submit the task via OpenAPI                                       #
    # ---------------------------------------------------------------------#
    def _create() -> dict:
        """Send the prepared task payload to CBRAIN and return the response."""
        return client.create_task(payload)

    response = run_with_spinner(
        _create,
        "Submitting task",
        show=show_spinner,
    )

    # The API may return either a single task dict or a list; normalise.
    tasks: List[Dict[str, Any]] = response if isinstance(response, list) else [response]

    # Strip CBRAIN’s verbose “key: value” description dump, keep last line.
    for task in tasks:
        desc = task.get("description", "")
        if isinstance(desc, str):
            task["description"] = desc.splitlines()[-1]

    logger.info(
        "Task created for '%s' on cluster '%s':\n%s",
        tool_name,
        cluster_name,
        json.dumps(tasks[0] if len(tasks) == 1 else tasks, indent=2),
    )


# -----------------------------------------------------------------------------#
def launch_tool_batch_for_group(
    base_url: str,
    token: str,
    tools_cfg: Dict[str, Any],
    tool_name: str,
    group_id: int,
    batch_type: Optional[str] = None,
    userfile_ids: Optional[List[int]] = None,
    extra_params: Optional[Dict[str, Any]] = None,
    results_dp_id: Optional[int] = None,
    bourreau_id: Optional[int] = None,
    override_tool_config_id: Optional[int] = None,
    dry_run: bool = False,
    *,
    show_spinner: bool = True,
) -> None:
    """Launch *one task per user-file* inside a CBRAIN group.

    Args:
        base_url: Portal URL.
        token: ``cbrain_api_token`` to authenticate the session.
        tools_cfg: Parsed *tools.yaml*.
        tool_name: Tool to be executed (e.g. ``hippunfold``).
        group_id: Numeric project (``Group``) ID whose user-files are iterated.
        batch_type: Optional CBRAIN file-type filter
            (e.g. ``"BidsSubject"``).  **None** launches on *all* user-files.
        userfile_ids: Explicit list of user-file IDs to process.  When set, only
            those IDs present in ``group_id`` are launched.  Useful for
            launching a single subject without enumerating the entire group.
        extra_params: Parameters merged into every individual *invoke* block.
        results_dp_id: Destination Data Provider for outputs.
        bourreau_id: Execution server to run on.
        override_tool_config_id: Force a particular ``tool_config_id``.
        dry_run: Print the payloads but skip submission.
        show_spinner: Display a console spinner during network calls.

    Raises:
        CbrainTaskError: Raised if no matching user-files are found or for any
            error during individual launches.

    Returns:
        None.
    """
    extra_params = extra_params or {}

    # ------------------------------------------------------------------#
    # 1. Collect user-files matching the filter                         #
    # ------------------------------------------------------------------#
    client = CbrainClient(base_url, token)

    def _fetch_userfiles() -> List[Dict[str, Any]]:
        """Retrieve all user-files from ``group_id`` via the CBRAIN API."""
        return list_userfiles_by_group(client, group_id, per_page=500)

    userfiles = run_with_spinner(
        _fetch_userfiles,
        "Submitting task",
        show=show_spinner,
    )
    if batch_type:
        userfiles = [uf for uf in userfiles if uf.get("type") == batch_type]
    if userfile_ids is not None:
        wanted = {int(uid) for uid in userfile_ids}
        userfiles = [uf for uf in userfiles if int(uf.get("id")) in wanted]

    if not userfiles:
        filt = f"type={batch_type}" if batch_type else "<any>"
        raise CbrainTaskError(
            f"No user-files of {filt} found in group={group_id}."
        )

    # ------------------------------------------------------------------#
    # 2. Launch (or simulate) one task per user-file                    #
    # ------------------------------------------------------------------#
    for uf in userfiles:
        uf_id = uf["id"]

        # Build per-subject parameter overrides.
        extra_ids = extra_params.get("interface_userfile_ids")
        if extra_ids is None:
            combined_ids = [uf_id]
        else:
            if not isinstance(extra_ids, (list, tuple)):
                extra_ids = [extra_ids]
            combined_ids = [uf_id] + list(extra_ids)

        batch_params: Dict[str, Any] = {
            **extra_params,
            "interface_userfile_ids": combined_ids,
        }
        if tools_cfg.get(tool_name, {}).get("requires_subject_dir"):
            batch_params["subject_dir"] = uf_id
        if "bids_dir" not in batch_params:
            batch_params["bids_dir"] = uf_id

        logger.info(
            "[BATCH %d] Launching '%s' (dry_run=%s)…",
            uf_id,
            tool_name,
            dry_run,
        )

        launch_tool(
            base_url=base_url,
            token=token,
            tools_cfg=tools_cfg,
            tool_name=tool_name,
            extra_params=batch_params,
            group_id=group_id,
            results_dp_id=results_dp_id,
            bourreau_id=bourreau_id,
            override_tool_config_id=override_tool_config_id,
            dry_run=dry_run,
            show_spinner=show_spinner,
        )
