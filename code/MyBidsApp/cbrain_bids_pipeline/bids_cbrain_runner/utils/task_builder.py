"""
Helpers for constructing CBRAIN *task* payloads and descriptions.

CBRAIN tasks are created by POST‑ing a JSON document to the Portal’s
``/tasks`` endpoint.  Building that document involves several small
conventions that are best kept in one place so that *all* CLI commands create
consistent, reproducible tasks.

Responsibilities
================
1. **Human‑readable description** – Provide a concise summary for the CBRAIN UI
   (appears as the *task description* column).  The description logic tries to
   extract meaningful identifiers (``subject_dir`` or first
   ``interface_userfile_ids`` element) when a dedicated *template* is not
   supplied.
2. **Cluster resolution** – Determine the target execution cluster from either
   an *explicit* ``bourreau_id`` or the tool‑specific default defined in
   ``tools.yaml``.
3. **Payload assembly** – Combine mandatory and optional keys into the final
   dictionary expected by the CBRAIN API, attaching the description only when
   a template demands it so that generic launches don’t clutter the UI with
   redundant text.

No network I/O is performed here; the caller is responsible for submitting the
payload through an OpenAPI client or raw HTTP request.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

__all__ = [
    "get_description",
    "build_task_payload",
]

# -----------------------------------------------------------------------------
# Description helper
# -----------------------------------------------------------------------------

def get_description(
    tool_name: str,
    invoke: Dict[str, Any],
    tools_cfg: Dict[str, Any],
    cluster: str,
) -> str:
    """Return a human‑friendly description string for a CBRAIN task.

    Precedence order:

    1. If ``tools.yaml`` defines ``description_template`` for *tool_name*,
       format the template with ``tool_name``, ``invoke`` and ``cluster``.
    2. Else, if ``invoke`` contains a ``subject_dir`` key, embed its value.
    3. Else, if ``interface_userfile_ids`` is present (and non‑empty), embed
       the *first* ID.
    4. Fallback to *generic* text – ``"Launch '<tool_name>' on <cluster>"``.

    Args:
        tool_name: Canonical tool identifier (e.g. ``hippunfold``).
        invoke: Mapping of Boutiques parameters to be sent to CBRAIN.
        tools_cfg: Parsed YAML section for all tools (``load_tools_config``).
        cluster: Name of the execution cluster ("beluga", "cedar", etc.).

    Returns:
        Description string suitable for the task’s ``description`` field.
    """
    tool_entry = tools_cfg.get(tool_name, {})

    # --- 1. Explicit template in YAML -----------------------------------------
    tpl = tool_entry.get("description_template")
    if tpl:
        return tpl.format(tool_name=tool_name, invoke=invoke, cluster=cluster)

    # --- 2. subject_dir parameter ---------------------------------------------
    if "subject_dir" in invoke:
        return f"{tool_name} run on subject directory {invoke['subject_dir']}"

    # --- 3. First userfile ID --------------------------------------------------
    if "interface_userfile_ids" in invoke and invoke["interface_userfile_ids"]:
        first = invoke["interface_userfile_ids"]
        val = first[0] if isinstance(first, list) else first
        return f"{tool_name} run on subject directory {val}"

    # --- 4. Generic fallback ---------------------------------------------------
    return f"Launch '{tool_name}' on {cluster}"


# -----------------------------------------------------------------------------
# Payload builder
# -----------------------------------------------------------------------------

def build_task_payload(
    tool_name: str,
    tool_config_id: int,
    invoke: Dict[str, Any],
    tools_cfg: Dict[str, Any],
    interface_userfile_ids: Optional[List[str]] = None,
    group_id: Optional[int] = None,
    results_dp_id: Optional[int] = None,
    bourreau_id: Optional[int] = None,
    non_invoke_params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Assemble a JSON‑serialisable dict compatible with CBRAIN’s /tasks API.

    Args:
        tool_name: CBRAIN tool slug.
        tool_config_id: Specific *ToolConfig* ID chosen for this run.
        invoke: Dict of Boutiques parameters required by the tool.
        tools_cfg: Full ``tools.yaml`` structure (already parsed).
        interface_userfile_ids: Optional list of *input* userfile IDs.
        group_id: Optional project ID to which the task should belong.
        results_dp_id: Optional data‑provider ID where results are stored.
        bourreau_id: Optional execution server override.
        non_invoke_params: Mapping of CBRAIN-specific parameters that should
            live alongside ``invoke`` within the ``params`` block rather than
            inside it.  Examples include flags such as
            ``cbrain_enable_output_cache_cleaner``.

    Returns:
        A ``dict`` ready to be serialised to JSON and POST‑ed to CBRAIN.
    """
    # --- 1. Determine cluster name --------------------------------------------
    tool_entry = tools_cfg.get(tool_name, {})
    clusters = tool_entry.get("clusters", {})
    cluster_name = tool_entry.get("default_cluster", "")

    if bourreau_id is not None:
        # Walk cluster configs to find a matching bourreau.
        for cname, info in clusters.items():
            if info.get("bourreau_id") == bourreau_id:
                cluster_name = cname
                break

    # --- 2. Prepare description (only if template exists) ---------------------
    invoke_for_desc = dict(invoke)  # shallow copy for safe mutation
    if interface_userfile_ids:
        invoke_for_desc["interface_userfile_ids"] = interface_userfile_ids

    description: Optional[str] = None
    if tool_entry.get("description_template"):
        description = get_description(tool_name, invoke_for_desc, tools_cfg, cluster_name)

    # --- 3. Build base payload -------------------------------------------------
    payload: Dict[str, Any] = {
        "type": tool_name,
        "tool_config_id": tool_config_id,
        "params": {"invoke": invoke},
    }

    if non_invoke_params:
        payload["params"].update(non_invoke_params)

    # Optional fields – added only when supplied -------------------------------
    if interface_userfile_ids:
        payload["params"]["interface_userfile_ids"] = interface_userfile_ids
    if group_id is not None:
        payload["group_id"] = group_id
    if results_dp_id is not None:
        payload["results_data_provider_id"] = results_dp_id
    if bourreau_id is not None:
        payload["bourreau_id"] = bourreau_id
    if description is not None:
        payload["description"] = description

    return payload
